"""Name a vertebra from its neighbours alone, on synthetic columns, and how many dimensions that takes.

    python run.py neighbour --outdir records/neighbour-2026-10-26
    python run.py neighbour-enumerate --shard 0 --of 4 --out shard0.json   # then --gather
    python run.py neighbour-figures --json records/neighbour-2026-10-26/neighbour.json

THE QUESTION. Vertebra i cannot be measured (instrumented, overlapped, clipped by the collimator).
Can its name be computed from the morphology of the vertebrae BESIDE it, with i's own
measurements withheld, and how many dimensions does the discriminating information occupy?
docs/NEIGHBOUR_IDENTITY_STUDY.md is the brief; docs/NEIGHBOUR_IDENTITY_RESULTS.md the answer.

EVERYTHING HERE IS SYNTHETIC. Columns are drawn by panjabi.py from Panjabi's published means and
spreads, nothing else; no CT, no label, no corpus is read. The truth every table scores against
is the COUNT from C2: the name of a body is its position in the column, so a model that could see
the position would be counting, which is the thing this programme exists to avoid. Hence the
first rule of the design:

NO ABSOLUTE POSITION REACHES A MODEL. A feature vector is built from the measurements of the
visible neighbours and from nothing else; `features` takes the column's values and the target's
index only to look the neighbours up, and tests/test_neighbour.py asserts that moving the same
neighbourhood to another position of another column leaves the features and the call unchanged.

THE ARMS say which neighbours are visible, by offset from the target: below1 (+1), above1 (-1),
flank (-1, +1), flank2 (-2, -1, +1, +2) and, for reference only, with_target (-2 .. +2, the
target included). THE REGIMES say which measures survive a projection: lateral (posterior
height, the two end-plate depths, canal depth), ap (posterior height, the two end-plate widths,
canal width) and both (all seven a SPINEPS mask gives). A projection is idealised here as a clean
selection of in-plane measures, which is OPTIMISTIC: magnification, obliquity and superimposition
are not modelled, so the single-plane arms are an upper bound on what an image yields.

THE NORMALISATION is the second trap. Dividing by the median of the visible bodies, as border.py
does on a whole CT, lets the set of visible levels leak into the feature; here the main arm
divides every measure by a FIXED constant from the table (the geometric mean of the measure's
published means over the column), which carries no position, and a side arm sweeps the median
over 2, 4, 6, 10 bodies and the whole column to bound what the leak is worth.

THE SOLUTIONS, each scored on the same columns:
  A  a scalar index: the first linear discriminant of the neighbour features, written out as a
     formula in log millimetres, with the check that its class means are monotone down the column
  B  a closed-form Gaussian classifier on the PUBLISHED means and spreads, nothing fitted: one
     free log-size per column profiled out, a diagonal covariance from the table and the
     measurement noise; an independent check on the fitted models, since it cannot learn an
     artefact of the generator
  C  a discriminative softmax classifier on the neighbour features (border.py's logistic
     regression taken to 22 classes, fitted by Newton's method), the deliverable where no
     formula exists
  D  measure-set selection by exhaustive enumeration of the 127 subsets of the seven measures,
     ranked by the WORST phenotype, selected on one seed and scored on another
  E  the projection-restricted variants: D's rows at the lateral and ap sets, and the main
     table's three regimes
  F  selective prediction: C abstains below a confidence chosen on the selection seed; accuracy
     against coverage on the scoring seed
  and the dimensionality curve: the discriminant spectrum and C's cousin, the Gaussian
  classifier, restricted to its first d discriminant directions, d = 1 .. p.

SEEDS. The models are fitted on columns from FIT_SEED, every threshold and subset is chosen on
columns from SELECT_SEED, and every number reported is scored on columns from SCORE_SEED, so no
reported number was chosen by looking at itself.

CHANCE IS NOT 1/23. A target is every eligible position of every column, so the marginal over the
true names is uniform over the levels the arm can see (an edge level with no neighbour on the
needed side is never a target); the record states that marginal, the majority-class rate and the
uniform rates for exact and within-one naming.

THE SIGNED OFFSET is the finding to look for, not the error rate. In a t13 column the count names
the thirteenth rib-bearing body L1 and every body below it one name further than its shape says;
a model fitted on typical columns names those bodies by their shape, one level above the count,
confidently and systematically. That is a different finding from scatter, and it is reported per
phenotype beside the rate against the rib reading, which names the same bodies the way the shape
does.

r, the correlation between a patient's offsets in the different measures, is UNIDENTIFIED
(covariance.py): the main table is at r = 0, the optimistic end, and the sweep reports the
identified set of every regime's accuracy over the grid with its Imbens-Manski interval and the
sign of each between-regime difference, never a point estimate alone.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import panjabi as P                                                  # noqa: E402
import covariance as CV                                              # noqa: E402

ARMS: Dict[str, Tuple[int, ...]] = {
    "below1": (1,), "above1": (-1,), "flank": (-1, 1), "flank2": (-2, -1, 1, 2),
    "with_target": (-2, -1, 0, 1, 2)}
NEIGHBOUR_ARMS = ("below1", "above1", "flank", "flank2")
REGIMES: Dict[str, List[str]] = {
    "lateral": ["h_post", "endplate_depth", "endplate_lower_depth", "canal_ap"],
    "ap": ["h_post", "endplate", "endplate_lower", "canal_w"],
    "both": list(CV.SPINEPS_7)}
MEASURE_NAME = {"endplate": "upper end-plate width", "endplate_depth": "upper end-plate depth",
                "endplate_lower": "lower end-plate width",
                "endplate_lower_depth": "lower end-plate depth",
                "h_post": "posterior body height", "canal_w": "canal width", "canal_ap": "canal depth"}
# the name the count from C2 gives the body at each position; a column never holds more than 23
COUNT_NAMES = P.CERVICAL + P.THORACIC + ["L%d" % i for i in range(1, 8)]
# the names a model fitted on typical columns can give
CLASSES = list(P.LEVELS)
K = len(CLASSES)
SYNTH = dict(rho=0.5, noise_mm=1.0, scale_sd=0.07, blend=0.5)
FIT_SEED, SELECT_SEED, SCORE_SEED = 11, 23, 97
N_FIT, N_SELECT, N_SCORE = 300, 150, 200
COVERAGES = (0.9, 0.75, 0.5)
MEDIAN_BODIES = (1, 2, 3, 5, "all")
EPS = 1e-9


# ---- names and truths -----------------------------------------------------------------------

def count_names(column: P.Column) -> List[str]:
    """What the count from C2 calls each body: its position, whatever its shape."""
    return COUNT_NAMES[:len(column)]


def rib_ordinals(column: P.Column) -> List[Optional[int]]:
    """The ordinal (index into COUNT_NAMES) the rib reading gives each body, where it differs
    from the count: on the three thoracolumbar phenotypes the bodies below the transitional one
    move by RIB_SHIFT and the transitional body itself has no name in the count's list (T13 or
    an L1 read as thoracic), so it is None and left out of the rib score."""
    n = len(column)
    t = column.transitional_at
    if t is None:
        return list(range(n))
    shift = P.RIB_SHIFT.get(column.phenotype, 0)
    out: List[Optional[int]] = list(range(n))
    if shift > 0:                       # t13, lumbar_rib: the body at t is thoracic by the ribs
        out[t] = None
        for p in range(t + 1, n):
            out[p] = p - 1
    elif shift < 0:                     # no_rib_t12: the body at t is lumbar by the ribs
        for p in range(t, n):
            out[p] = p + 1
    return out


# ---- features --------------------------------------------------------------------------------

def external_constant(ref, measures: Sequence[str]) -> Dict[str, float]:
    """One fixed constant per measure: the geometric mean of its published means over the column.
    Dividing by it removes nothing a patient carries; it only centres the logs, which keeps the
    standardisation well conditioned and carries no position."""
    return {m: float(np.exp(np.mean([math.log(ref[m][lv][0]) for lv in P.LEVELS]))) for m in measures}


def feature_names(arm: str, measures: Sequence[str]) -> List[str]:
    return ["log %s(%+d)" % (m, d) for d in ARMS[arm] for m in measures]


def eligible(n: int, arm: str) -> List[int]:
    """The targets whose visible neighbours all exist in a column of n bodies."""
    offs = ARMS[arm]
    return [i for i in range(n) if all(0 <= i + d < n for d in offs)]


def normaliser(values: Dict[str, np.ndarray], i: int, measures: Sequence[str], norm, constant) -> Dict[str, float]:
    """What each measure is divided by at target i: the external constant, or the median of the
    bodies within k of i (the target itself withheld), clipped at the column's ends, so that a
    window at the end of the column normalises by fewer bodies -- which is the leak the side arm
    measures."""
    if norm == "external":
        return constant
    kind, k = norm
    n = len(values[measures[0]])
    if k == "all":
        idx = [j for j in range(n) if j != i]
    else:
        idx = [j for j in range(max(0, i - k), min(n, i + k + 1)) if j != i]
    return {m: float(np.median(values[m][idx])) for m in measures}


def features(values: Dict[str, np.ndarray], i: int, arm: str, measures: Sequence[str],
             norm="external", constant: Optional[Dict[str, float]] = None) -> List[float]:
    """The feature vector of target i: the log of each visible neighbour's measures over the
    normaliser. The index i is used to look the neighbours up and for nothing else."""
    den = normaliser(values, i, measures, norm, constant)
    return [math.log(values[m][i + d] / den[m]) for d in ARMS[arm] for m in measures]


@dataclass
class Rows:
    """Every eligible target of a set of columns, as a design matrix with its truths."""
    X: np.ndarray
    y: np.ndarray            # the count's ordinal = the position
    rib: np.ndarray          # the rib reading's ordinal, -1 where it has none
    group: np.ndarray        # which column, for grouped folds and clustered errors
    phenotype: np.ndarray
    n_columns: int = 0
    names: List[str] = field(default_factory=list)


def draw_columns(ref, phenotypes: Sequence[str], seed: int, n: int, measures: Sequence[str],
                 r_between: float = 0.0, **synth) -> List[P.Column]:
    rng = np.random.default_rng(seed)
    kw = dict(SYNTH, **synth)
    return [P.synthesize(ref, phenotypes[k % len(phenotypes)], rng, measures=list(measures),
                         r_between=r_between, **kw) for k in range(n)]


def rows_of(columns: Sequence[P.Column], arm: str, measures: Sequence[str], norm="external",
            constant: Optional[Dict[str, float]] = None) -> Rows:
    X, y, rib, grp, ph = [], [], [], [], []
    for g, col in enumerate(columns):
        ro = rib_ordinals(col)
        for i in eligible(len(col), arm):
            X.append(features(col.values, i, arm, measures, norm, constant))
            y.append(i)
            rib.append(-1 if ro[i] is None else ro[i])
            grp.append(g)
            ph.append(col.phenotype)
    return Rows(X=np.asarray(X, float), y=np.asarray(y, int), rib=np.asarray(rib, int),
                group=np.asarray(grp, int), phenotype=np.asarray(ph), n_columns=len(columns),
                names=feature_names(arm, measures))


# ---- solution C: the softmax classifier, border.py's logistic regression over 22 classes --------

def softmax(Z: np.ndarray) -> np.ndarray:
    Z = Z - Z.max(1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(1, keepdims=True)


def fit_softmax(X: np.ndarray, y: np.ndarray, k: int = K, iters: int = 30, l2: float = 1e-3,
                tol: float = 1e-7) -> np.ndarray:
    """Multinomial logistic regression by Newton's method with a backtracking line search.

    W is (p + 1) x (k - 1): the last class is the reference with zero weights, so the Hessian is
    nonsingular once the weights (not the biases) carry an L2 penalty. The Hessian is built as
    blockdiag(A' diag(P_c) A) - B'B with B the row-wise Kronecker product of P and A, which is
    one BLAS product rather than a four-index einsum; 300 parameters, so a solve is nothing.
    """
    n, p = X.shape
    A = np.hstack([X, np.ones((n, 1))])
    Y = np.zeros((n, k))
    Y[np.arange(n), y] = 1.0
    pen = np.r_[np.full(p, l2), 1e-8]            # a hair on the biases for conditioning
    W = np.zeros((p + 1, k - 1))

    def loss_and_probs(W):
        Z = np.hstack([A @ W, np.zeros((n, 1))])
        Z = Z - Z.max(1, keepdims=True)
        logp = Z - np.log(np.exp(Z).sum(1, keepdims=True))
        nll = -float((Y * logp).sum()) / n + 0.5 * float((pen[:, None] * W * W).sum())
        return nll, np.exp(logp)

    loss, Pr = loss_and_probs(W)
    for _ in range(iters):
        R = Pr[:, :-1] - Y[:, :-1]
        G = A.T @ R / n + pen[:, None] * W
        if np.abs(G).max() < tol:
            break
        Pc = Pr[:, :-1]
        # blockdiag part: for each class c, A' diag(P_c) A / n
        blocks = np.einsum("ic,ij,il->cjl", Pc, A, A) / n
        H = np.zeros(((p + 1) * (k - 1), (p + 1) * (k - 1)))
        q = p + 1
        for c in range(k - 1):
            H[c * q:(c + 1) * q, c * q:(c + 1) * q] = blocks[c]
        B = (Pc[:, :, None] * A[:, None, :]).reshape(n, (k - 1) * q)
        H -= B.T @ B / n
        H[np.arange(len(H)), np.arange(len(H))] += np.tile(pen, k - 1)
        # W is laid out (feature, class); the Hessian is laid out class-major, so transpose
        step = np.linalg.solve(H, G.T.reshape(-1)).reshape(k - 1, q).T
        t = 1.0
        while t > 1e-4:
            W_new = W - t * step
            new_loss, new_P = loss_and_probs(W_new)
            if new_loss <= loss - 1e-4 * t * float((G * step).sum()):
                break
            t *= 0.5
        W, loss, Pr = W_new, new_loss, new_P
        if t <= 1e-4:
            break
    return W


@dataclass
class Softmax:
    """Solution C. Standardised features, the fitted weights, the classes it can name."""
    arm: str
    measures: Tuple[str, ...]
    norm: object
    mu: np.ndarray
    sd: np.ndarray
    W: np.ndarray
    n_rows: int = 0
    fit_seconds: float = 0.0

    def probabilities(self, X: np.ndarray) -> np.ndarray:
        A = np.hstack([(X - self.mu) / self.sd, np.ones((len(X), 1))])
        return softmax(np.hstack([A @ self.W, np.zeros((len(X), 1))]))

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.probabilities(X).argmax(1)

    def to_json(self) -> dict:
        return {"arm": self.arm, "measures": list(self.measures), "norm": str(self.norm),
                "mu": self.mu.tolist(), "sd": self.sd.tolist(), "W": self.W.tolist(),
                "n_rows": self.n_rows, "fit_seconds": self.fit_seconds}


def train_softmax(rows: Rows, arm: str, measures: Sequence[str], norm="external", l2: float = 1e-3) -> Softmax:
    t0 = time.perf_counter()
    mu, sd = rows.X.mean(0), rows.X.std(0)
    sd[sd == 0] = 1.0
    # a fit on typical columns names C3 .. L5; one on every phenotype can name L6 too
    W = fit_softmax((rows.X - mu) / sd, rows.y, k=max(K, int(rows.y.max()) + 1), l2=l2)
    return Softmax(arm=arm, measures=tuple(measures), norm=norm, mu=mu, sd=sd, W=W,
                   n_rows=len(rows.y), fit_seconds=time.perf_counter() - t0)


def out_of_fold_softmax(rows: Rows, folds: int = 5, seed: int = 0) -> np.ndarray:
    """border.py's grouped out-of-fold scoring, the groups being columns: every prediction is
    from a fit that never saw its column. A check that the fresh-seed scores below are not an
    artefact of the split, and the estimate a selection inside one seed would use."""
    cols = np.unique(rows.group)
    rng = np.random.default_rng(seed)
    rng.shuffle(cols)
    assign = {c: i % folds for i, c in enumerate(cols)}
    fold = np.array([assign[g] for g in rows.group])
    pred = np.zeros(len(rows.y), int)
    for f in range(folds):
        tr, te = fold != f, fold == f
        mu, sd = rows.X[tr].mean(0), rows.X[tr].std(0)
        sd[sd == 0] = 1.0
        W = fit_softmax((rows.X[tr] - mu) / sd, rows.y[tr], k=max(K, int(rows.y.max()) + 1))
        A = np.hstack([(rows.X[te] - mu) / sd, np.ones((int(te.sum()), 1))])
        pred[te] = np.hstack([A @ W, np.zeros((int(te.sum()), 1))]).argmax(1)
    return pred


# ---- solutions A and the dimensionality curve: linear discriminants ----------------------------

@dataclass
class Discriminant:
    """Fisher's linear discriminant analysis on standardised features: the directions that
    separate the classes, in order of the separation each carries, and a Gaussian classifier
    (shared covariance, equal priors) restricted to the first d of them. d = 1 is solution A,
    the scalar index; d = all is the generative twin of solution C."""
    arm: str
    measures: Tuple[str, ...]
    mu: np.ndarray
    sd: np.ndarray
    classes: np.ndarray          # the class ordinals present in training
    means: np.ndarray            # class means in the whitened space, (n_classes, p)
    directions: np.ndarray       # columns: discriminant directions in the whitened space
    eigenvalues: np.ndarray
    whiten: np.ndarray           # Sw^{-1/2}
    fit_seconds: float = 0.0

    @property
    def n_dims(self) -> int:
        return self.directions.shape[1]

    def project(self, X: np.ndarray, dims: int) -> np.ndarray:
        Z = ((X - self.mu) / self.sd) @ self.whiten
        return Z @ self.directions[:, :dims]

    def predict(self, X: np.ndarray, dims: Optional[int] = None) -> np.ndarray:
        dims = self.n_dims if dims is None else dims
        Zp = self.project(X, dims)
        Mp = self.means @ self.directions[:, :dims]
        d2 = ((Zp[:, None, :] - Mp[None, :, :]) ** 2).sum(2)
        return self.classes[d2.argmin(1)]

    def index_weights(self) -> np.ndarray:
        """The first discriminant as weights on the RAW log-millimetre features: index = w . x + c
        with x the feature vector before standardisation."""
        v = self.whiten @ self.directions[:, 0]
        return v / self.sd

    def index(self, X: np.ndarray) -> np.ndarray:
        return self.project(X, 1)[:, 0]


def train_discriminant(rows: Rows, arm: str, measures: Sequence[str], shrink: float = 1e-3) -> Discriminant:
    t0 = time.perf_counter()
    mu, sd = rows.X.mean(0), rows.X.std(0)
    sd[sd == 0] = 1.0
    X = (rows.X - mu) / sd
    classes = np.unique(rows.y)
    p = X.shape[1]
    means = np.vstack([X[rows.y == c].mean(0) for c in classes])
    Sw = np.zeros((p, p))
    for c, m in zip(classes, means):
        D = X[rows.y == c] - m
        Sw += D.T @ D
    Sw /= max(len(X) - len(classes), 1)
    Sw += shrink * np.eye(p)
    vals, vecs = np.linalg.eigh(Sw)
    whiten = vecs @ np.diag(1.0 / np.sqrt(vals)) @ vecs.T
    Mw = means @ whiten
    grand = Mw.mean(0)
    Sb = (Mw - grand).T @ (Mw - grand) / len(classes)
    ev, V = np.linalg.eigh(Sb)
    order = np.argsort(-ev)
    ev, V = np.maximum(ev[order], 0.0), V[:, order]
    q = min(p, len(classes) - 1)
    return Discriminant(arm=arm, measures=tuple(measures), mu=mu, sd=sd, classes=classes, means=Mw,
                        directions=V[:, :q], eigenvalues=ev[:q], whiten=whiten,
                        fit_seconds=time.perf_counter() - t0)


def monotone_check(disc: Discriminant, rows: Rows) -> dict:
    """Is the scalar index monotone in level? The class means of the index down the column, the
    number of sign changes in their successive differences, Spearman's rank correlation with the
    ordinal, and how far apart neighbouring class means are in units of the within-class SD."""
    idx = disc.index(rows.X)
    cls = [int(c) for c in disc.classes]
    means = np.array([idx[rows.y == c].mean() for c in cls])
    sds = np.array([idx[rows.y == c].std(ddof=1) for c in cls])
    diffs = np.diff(means)
    if means[-1] < means[0]:                 # orient the index to increase down the column
        means, diffs = -means, -diffs
    sign_changes = int(((diffs[1:] > 0) != (diffs[:-1] > 0)).sum())
    rank = np.argsort(np.argsort(means)).astype(float)
    ordinal = np.arange(len(cls), dtype=float)
    spearman = float(np.corrcoef(rank, ordinal)[0, 1])
    within = float(np.sqrt(np.mean(sds ** 2)))
    return {"classes": [COUNT_NAMES[c] for c in cls], "class_means": means.tolist(),
            "class_sds": sds.tolist(), "sign_changes": sign_changes,
            "monotone": sign_changes == 0, "spearman": spearman,
            "step_over_within_sd": (np.abs(diffs) / within).tolist(),
            "min_step_over_within_sd": float(np.abs(diffs).min() / within),
            "flattest_step_between": [COUNT_NAMES[cls[int(np.abs(diffs).argmin())]],
                                      COUNT_NAMES[cls[int(np.abs(diffs).argmin()) + 1]]]}


# ---- solution B: the published-means classifier --------------------------------------------------

@dataclass
class Published:
    """Nothing fitted. For every candidate name of the target, the neighbours' expected log
    measures are the table's at the candidate's neighbouring levels; a column's size is one free
    log-offset shared by every measure, profiled out by weighted least squares; the variance of a
    log measure is (population SD / mean)^2 + (noise / mean)^2, POOLED over the levels for each
    measure, since a spread printed from twelve spines is not trusted level by level and a
    per-level variance would let the classifier prefer the level whose sample happened to be
    tight. The candidate at the smallest profiled Mahalanobis distance is the call, so a column
    drawn at the table's means is named exactly, whatever its size (tests/test_neighbour.py)."""
    arm: str
    measures: Tuple[str, ...]
    classes: np.ndarray
    expect: np.ndarray            # (n_candidates, p) expected log(value / constant)
    var: np.ndarray               # (p,) pooled
    constant: Dict[str, float]

    def scores(self, X: np.ndarray) -> np.ndarray:
        """Half the Mahalanobis distance of each candidate, size profiled out."""
        w = 1.0 / self.var                                  # (p,)
        R = X[:, None, :] - self.expect[None, :, :]         # (n, c, p)
        s_hat = (R * w).sum(2) / w.sum()                    # (n, c): the profiled log-size
        R = R - s_hat[:, :, None]
        return 0.5 * (R * R * w).sum(2)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes[self.scores(X).argmin(1)]

    def probabilities(self, X: np.ndarray) -> np.ndarray:
        return softmax(-self.scores(X))


def build_published(ref, arm: str, measures: Sequence[str], constant: Dict[str, float],
                    noise_mm: float = SYNTH["noise_mm"]) -> Published:
    offs = ARMS[arm]
    pooled = {m: float(np.mean([(ref[m][lv][1] / ref[m][lv][0]) ** 2 + (noise_mm / ref[m][lv][0]) ** 2
                                for lv in P.LEVELS])) for m in measures}
    cands, E = [], []
    for c, name in enumerate(CLASSES):
        if not all(0 <= c + d < K for d in offs):
            continue
        e = []
        for d in offs:
            lv = CLASSES[c + d]
            for m in measures:
                e.append(math.log(ref[m][lv][0] / constant[m]))
        cands.append(c)
        E.append(e)
    var = np.asarray([pooled[m] for d in offs for m in measures], float)
    return Published(arm=arm, measures=tuple(measures), classes=np.asarray(cands, int),
                     expect=np.asarray(E, float), var=var, constant=constant)


# ---- scoring -------------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def clustered_se(hit: np.ndarray, group: np.ndarray) -> float:
    """The standard error of a rate whose rows come in columns: targets of one column share the
    patient's draws, so the binomial error understates it. The per-column rates' SD over the
    square root of the number of columns."""
    cols = np.unique(group)
    rates = np.array([hit[group == g].mean() for g in cols])
    return float(rates.std(ddof=1) / math.sqrt(len(cols))) if len(cols) > 1 else float("nan")


def score(pred: np.ndarray, rows: Rows, mask: Optional[np.ndarray] = None) -> dict:
    """Exact and within-one rates, the signed offsets, the rib-reading rate, per phenotype."""
    out = {}
    sel_all = np.ones(len(rows.y), bool) if mask is None else mask
    for ph in sorted(set(rows.phenotype.tolist()), key=P.PHENOTYPES.index):
        sel = sel_all & (rows.phenotype == ph)
        n = int(sel.sum())
        off = pred[sel] - rows.y[sel]
        hit = off == 0
        rib_sel = sel & (rows.rib >= 0)
        rib_hit = pred[rib_sel] == rows.rib[rib_sel]
        offsets = Counter(int(o) for o in off)
        lo, hi = wilson(int(hit.sum()), n)
        ys = rows.y[sel]
        by_lv = {COUNT_NAMES[int(c)]: float(off[ys == c].mean()) for c in np.unique(ys)}
        out[ph] = {"n": n, "n_columns": int(len(np.unique(rows.group[sel]))),
                   "exact": int(hit.sum()), "exact_rate": float(hit.mean()) if n else float("nan"),
                   "wilson": [lo, hi], "se_cluster": clustered_se(hit.astype(float), rows.group[sel]) if n else float("nan"),
                   "within_one": int((np.abs(off) <= 1).sum()),
                   "within_one_rate": float((np.abs(off) <= 1).mean()) if n else float("nan"),
                   "mean_offset": float(off.mean()) if n else float("nan"),
                   "mean_offset_by_level": by_lv,
                   "offsets": {str(k): v for k, v in sorted(offsets.items())},
                   "n_rib": int(rib_sel.sum()), "exact_rib": int(rib_hit.sum()),
                   "exact_rib_rate": float(rib_hit.mean()) if rib_sel.any() else float("nan")}
    return out


def worst_of(per: dict, key: str = "exact_rate") -> dict:
    ph = min(per, key=lambda p: per[p][key])
    return {"phenotype": ph, key: per[ph][key]}


def by_level(pred: np.ndarray, rows: Rows, phenotype: str = "typical") -> Dict[str, float]:
    sel = rows.phenotype == phenotype
    out = {}
    for c in np.unique(rows.y[sel]):
        m = sel & (rows.y == c)
        out[COUNT_NAMES[int(c)]] = float((pred[m] == c).mean())
    return out


def chance(rows: Rows) -> dict:
    """The marginal the chance rates assume: every eligible target of a typical column, so
    uniform over the levels the arm can see."""
    sel = rows.phenotype == "typical"
    counts = Counter(COUNT_NAMES[int(c)] for c in rows.y[sel])
    n = sum(counts.values())
    k = len(counts)
    # within one under a uniform guess over k names: 3/k inside, less at the two ends
    within = (3 * k - 2) / (k * k) if k else float("nan")
    return {"marginal": {name: counts[name] for name in COUNT_NAMES if name in counts},
            "k_names": k, "uniform_exact": 1.0 / k if k else float("nan"),
            "uniform_within_one": within,
            "majority_exact": max(counts.values()) / n if n else float("nan")}


# ---- the pieces of the study -------------------------------------------------------------------

def shuffle_invariance(ref, arm: str, measures: Sequence[str], model, norm="external",
                       constant=None, seed: int = 5, trials: int = 50) -> dict:
    """The position-leak test the brief asks for, run on the fitted model and recorded: the same
    neighbourhood (the visible neighbours and, for a median arm, its normalisation set) placed
    at another position of a column whose other bodies are shuffled must give the same features
    and the same call, bit for bit."""
    rng = np.random.default_rng(seed)
    offs = ARMS[arm]
    reach = max(abs(d) for d in offs)
    if norm != "external" and norm[1] != "all":
        reach = max(reach, int(norm[1]))
    same = 0
    for _ in range(trials):
        col = P.synthesize(ref, "typical", rng, measures=list(measures), **SYNTH)
        n = len(col)
        i = int(rng.integers(reach, n - reach))
        f0 = features(col.values, i, arm, measures, norm, constant)
        p0 = model.predict(np.asarray([f0]))[0]
        # move the neighbourhood: the bodies outside it are shuffled and the block is placed
        # at a new position by rotating the column
        block = list(range(i - reach, i + reach + 1))
        others = [j for j in range(n) if j not in block]
        rng.shuffle(others)
        split = int(rng.integers(0, len(others) + 1))
        order = others[:split] + block + others[split:]
        new_i = split + reach
        values = {m: col.values[m][order] for m in measures}
        if norm != "external" and norm[1] == "all":
            values = {m: col.values[m][order] for m in measures}   # the same multiset: same median
        f1 = features(values, new_i, arm, measures, norm, constant)
        p1 = model.predict(np.asarray([f1]))[0]
        same += int(np.allclose(f0, f1) and p0 == p1)
    return {"trials": trials, "identical": same, "arm": arm, "norm": str(norm)}


def selective(prob: np.ndarray, pred: np.ndarray, rows: Rows, thresholds: Sequence[float]) -> dict:
    """Accuracy against coverage when the model abstains below a confidence (the largest
    class probability), per phenotype, at the thresholds given."""
    conf = prob.max(1)
    out = {}
    for ph in P.PHENOTYPES:
        sel = rows.phenotype == ph
        if not sel.any():
            continue
        cov, acc, within = [], [], []
        for t in thresholds:
            called = sel & (conf >= t)
            cov.append(float(called.sum() / sel.sum()))
            if called.any():
                off = pred[called] - rows.y[called]
                acc.append(float((off == 0).mean()))
                within.append(float((np.abs(off) <= 1).mean()))
            else:
                acc.append(float("nan"))
                within.append(float("nan"))
        out[ph] = {"coverage": cov, "exact_rate": acc, "within_one_rate": within}
    return out


def thresholds_for_coverage(prob: np.ndarray, rows: Rows, coverages: Sequence[float]) -> Dict[str, float]:
    """The confidence threshold that keeps each coverage on the SELECTION columns, typical and
    anomalous alike, so the thresholds are chosen on one seed and scored on another."""
    conf = np.sort(prob.max(1))
    out = {}
    for c in coverages:
        k = int(math.floor((1.0 - c) * len(conf)))
        out[str(c)] = float(conf[min(k, len(conf) - 1)])
    return out


def latency(ref, model: Softmax, disc: Discriminant, pub: Published, arm: str, measures,
            constant, repeats: int = 2000) -> dict:
    """What one call costs, as a surgeon's window would pay it: one target, features and the
    call, timed one at a time; and the batch throughput."""
    rng = np.random.default_rng(1)
    col = P.synthesize(ref, "typical", rng, measures=list(measures), **SYNTH)
    i = eligible(len(col), arm)[len(col) // 2]
    out = {}
    for name, m in (("C_softmax", model), ("A_scalar_index", disc), ("B_published", pub)):
        t0 = time.perf_counter()
        for _ in range(repeats):
            f = features(col.values, i, arm, measures, "external", constant)
            if name == "A_scalar_index":
                m.predict(np.asarray([f]), dims=1)
            else:
                m.predict(np.asarray([f]))
        out[name + "_ms_per_window"] = 1000.0 * (time.perf_counter() - t0) / repeats
    t0 = time.perf_counter()
    for _ in range(200):
        P.synthesize(ref, "typical", rng, measures=list(measures), **SYNTH)
    out["synthesize_ms_per_column"] = 1000.0 * (time.perf_counter() - t0) / 200
    return out


def fit_cost(ref, arm: str, measures, constant, sizes=(120, 300, 600)) -> List[dict]:
    out = []
    for n in sizes:
        cols = draw_columns(ref, ("typical",), FIT_SEED, n, measures)
        rows = rows_of(cols, arm, measures, "external", constant)
        m = train_softmax(rows, arm, measures)
        d = train_discriminant(rows, arm, measures)
        out.append({"n_columns": n, "n_rows": len(rows.y), "softmax_seconds": m.fit_seconds,
                    "discriminant_seconds": d.fit_seconds})
    return out


# ---- the study -------------------------------------------------------------------------------

def _cell(ref, arm, regime, measures, fit_cols, sel_cols, sco_cols, constant, norm="external",
          want_dims=False, want_selective=False, want_oof=False):
    """One arm x regime: fit on the fit columns, choose on the selection columns, score on the
    scoring columns, for solutions A, B and C."""
    fit = rows_of(fit_cols, arm, measures, norm, constant)
    sco = rows_of(sco_cols, arm, measures, norm, constant)
    model = train_softmax(fit, arm, measures, norm)
    disc = train_discriminant(fit, arm, measures)
    cell = {"arm": arm, "regime": regime, "measures": list(measures), "norm": str(norm),
            "n_fit_rows": len(fit.y), "n_score_rows": len(sco.y), "solutions": {}}
    prob = model.probabilities(sco.X)
    pred_c = prob.argmax(1)
    cell["solutions"]["C"] = {"per_phenotype": score(pred_c, sco), "fit_seconds": model.fit_seconds,
                              "by_level_typical": by_level(pred_c, sco)}
    pred_a = disc.predict(sco.X, dims=1)
    cell["solutions"]["A"] = {"per_phenotype": score(pred_a, sco), "fit_seconds": disc.fit_seconds,
                              "by_level_typical": by_level(pred_a, sco)}
    pred_full = disc.predict(sco.X)
    cell["solutions"]["LDA_full"] = {"per_phenotype": score(pred_full, sco),
                                     "by_level_typical": by_level(pred_full, sco)}
    if norm == "external":
        pub = build_published(ref, arm, measures, constant)
        pred_b = pub.predict(sco.X)
        cell["solutions"]["B"] = {"per_phenotype": score(pred_b, sco), "fit_seconds": 0.0,
                                  "by_level_typical": by_level(pred_b, sco),
                                  "agreement_with_C": float((pred_b == pred_c).mean())}
    for s in cell["solutions"].values():
        s["worst"] = worst_of(s["per_phenotype"])
        s["worst_within_one"] = worst_of(s["per_phenotype"], "within_one_rate")
    cell["formula"] = {"weights": dict(zip(fit.names, disc.index_weights().tolist())),
                       "eigenvalues": disc.eigenvalues.tolist(),
                       "share": (disc.eigenvalues / max(disc.eigenvalues.sum(), EPS)).tolist(),
                       "check": monotone_check(disc, sco)}
    if want_dims:
        acc = {}
        for d in range(1, disc.n_dims + 1):
            pr = disc.predict(sco.X, dims=d)
            per = score(pr, sco)
            acc[str(d)] = {ph: per[ph]["exact_rate"] for ph in per}
            acc[str(d)]["worst"] = worst_of(per)["exact_rate"]
        cell["dimensionality"] = {"n_dims": disc.n_dims, "exact_by_dims": acc}
    if want_selective:
        sel = rows_of(sel_cols, arm, measures, norm, constant)
        thr = thresholds_for_coverage(model.probabilities(sel.X), sel, COVERAGES)
        grid = [float(x) for x in np.linspace(0.0, 1.0, 41)]
        cell["selective"] = {"thresholds_from_selection_seed": thr,
                             "grid": grid, "curve": selective(prob, pred_c, sco, grid),
                             "at_coverage": {c: {"threshold": thr[str(c)],
                                                 "per_phenotype": selective(prob, pred_c, sco, [thr[str(c)]])}
                                             for c in COVERAGES}}
    if want_oof:
        oof = out_of_fold_softmax(fit)
        cell["oof_typical_exact_rate"] = float((oof == fit.y).mean())
    cell["shuffle"] = shuffle_invariance(ref, arm, measures, model, norm, constant)
    return cell, model, disc, (pub if norm == "external" else None)


def run(outdir: Optional[str] = None, n_fit: int = N_FIT, n_select: int = N_SELECT, n_score: int = N_SCORE,
        r_grid: Optional[Sequence[float]] = None, quick: bool = False) -> dict:
    """The whole study but the enumeration, which has its own command. Prints as it goes."""
    t_start = time.perf_counter()
    measures7 = list(CV.SPINEPS_7)
    ref = P.load_reference(measures=measures7)
    constant = external_constant(ref, measures7)
    arms = list(ARMS)
    regimes = list(REGIMES)
    if quick:
        n_fit, n_select, n_score = min(n_fit, 60), min(n_select, 30), min(n_score, 40)
    fit_cols = draw_columns(ref, ("typical",), FIT_SEED, n_fit, measures7)
    sel_cols = draw_columns(ref, P.PHENOTYPES, SELECT_SEED, n_select * len(P.PHENOTYPES), measures7)
    sco_cols = draw_columns(ref, P.PHENOTYPES, SCORE_SEED, n_score * len(P.PHENOTYPES), measures7)
    rec = {"study": "neighbour-identity", "synth": dict(SYNTH, r_between=0.0),
           "seeds": {"fit": FIT_SEED, "select": SELECT_SEED, "score": SCORE_SEED},
           "n_columns": {"fit_typical": n_fit, "select_per_phenotype": n_select, "score_per_phenotype": n_score},
           "arms": {a: list(o) for a, o in ARMS.items()}, "regimes": REGIMES, "classes": CLASSES,
           "external_constant": constant, "chance": {}, "cells": [], "normalisation": [],
           "r_sweep": {}, "latency": {}, "python": sys.version.split()[0], "numpy": np.__version__}
    print("neighbour-identity study: %d fit columns, %d selection and %d scoring columns per phenotype"
          % (n_fit, n_select, n_score))
    keep = {}
    for arm in arms:
        rec["chance"][arm] = chance(rows_of(sco_cols, arm, measures7, "external", constant))
        for regime in regimes:
            main = (arm == "flank")
            cell, model, disc, pub = _cell(ref, arm, regime, REGIMES[regime], fit_cols, sel_cols, sco_cols,
                                           constant, want_dims=True, want_selective=main, want_oof=main)
            rec["cells"].append(cell)
            keep[(arm, regime)] = (model, disc, pub)
            c = cell["solutions"]["C"]
            print("  %-12s %-8s C exact typical %.3f worst %.3f (%s)  A %.3f  B %.3f  shuffle %d/%d  %.1fs"
                  % (arm, regime, c["per_phenotype"]["typical"]["exact_rate"], c["worst"]["exact_rate"],
                     c["worst"]["phenotype"], cell["solutions"]["A"]["worst"]["exact_rate"],
                     cell["solutions"]["B"]["worst"]["exact_rate"], cell["shuffle"]["identical"],
                     cell["shuffle"]["trials"], c["fit_seconds"]))
    # the obvious objection: fit on the anomalies too. The count's name of a shape is then
    # ambiguous by construction (an L1-shaped body is L1 in a typical column and L2 below a T13),
    # so this cell says what a fit can do about the shift, not what the shape can
    mixed_cols = draw_columns(ref, P.PHENOTYPES, FIT_SEED, n_fit, measures7)
    cell, _, _, _ = _cell(ref, "flank", "both", measures7, mixed_cols, sel_cols, sco_cols, constant)
    cell["fitted_on"] = "all six phenotypes, %d columns" % n_fit
    rec["mixed_fit"] = cell
    c = cell["solutions"]["C"]
    print("  fitted on every phenotype: C exact typical %.3f worst %.3f (%s)"
          % (c["per_phenotype"]["typical"]["exact_rate"], c["worst"]["exact_rate"], c["worst"]["phenotype"]))
    # the normalisation leak: flank, both, C, the median over 2 .. all bodies against the constant
    for k in MEDIAN_BODIES:
        norm = ("median", k)
        cell, _, _, _ = _cell(ref, "flank", "both", measures7, fit_cols, sel_cols, sco_cols, constant, norm=norm)
        bodies = "all" if k == "all" else 2 * k
        c = cell["solutions"]["C"]
        rec["normalisation"].append({"norm": str(norm), "bodies": bodies, "solutions": cell["solutions"],
                                     "shuffle": cell["shuffle"]})
        print("  median over %-4s bodies: C exact typical %.3f worst %.3f"
              % (bodies, c["per_phenotype"]["typical"]["exact_rate"], c["worst"]["exact_rate"]))
    # the r sweep: flank, three regimes, solution C; the main table is r = 0
    grid = list(CV.R_GRID) if r_grid is None else list(r_grid)
    if quick:
        grid = grid[:3]
    for regime in regimes:
        rows_r = []
        for r in grid:
            fc = draw_columns(ref, ("typical",), FIT_SEED, n_fit, measures7, r_between=r)
            sc = draw_columns(ref, P.PHENOTYPES, SCORE_SEED, n_score * len(P.PHENOTYPES), measures7, r_between=r)
            fit = rows_of(fc, "flank", REGIMES[regime], "external", constant)
            sco = rows_of(sc, "flank", REGIMES[regime], "external", constant)
            m = train_softmax(fit, "flank", REGIMES[regime])
            pred = m.predict(sco.X)
            per = score(pred, sco)
            hit = (pred == sco.y).astype(float)
            rows_r.append({"r": r, "acc": float(hit.mean()), "se": clustered_se(hit, sco.group),
                           "se_binomial": CV.binomial_se(float(hit.mean()), len(hit)), "n": len(hit),
                           "worst": worst_of(per), "per_phenotype": {ph: per[ph]["exact_rate"] for ph in per}})
        rec["r_sweep"][regime] = rows_r
        print("  r sweep %-8s %s" % (regime, " ".join("%.3f" % x["acc"] for x in rows_r)))
    rec["identified"] = {regime: CV.identified_set(rec["r_sweep"][regime]) for regime in regimes}
    rec["profile_in_r"] = {regime: CV.profile_in_r(rec["r_sweep"][regime]) for regime in regimes}
    rec["sign"] = {}
    for a, b in (("both", "lateral"), ("both", "ap"), ("ap", "lateral")):
        v = CV.sign_invariance(rec["r_sweep"][a], rec["r_sweep"][b])
        rec["sign"]["%s_minus_%s" % (a, b)] = v
    # latency, on this machine
    model, disc, pub = keep[("flank", "both")]
    rec["latency"] = latency(ref, model, disc, pub, "flank", measures7, constant)
    rec["latency"]["fit_cost"] = fit_cost(ref, "flank", measures7, constant)
    rec["latency"]["machine"] = {"platform": sys.platform, "cpus": os.cpu_count()}
    rec["seconds_total"] = time.perf_counter() - t_start
    rec["latency"]["study_seconds"] = rec["seconds_total"]
    print("  latency: C %.3f ms/window, A %.3f, B %.3f; study %.0f s"
          % (rec["latency"]["C_softmax_ms_per_window"], rec["latency"]["A_scalar_index_ms_per_window"],
             rec["latency"]["B_published_ms_per_window"], rec["seconds_total"]))
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "neighbour.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1, sort_keys=True, default=_jsonable)
            fh.write("\n")
        with open(os.path.join(outdir, "models.json"), "w", encoding="utf-8") as fh:
            json.dump({"%s/%s" % k: v[0].to_json() for k, v in keep.items()}, fh, sort_keys=True)
            fh.write("\n")
        print("wrote %s" % path)
    return rec


def _jsonable(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


# ---- solution D: exhaustive enumeration of the measure subsets -----------------------------------

def enumerate_subsets(arm: str = "flank", measures=None, shard: int = 0, n_shards: int = 1,
                      n_fit: int = N_FIT, n_select: int = N_SELECT, n_score: int = N_SCORE,
                      out_json: Optional[str] = None, quick: bool = False) -> dict:
    """Every subset of the seven measures, solution C on the arm, fitted on FIT_SEED, chosen on
    SELECT_SEED (the worst phenotype's exact rate) and scored on SCORE_SEED; sharded so a Slurm
    array splits the 127 subsets, gathered by gather_subsets."""
    measures = list(measures or CV.SPINEPS_7)
    ref = P.load_reference(measures=measures)
    constant = external_constant(ref, measures)
    if quick:
        n_fit, n_select, n_score = min(n_fit, 60), min(n_select, 30), min(n_score, 40)
    subsets = CV.subsets_of(measures, 1)
    mine = [s for k, s in enumerate(subsets) if k % n_shards == shard]
    fit_cols = draw_columns(ref, ("typical",), FIT_SEED, n_fit, measures)
    sel_cols = draw_columns(ref, P.PHENOTYPES, SELECT_SEED, n_select * len(P.PHENOTYPES), measures)
    sco_cols = draw_columns(ref, P.PHENOTYPES, SCORE_SEED, n_score * len(P.PHENOTYPES), measures)
    rows = []
    t0 = time.perf_counter()
    for sub in mine:
        fit = rows_of(fit_cols, arm, sub, "external", constant)
        sel = rows_of(sel_cols, arm, sub, "external", constant)
        sco = rows_of(sco_cols, arm, sub, "external", constant)
        m = train_softmax(fit, arm, sub)
        per_sel = score(m.predict(sel.X), sel)
        per_sco = score(m.predict(sco.X), sco)
        rows.append({"measures": list(sub), "k": len(sub),
                     "select": {ph: per_sel[ph]["exact_rate"] for ph in per_sel},
                     "select_worst": worst_of(per_sel),
                     "score": {ph: per_sco[ph]["exact_rate"] for ph in per_sco},
                     "score_worst": worst_of(per_sco),
                     "score_se": {ph: per_sco[ph]["se_cluster"] for ph in per_sco},
                     "score_offsets": {ph: per_sco[ph]["offsets"] for ph in per_sco},
                     "fit_seconds": m.fit_seconds})
        print("  %-60s select worst %.3f  score worst %.3f  (%.1fs)"
              % (",".join(sub), rows[-1]["select_worst"]["exact_rate"],
                 rows[-1]["score_worst"]["exact_rate"], m.fit_seconds))
    d = {"arm": arm, "ground_set": measures, "n_subsets_total": len(subsets), "shard": shard,
         "n_shards": n_shards, "seeds": {"fit": FIT_SEED, "select": SELECT_SEED, "score": SCORE_SEED},
         "n_columns": {"fit_typical": n_fit, "select_per_phenotype": n_select, "score_per_phenotype": n_score},
         "rows": rows, "seconds": time.perf_counter() - t0}
    if out_json:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("wrote %s" % out_json)
    return d


def gather_subsets(paths: Sequence[str], out_json: Optional[str] = None) -> dict:
    """Merge the shards; rank by the selection seed's worst phenotype; report the scoring seed's
    numbers of the top subsets, the regimes' subsets and the full set, so the chosen subset's
    reported accuracy was not the number it was chosen by."""
    rows, total, ground, arm, shards = [], None, None, None, []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        rows.extend(d["rows"])
        total, ground, arm = d["n_subsets_total"], d["ground_set"], d["arm"]
        shards.append(d["shard"])
    seen = {tuple(x["measures"]) for x in rows}
    complete = len(seen) == total
    ranked = sorted(rows, key=lambda x: (-x["select_worst"]["exact_rate"], x["k"]))
    out = {"arm": arm, "ground_set": ground, "n_subsets_total": total, "n_subsets_present": len(seen),
           "complete": complete, "shards": sorted(shards), "ranked_by_selection": ranked[:10],
           "named": {}}
    for name, ms in list(REGIMES.items()):
        for x in rows:
            if sorted(x["measures"]) == sorted(ms):
                out["named"][name] = x
    out["all_rows"] = [{"measures": x["measures"], "k": x["k"], "select_worst": x["select_worst"],
                        "score_worst": x["score_worst"], "score": x["score"], "score_se": x["score_se"]}
                       for x in ranked]
    best = ranked[0]
    out["winner"] = best
    out["winner_scored"] = best["score_worst"]
    # does a superset ever score worse than its subset, beyond the clustered error? (A is not
    # monotone in S in the junction enumeration; it need not be here either)
    by = {frozenset(x["measures"]): x for x in rows}
    drops = []
    for s, x in by.items():
        for m in ground:
            if m in s:
                continue
            y = by.get(s | {m})
            if y is None:
                continue
            d = y["score_worst"]["exact_rate"] - x["score_worst"]["exact_rate"]
            se = math.hypot(y["score_se"][y["score_worst"]["phenotype"]], x["score_se"][x["score_worst"]["phenotype"]])
            if d < -2 * se:
                drops.append({"subset": sorted(s), "added": m, "drop": d, "se": se})
    out["supersets_worse_by_2se"] = sorted(drops, key=lambda z: z["drop"])[:20]
    out["n_supersets_worse_by_2se"] = len(drops)
    print("gathered %d shards, %d of %d subsets%s" % (len(paths), len(seen), total, "" if complete else "  INCOMPLETE"))
    print("  top 5 by the SELECTION seed's worst phenotype, with the SCORING seed's numbers beside:")
    for x in ranked[:5]:
        print("    select %.3f  score %.3f (%s)  k=%d  %s"
              % (x["select_worst"]["exact_rate"], x["score_worst"]["exact_rate"],
                 x["score_worst"]["phenotype"], x["k"], ",".join(x["measures"])))
    for name, x in out["named"].items():
        print("  %-8s select %.3f  score %.3f (%s)" % (name, x["select_worst"]["exact_rate"],
                                                         x["score_worst"]["exact_rate"], x["score_worst"]["phenotype"]))
    print("  supersets scoring worse than a subset by more than 2 s.e.: %d" % len(drops))
    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print("wrote %s" % out_json)
    return out
