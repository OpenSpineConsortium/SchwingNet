"""The QA loop's gates and its controller, in numpy alone (docs/research/qa-loop/PREREG.md).

The QA loop (flows/qaloop.py) trains the auto-anatomist round after round and, after each round,
asks six questions of what it has; it stops when every answer is yes, when a question cannot be
asked for want of data, or when its rounds run out. This module answers the questions from arrays
and decides the next round; tools/qaloop_round.py makes the arrays (it trains, reads the network
and projects the landmarks) and the flow calls controller() between rounds. Nothing here imports
JAX, so the gates are tested on any machine and the flow's own interpreter runs the controller.

The questions, each a gate with its bars in the plan (grid/qaloop/<plan>.json):

- convergence: the training loss has stopped falling (its mean over the last window within
  rel_tol of the window before) and the held-out reading is not rising (no worse than the best
  round's by more than rise_tol);
- anomaly: every anomaly class the plan names is decoded (the network's mask of the class's crops
  reaches the Dice bar from the CT alone) and encoded (the name head names the crop's level, and
  a nearest-class-mean probe on the latent alone recovers the class);
- fingerprint: a set of landmarks, chosen by a greedy search from the 18 the oracle names, whose
  2-D projections name the levels of a visible run of k bodies, in every column type, as a C-arm
  sees them (anteroposterior and lateral, the poses drawn about each), with a Wilson lower bound
  at or above the bar and a median margin, the log odds of the right names against the best wrong
  ones, at or above log(9);
- presence: on real paired frames (C-ArmLSpine: each case's CBCT with its spot frames and their
  registered poses), the fingerprint's landmarks, taken from the CBCT's masks and projected through
  the frame's pose, sit on stronger edges of the real image than points drawn inside the same
  bodies do;
- real naming: the same fingerprint, measured on the real CBCTs and projected through the real
  poses, names the real lumbar levels of held-out persons;
- latency: the 2-D naming path's seconds per frame, p95 within the 97 ms budget, on the node's CPU
  (the naming path only: no landmark detector exists yet, so this is no latency number of a
  network, which the latency flow's ONNX parity rule governs).

The landmarks are named as the oracle names its points (autoanatomist/specs.py, landmarks), so the
exact phantom landmarks and the oracle's on a real mask are the same eighteen.
"""

import hashlib
import math
import time

import numpy as np

LANDMARKS = (
    "endplate.right", "endplate.left", "endplate_depth.posterior", "endplate_depth.anterior",
    "endplate_lower.right", "endplate_lower.left", "endplate_lower_depth.posterior", "endplate_lower_depth.anterior",
    "h_post.superior", "h_post.inferior", "canal_w.right", "canal_w.left", "canal_ap.posterior", "canal_ap.anterior",
    "tp_span.right", "tp_span.left", "spinous_length.canal", "spinous_length.tip",
)
INDEX = {name: i for i, name in enumerate(LANDMARKS)}
VIEWS = ("ap", "lat")
ANCHORS = ("bottom", "none")
# The column types a run is named under and their prior weights: autoanatomist/naming.py's TYPES and
# WEIGHTS (chain.py's, with four_lumbar at 0.05), stated here so the gates import no JAX.
TYPE_WEIGHTS = {"typical": 0.9, "six_lumbar": 0.05, "four_lumbar": 0.05, "t13": 0.05}
# Phenotypes that name their levels as a typical column does: their difference is a rib, not a level.
NAMED_AS = {"typical": "typical", "lumbar_rib": "typical", "no_rib_t12": "typical", "six_lumbar": "six_lumbar",
            "four_lumbar": "four_lumbar", "t13": "t13"}
UNIQUE_MARGIN = math.log(9.0)      # posterior odds of 9 to 1 for the names given: the margin a unique fingerprint shows
SHRINK = 0.2                       # the pooled covariance's shrinkage toward its diagonal
FLOOR = 1e-6                       # a variance's floor, so a feature constant in the data never divides by zero
Z95 = 1.959964


def wilson(hits, n, z=Z95):
    """The Wilson score interval of hits in n, (low, high); (0, 1) where n is 0."""
    if n <= 0:
        return 0.0, 1.0
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


# ---------------------------------------------------------------- projection

def projection_matrix(K, R, t):
    """P = K [R | t], world millimetres to pixels."""
    return np.asarray(K, float) @ np.hstack([np.asarray(R, float), np.asarray(t, float).reshape(3, 1)])


def project(P, points):
    """Points (..., 3) in world millimetres to pixels (..., 2) through P; NaN where a point is NaN or
    behind the source."""
    X = np.asarray(points, float)
    h = X @ P[:, :3].T + P[:, 3]
    w = h[..., 2:3]
    with np.errstate(invalid="ignore", divide="ignore"):
        uv = h[..., :2] / w
    return np.where(w > 0, uv, np.nan)


def rotation(axis, degrees):
    """The rotation by degrees about a unit axis (Rodrigues)."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    th = math.radians(degrees)
    k = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(th) * k + (1 - math.cos(th)) * (k @ k)


def carm_camera(centre, ex, ey, ez, view, yaw=0.0, tilt=0.0, roll=0.0, sod=650.0, sdd=1140.0, pixel_mm=0.6, size=512):
    """A C-arm's K, R and t looking at `centre` along the column's frame (ex right, ey anterior, ez
    up): the anteroposterior view's beam runs from in front of the column to behind it, the lateral
    view's from its right to its left; yaw turns the beam about the column's axis (an oblique view),
    tilt about its left-right axis (a cranio-caudal tilt) and roll the image about the beam. The
    source is sod from the centre, the detector sdd from the source, pixel_mm a pixel and size the
    frame's width and height in pixels; image rows run down the column, as a C-arm's frame is shown."""
    ex, ey, ez = (np.asarray(v, float) for v in (ex, ey, ez))
    beam = -ey if view == "ap" else -ex
    turn = rotation(ez, yaw) @ rotation(ex if view == "ap" else ey, tilt)
    beam = turn @ beam
    down = turn @ (-ez)
    down = down - beam * (down @ beam)
    down = down / np.linalg.norm(down)
    across = np.cross(down, beam)
    c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    across, down = c * across + s * down, -s * across + c * down
    R = np.vstack([across, down, beam])              # rows: the camera's x, y and z in world coordinates
    source = np.asarray(centre, float) - sod * beam
    f = sdd / pixel_mm
    K = np.array([[f, 0.0, size / 2.0], [0.0, f, size / 2.0], [0.0, 0.0, 1.0]])
    return K, R, -R @ source


# ---------------------------------------------------------------- runs

RUN_FIELDS = ("view", "anchor", "type", "person")


def pack(samples):
    """Runs grouped by their length into arrays, so a run of k bodies is named with every other run
    of k at once: k maps to points (n, k, 18, 2) in pixels, top body first, names (n, k), and each
    run's view, anchor, type (its phenotype), named_as (the column it is named under) and person.
    samples is a list of dicts with those fields and points (k, 18, 2)."""
    by_k = {}
    for s in samples:
        by_k.setdefault(len(s["names"]), []).append(s)
    packs = {}
    for k, runs in sorted(by_k.items()):
        p = {"points": np.asarray([r["points"] for r in runs], float).reshape(len(runs), k, len(LANDMARKS), 2),
             "names": np.asarray([[str(x) for x in r["names"]] for r in runs], dtype=str).reshape(len(runs), k)}
        for field in RUN_FIELDS:
            p[field] = np.asarray([str(r[field]) for r in runs], dtype=str)
        p["named_as"] = np.asarray([NAMED_AS[t] for t in p["type"]], dtype=str)
        packs[k] = p
    return packs


def subset(packs, masks):
    """The packs cut to the rows each mask keeps; a length whose mask keeps nothing is left out."""
    return {k: {f: v[masks[k]] for f, v in p.items()} for k, p in packs.items() if masks[k].any()}


def merge(*sets):
    """Packs joined length by length, the rows of the first set first."""
    out = {}
    for packs in sets:
        for k, p in packs.items():
            out[k] = p if k not in out else {f: np.concatenate([out[k][f], v]) for f, v in p.items()}
    return out


def count(packs):
    return int(sum(len(p["person"]) for p in packs.values()))


def where(packs, field, test):
    """A mask per length keeping the rows whose field passes test, a function of the field's array."""
    return {k: np.asarray(test(p[field]), bool) for k, p in packs.items()}


# ---------------------------------------------------------------- features

def batch_features(points, chosen):
    """Runs' features from their bodies' projected landmarks: points (n, k, 18, 2) in pixels, top
    body first, chosen the landmarks' indices (two or more). Each body gives its chosen points about
    their centroid, turned so the run runs down the image's y (the axis from its first body's
    centroid to its last's) and divided by the run's scale (the mean over its bodies of the chosen
    points' RMS distance from their centroid), the log of its own scale over the run's, and its
    centroid's distance to the next body's (the last body's to the one above) in the run's scale;
    (n, k, 2 len(chosen) + 2). The features do not change when the frame is turned, moved or
    magnified, so the C-arm's roll and distance leave them alone. A run with a missing point, or
    with no extent, is NaN throughout."""
    P = np.asarray(points, float)[:, :, list(chosen), :]
    n, k, m, _ = P.shape
    c = P.mean(axis=2)
    down = np.tile([0.0, 1.0], (n, 1))
    if k > 1:
        d = c[:, -1] - c[:, 0]
        length = np.linalg.norm(d, axis=1, keepdims=True)
        ok = np.isfinite(length[:, 0]) & (length[:, 0] > 0)
        down[ok] = d[ok] / length[ok]
    across = np.stack([down[:, 1], -down[:, 0]], axis=1)
    turn = np.stack([across, down], axis=1)                        # (n, 2, 2): the rows across and down
    local = np.einsum("nkmj,nij->nkmi", P - c[:, :, None, :], turn)
    scale = np.sqrt(np.mean(np.sum(local ** 2, axis=3), axis=2))   # (n, k)
    s_run = scale.mean(axis=1)
    bad = ~np.isfinite(s_run) | ~(s_run > 0)
    s_run = np.where(bad, 1.0, s_run)
    if k > 1:
        gaps = np.linalg.norm(np.diff(c, axis=1), axis=2) / s_run[:, None]
        gap = np.concatenate([gaps, gaps[:, -1:]], axis=1)
    else:
        gap = np.zeros((n, 1))
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.log(scale / s_run[:, None])
    feats = np.concatenate([local.reshape(n, k, 2 * m) / s_run[:, None, None], rel[..., None], gap[..., None]], axis=2)
    feats[bad] = np.nan
    return feats


def run_features(points, chosen):
    """One run's features, points (k, 18, 2): batch_features of a batch of one."""
    return batch_features(np.asarray(points, float)[None], chosen)[0]


def features_of(packs, chosen):
    return {k: batch_features(p["points"], chosen) for k, p in packs.items()}


def whole_runs(feats):
    """The runs every feature of which is a number."""
    return np.all(np.isfinite(feats), axis=(1, 2))


# ---------------------------------------------------------------- the naming model

class NameModel:
    """A Gaussian model of a body's features per (column type, level name) and view, with one
    covariance per view pooled over the classes and shrunk toward its diagonal (linear discriminant
    analysis): what a name looks like in 2-D, fit on the selection persons alone."""

    def __init__(self):
        self.means = {}
        self.inv = {}
        self.dims = 0

    def fit(self, packs, feats, masks=None):
        X, V, C = [], [], []
        for k, p in packs.items():
            f = feats[k]
            keep = whole_runs(f) if masks is None else whole_runs(f) & masks[k]
            if not keep.any():
                continue
            X.append(f[keep].reshape(-1, f.shape[2]))
            V.append(np.repeat(p["view"][keep], k))
            C.append(np.char.add(np.char.add(np.repeat(p["named_as"][keep], k), "|"), p["names"][keep].reshape(-1)))
        if not X:
            return self
        X, V, C = np.concatenate(X), np.concatenate(V), np.concatenate(C)
        self.dims = X.shape[1]
        for view in np.unique(V):
            self.fit_view(str(view), X[V == view], C[V == view])
        return self

    def fit_view(self, view, X, C):
        labels, inverse, counts = np.unique(C, return_inverse=True, return_counts=True)
        inverse = inverse.reshape(-1)
        order = np.argsort(inverse, kind="stable")
        starts = np.concatenate([[0], np.cumsum(counts)[:-1]])
        means = np.add.reduceat(X[order], starts, axis=0) / counts[:, None]
        Z = X - means[inverse]
        cov = Z.T @ Z / max(len(Z) - len(labels), 1)
        cov = (1 - SHRINK) * cov + SHRINK * np.diag(np.diag(cov)) + FLOOR * np.eye(len(cov))
        self.inv[view] = np.linalg.inv(cov)
        for label, mu in zip(labels, means):
            kind, name = str(label).split("|", 1)
            self.means[(view, kind, name)] = mu


def hypotheses(type_levels, k, anchor):
    """Every (type, names, places) a run of k bodies can be: k consecutive levels of a type's column,
    the run's last body the column's last where the bottom is anchored (the sacrum in view below
    it); places is how many placements the type allows, its prior shared among them."""
    out = []
    for kind, levels in type_levels.items():
        places = [len(levels) - k] if anchor == "bottom" else range(len(levels) - k + 1)
        for p in places:
            if p >= 0:
                out.append((kind, tuple(levels[p:p + k]), len(places)))
    return out


class Namer:
    """A fitted model's hypotheses for each (view, k, anchor) stacked once: their means, each one's
    quadratic term and log prior, and which hypotheses give the same names, so naming n runs is one
    product. The score of a hypothesis is its log likelihood less the term every hypothesis of the
    run shares, so the best names and the margins are the model's exactly. A hypothesis whose names
    the model has not seen in the view scores minus infinity."""

    def __init__(self, model, type_levels, weights=TYPE_WEIGHTS):
        self.model, self.type_levels, self.weights = model, type_levels, weights
        self.tables = {}

    def table(self, view, k, anchor):
        key = (view, k, anchor)
        if key not in self.tables:
            self.tables[key] = self.stack(view, k, anchor)
        return self.tables[key]

    def stack(self, view, k, anchor):
        hyps = hypotheses(self.type_levels, k, anchor)
        d = self.model.dims
        M = np.zeros((len(hyps), k, d))
        valid = np.full(len(hyps), view in self.model.inv)
        prior = np.zeros(len(hyps))
        for h, (kind, names, places) in enumerate(hyps):
            prior[h] = math.log(self.weights.get(kind, 1e-3)) - math.log(places)
            for i, name in enumerate(names):
                mu = self.model.means.get((view, kind, name))
                if mu is None:
                    valid[h] = False
                else:
                    M[h, i] = mu
        inv = self.model.inv.get(view, np.eye(d))
        quad = np.einsum("hkd,de,hke->h", M, inv, M) if len(hyps) else np.zeros(0)
        groups = sorted({names for _, names, _ in hyps})
        return {"M": M.reshape(len(hyps), k * d), "inv": inv, "bias": np.where(valid, prior - 0.5 * quad, -np.inf),
                "group_of": np.asarray([groups.index(names) for _, names, _ in hyps], int),
                "groups": np.asarray(groups, dtype=str).reshape(len(groups), k), "hypotheses": len(hyps)}

    def name(self, view, anchor, feats):
        """Each names group's best score for each of n runs of one view, anchor and length, feats
        (n, k, d): (n, groups) in the table's order of groups, and the table."""
        n, k, d = feats.shape
        t = self.table(view, k, anchor)
        groups = len(t["groups"])
        best_of = np.full((n, groups), -np.inf)
        if groups == 0:
            return best_of, t
        score = (feats @ t["inv"]).reshape(n, k * d) @ t["M"].T + t["bias"]
        for g in range(groups):
            best_of[:, g] = score[:, t["group_of"] == g].max(axis=1)
        return best_of, t


def judged(best_of, groups, truth):
    """Whether each run is named right, and the margin in log odds of its true names over the best
    other names: positive where it is named right and negative where it is not, so its median says
    how most runs stand; minus infinity where the true names are no hypothesis the model scores,
    plus infinity where no other names are. truth (n, k) against groups (G, k)."""
    n = len(truth)
    if best_of.shape[1] == 0:
        return np.zeros(n, bool), np.full(n, -np.inf)
    eq = np.all(truth[:, None, :] == groups[None, :, :], axis=2)
    has = eq.any(axis=1)
    rows = np.arange(n)
    true_g = eq.argmax(axis=1)
    mine = best_of[rows, true_g]
    others = best_of.copy()
    others[rows, true_g] = -np.inf
    other = others.max(axis=1)
    with np.errstate(invalid="ignore"):
        margin = np.where(has & np.isfinite(mine), mine - other, -np.inf)
    return margin > 0, margin


def name_rows(namer, packs, feats, masks=None):
    """Each run named, one entry per run (of the masks where given): arrays of its view, anchor,
    type, person, length, whether its names came out right and its margin. A run with a chosen
    landmark missing, out of its frame, cannot be named from that frame: it counts as a miss with a
    margin of 0, so a choice of landmarks is never flattered by leaving out the runs it cannot see."""
    cols = {f: [] for f in ("view", "anchor", "type", "person", "k", "right", "margin")}

    def add(p, k, sel, right, margin):
        for field in ("view", "anchor", "type", "person"):
            cols[field].append(p[field][sel])
        cols["k"].append(np.full(int(sel.sum()), k))
        cols["right"].append(np.asarray(right, bool))
        cols["margin"].append(np.asarray(margin, float))

    for k, p in packs.items():
        f = feats[k]
        inside = np.ones(len(f), bool) if masks is None else np.asarray(masks[k], bool)
        whole = whole_runs(f)
        for view in np.unique(p["view"][inside]):
            for anchor in np.unique(p["anchor"][inside]):
                cell = inside & (p["view"] == view) & (p["anchor"] == anchor)
                sel, miss = cell & whole, cell & ~whole
                if sel.any():
                    best_of, t = namer.name(str(view), str(anchor), f[sel])
                    right, margin = judged(best_of, t["groups"], p["names"][sel])
                    add(p, k, sel, right, margin)
                if miss.any():
                    add(p, k, miss, np.zeros(int(miss.sum()), bool), np.zeros(int(miss.sum())))
    return {f: np.concatenate(v) if v else np.empty(0) for f, v in cols.items()}


def join_rows(parts):
    parts = [r for r in parts if len(r["right"])]
    if not parts:
        return {f: np.empty(0) for f in ("view", "anchor", "type", "person", "k", "right", "margin")}
    return {f: np.concatenate([r[f] for r in parts]) for f in parts[0]}


def cells(rows):
    """Accuracy, its Wilson interval and the lower median of the true names' margin per (view,
    anchor, type) cell; the lower median, the smaller of the two middle values, so an even cell is
    never flattered."""
    if len(rows["right"]) == 0:
        return {}
    keys = np.char.add(np.char.add(np.char.add(np.char.add(rows["view"].astype(str), "/"), rows["anchor"].astype(str)), "/"),
                       rows["type"].astype(str))
    table = {}
    for key in np.unique(keys):
        sel = keys == key
        n = int(sel.sum())
        hits = int(rows["right"][sel].sum())
        lo, hi = wilson(hits, n)
        table[str(key)] = {"n": n, "right": hits, "accuracy": hits / n, "low": lo, "high": hi,
                           "median_margin": float(np.percentile(rows["margin"][sel], 50, method="lower")),
                           "persons": int(len(np.unique(rows["person"][sel])))}
    return table


def arm_of(view):
    """The arm a view belongs to: the real pairs' views end in _real, the phantoms' do not."""
    return "real" if str(view).endswith("_real") else "phantom"


def objective(table, arms=()):
    """The selection's objective: the mean over the arms (the phantoms', the real pairs') of the mean
    over each arm's cells of the cell's accuracy, every cell weighed alike within its arm, so an
    anomalous type counts as much as the typical one, and the real frames as much as every phantom.
    An arm the runs hold (arms, from the packs) with no cell in the table counts 0, so a choice that
    names none of an arm's runs never scores as though the arm were not there."""
    by_arm = {arm: [] for arm in arms}
    for key, c in table.items():
        by_arm.setdefault(arm_of(key.split("/")[0]), []).append(c["accuracy"])
    return float(np.mean([np.mean(v) if v else 0.0 for v in by_arm.values()])) if by_arm else 0.0


def arms_of(packs):
    """The arms the runs of the packs belong to."""
    return sorted({arm_of(v) for p in packs.values() for v in np.unique(p["view"])})


def deal_folds(packs, folds):
    """Each person dealt to a fold: within each type, persons in the order of their names' SHA-1, so
    a person's runs share one fold, every type is spread over the folds, and the deal does not
    depend on the order the runs came in."""
    by_type = {}
    for p in packs.values():
        for person, kind in zip(p["person"], p["type"]):
            by_type.setdefault(str(kind), set()).add(str(person))
    deal = {}
    for kind, persons in sorted(by_type.items()):
        for i, person in enumerate(sorted(persons, key=lambda x: hashlib.sha1(x.encode()).hexdigest())):
            deal.setdefault(person, i % folds)
    return deal


def fold_ids(packs, folds):
    deal = deal_folds(packs, folds)
    return {k: np.asarray([deal[str(x)] for x in p["person"]], int) for k, p in packs.items()}


def cv_objective(packs, chosen, type_levels, folds=3, ids=None):
    """The objective of a choice of landmarks, each fold scored by a model fit on the other folds'
    persons; returns the objective and the table of cells it came from."""
    ids = ids if ids is not None else fold_ids(packs, folds)
    feats = features_of(packs, chosen)
    parts = []
    for f in range(folds):
        train = {k: v != f for k, v in ids.items()}
        test = {k: v == f for k, v in ids.items()}
        if not any(m.any() for m in train.values()) or not any(m.any() for m in test.values()):
            continue
        namer = Namer(NameModel().fit(packs, feats, train), type_levels)
        parts.append(name_rows(namer, packs, feats, test))
    table = cells(join_rows(parts))
    return objective(table, arms_of(packs)), table


def greedy_select(packs, pool, type_levels, max_landmarks=8, min_gain=0.005, folds=3, log=None):
    """The landmarks chosen from the pool: the best pair first, then one landmark at a time, each the
    one that raises the objective most, until max_landmarks or a gain below min_gain. Returns the
    chosen indices and every step's objective."""
    pool = list(pool)
    ids = fold_ids(packs, folds)
    trace = []
    best, best_score = None, -1.0
    for i in range(len(pool)):
        for j in range(i + 1, len(pool)):
            score, _ = cv_objective(packs, [pool[i], pool[j]], type_levels, folds, ids)
            if score > best_score:
                best, best_score = [pool[i], pool[j]], score
    if best is None:
        return [], trace
    trace.append({"chosen": [LANDMARKS[i] for i in best], "objective": best_score})
    if log:
        log(f"fingerprint: pair {', '.join(LANDMARKS[i] for i in best)} at {best_score:.3f}")
    while len(best) < max_landmarks:
        step, step_score = None, best_score
        for i in pool:
            if i in best:
                continue
            score, _ = cv_objective(packs, best + [i], type_levels, folds, ids)
            if score > step_score:
                step, step_score = i, score
        if step is None or step_score - best_score < min_gain:
            break
        best, best_score = best + [step], step_score
        trace.append({"chosen": [LANDMARKS[i] for i in best], "objective": best_score})
        if log:
            log(f"fingerprint: + {LANDMARKS[step]} to {best_score:.3f}")
    return best, trace


def upper(cell):
    """The upper end of a cell's accuracy: its Wilson bound, from its runs where it counts them, else
    its accuracy."""
    if "high" in cell:
        return float(cell["high"])
    if "n" in cell and "right" in cell:
        return wilson(int(cell["right"]), int(cell["n"]))[1]
    return float(cell["accuracy"])


def fingerprint_gate(table, bars, anchors=ANCHORS, arm="phantom", ceiling=None):
    """Whether every cell of one arm of the held-out table clears the bars: the Wilson lower bound of
    its accuracy at or above bars['accuracy_low'] and its median margin at or above bars['margin']
    (log(9) where the plan gives none), for each anchor the plan gates on. ceiling is the same table
    for the whole pool, every landmark the search could choose, fitted and judged alike. A failing
    cell is beyond what one frame of the pool's landmarks names, at the selection's size, only where
    the upper ends of both its own interval and its ceiling's fall short of the bar: a cell that fails
    for want of runs, as a perfect cell of a few runs does, is never called beyond, and the result
    says which are cell by cell."""
    failing, cells_failing, beyond = [], [], []
    asked = 0
    margin_bar = bars.get("margin", UNIQUE_MARGIN)
    for key, c in sorted(table.items()):
        view, anchor, kind = key.split("/")
        if anchor not in anchors or arm_of(view) != arm:
            continue
        asked += 1
        if c["low"] < bars["accuracy_low"]:
            failing.append(f"{key}: accuracy {c['accuracy']:.3f}, low {c['low']:.3f} < {bars['accuracy_low']}")
        elif c["median_margin"] < margin_bar:
            failing.append(f"{key}: median margin {c['median_margin']:.2f} < {margin_bar:.2f}")
        else:
            continue
        top = (ceiling or {}).get(key)
        reach = top is None or max(upper(c), upper(top)) >= bars["accuracy_low"]
        cells_failing.append({"cell": key, "accuracy": c["accuracy"], "low": c["low"], "high": upper(c),
                              "margin": c["median_margin"], "ceiling": top["accuracy"] if top else None,
                              "ceiling_high": upper(top) if top else None, "within_reach": reach})
        if not reach:
            beyond.append(key)
    result = {"pass": asked > 0 and not failing, "failing": failing, "cells": asked, "failing_cells": cells_failing,
              "beyond_ceiling": beyond, "ceiling_known": ceiling is not None}
    if asked == 0:
        # No cell of the arm to judge is the gate's data missing, which stops the loop with its
        # reason, never a failure the controller would try to mend with more landmarks.
        result["missing"] = f"no {arm} cell under the anchors {', '.join(anchors)} to judge"
    return result


def within_reach(result):
    """Whether a failing fingerprint result has a cell that a better choice of the pool's landmarks
    could lift: one whose ceiling reaches the bar, or any where no ceiling was measured."""
    cells = result.get("failing_cells") or []
    if not result.get("ceiling_known"):
        return True
    return any(c["within_reach"] for c in cells)


# ---------------------------------------------------------------- presence on real frames

def gaussian_kernel(sigma):
    r = max(1, int(math.ceil(3 * sigma)))
    x = np.arange(-r, r + 1, dtype=float)
    k = np.exp(-0.5 * (x / sigma) ** 2)
    return k / k.sum()


def smooth(image, sigma):
    """A separable Gaussian blur, edges carried outward."""
    k = gaussian_kernel(sigma)
    r = len(k) // 2
    out = np.asarray(image, float)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        p = np.pad(out, pad, mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(p, len(k), axis=axis)
        out = windows @ k
    return out


def edge_strength(image, sigma=1.5):
    """The gradient magnitude of the blurred image, scaled to its 99th percentile."""
    s = smooth(image, sigma)
    gy, gx = np.gradient(s)
    g = np.hypot(gx, gy)
    top = np.percentile(g, 99)
    return g / top if top > 0 else g


def max_near(field, radius):
    """Each pixel's maximum over the square of half-width radius about it, edges carried outward."""
    out = np.asarray(field, float)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (radius, radius)
        p = np.pad(out, pad, mode="edge")
        out = np.lib.stride_tricks.sliding_window_view(p, 2 * radius + 1, axis=axis).max(axis=-1)
    return out


def sample_at(field, uv):
    """The field at pixel centres nearest uv (n, 2), column then row; NaN outside the field."""
    uv = np.asarray(uv, float)
    out = np.full(len(uv), np.nan)
    ok = np.all(np.isfinite(uv), axis=1)
    c = np.floor(uv[ok, 0]).astype(int)
    r = np.floor(uv[ok, 1]).astype(int)
    inside = (c >= 0) & (c < field.shape[1]) & (r >= 0) & (r < field.shape[0])
    vals = np.full(ok.sum(), np.nan)
    vals[inside] = field[r[inside], c[inside]]
    out[ok] = vals
    return out


def inside_hull(points2d, n, rng):
    """n points drawn uniformly inside the convex hull of a body's projected landmarks, by drawing in
    their bounding box and keeping those inside every edge of the hull."""
    P = np.asarray(points2d, float)
    P = P[np.all(np.isfinite(P), axis=1)]
    if len(P) < 3:
        return np.empty((0, 2))
    hull = convex_hull(P)
    lo, hi = P.min(axis=0), P.max(axis=0)
    out = []
    for _ in range(20):
        q = rng.uniform(lo, hi, size=(4 * n, 2))
        keep = np.ones(len(q), bool)
        for a, b in zip(hull, np.roll(hull, -1, axis=0)):
            keep &= ((b[0] - a[0]) * (q[:, 1] - a[1]) - (b[1] - a[1]) * (q[:, 0] - a[0])) >= 0
        out.extend(q[keep])
        if len(out) >= n:
            break
    return np.asarray(out[:n])


def convex_hull(P):
    """The convex hull of 2-D points, counter-clockwise (Andrew's monotone chain)."""
    pts = sorted(map(tuple, np.asarray(P, float)))
    if len(pts) <= 2:
        return np.asarray(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.asarray(lower[:-1] + upper[:-1])


def presence_percentiles(image, bodies, chosen, radius=8, sigma=1.5, null_per_body=200, seed=0):
    """Each chosen landmark's edge evidence as a percentile of the frame's null: the strongest edge
    within radius pixels of its projected position, against the same at points drawn inside the
    bodies' projected outlines. bodies is a list of (18, 2) projected landmarks in the image's pixels.
    Returns (percentiles (bodies, chosen), how many null points)."""
    rng = np.random.default_rng(seed)
    field = max_near(edge_strength(image, sigma), radius)
    null = np.concatenate([sample_at(field, inside_hull(b, null_per_body, rng)) for b in bodies] or [np.empty(0)])
    null = np.sort(null[np.isfinite(null)])
    out = np.full((len(bodies), len(chosen)), np.nan)
    if len(null) == 0:
        return out, 0
    for i, b in enumerate(bodies):
        vals = sample_at(field, np.asarray(b, float)[list(chosen)])
        ok = np.isfinite(vals)
        out[i, ok] = np.searchsorted(null, vals[ok], side="right") / len(null)
    return out, int(len(null))


def presence_gate(frame_means, bars):
    """Whether most frames show the fingerprint: the share of frames whose landmarks' mean percentile
    is at or above bars['frame_mean'], its Wilson lower bound at or above bars['share_low']."""
    m = np.asarray([x for x in frame_means if np.isfinite(x)])
    hits = int((m >= bars["frame_mean"]).sum())
    lo, hi = wilson(hits, len(m))
    passed = bool(len(m)) and lo >= bars["share_low"]
    why = (f"{hits} of {len(m)} frames show the landmarks at or above the {bars['frame_mean']} percentile, the share's "
           f"low {lo:.3f} {'at or above' if passed else 'below'} {bars['share_low']}") if len(m) else "no frame had a landmark to read"
    return {"pass": passed, "why": why, "frames": int(len(m)), "hits": hits, "low": lo, "high": hi,
            "median": float(np.median(m)) if len(m) else float("nan")}


# ---------------------------------------------------------------- the network's gates

def convergence(totals, held, bars):
    """Whether training has converged: the mean training loss over the last window within rel_tol of
    the window before it, and this round's held-out distance no worse than the best round's by more
    than rise_tol of it. totals: every step's loss of the session, in order; held: each round's
    held-out distance_mm, this round last."""
    w = int(bars["window"])
    x = np.asarray(totals, float)
    if len(x) < 2 * w:
        return {"pass": False, "why": f"{len(x)} steps, fewer than two windows of {w}", "steps": int(len(x))}
    last, before = x[-w:].mean(), x[-2 * w:-w].mean()
    change = abs(last - before) / max(abs(before), 1e-12)
    flat = change <= bars["rel_tol"]
    # A round's distance comes back from JSON, where one that was not finite is its name in words.
    h = [float(v) for v in held if isinstance(v, (int, float)) and math.isfinite(v)]
    rising = bool(h) and len(h) > 1 and h[-1] > min(h[:-1]) * (1 + bars["rise_tol"])
    why = []
    if not flat:
        why.append(f"loss still moving: {change:.3f} of the window before")
    if rising:
        why.append(f"held-out distance rising: {h[-1]:.2f} mm against the best {min(h[:-1]):.2f} mm")
    return {"pass": flat and not rising, "why": "; ".join(why) or "flat and not rising", "change": float(change),
            "steps": int(len(x)), "last_mean": float(last), "held": h[-1] if h else None}


def probe(train_latents, train_labels, test_latents, test_labels):
    """A nearest-class-mean probe on the latent alone: the latents standardised on the training crops,
    each test crop given the class whose training mean is nearest. Returns per-class recall and n."""
    A = np.asarray(train_latents, float)
    mu, sd = A.mean(axis=0), A.std(axis=0) + 1e-6
    A = (A - mu) / sd
    B = (np.asarray(test_latents, float) - mu) / sd
    labels = sorted(set(train_labels))
    means = np.vstack([A[np.asarray(train_labels) == c].mean(axis=0) for c in labels])
    d = ((B[:, None, :] - means[None]) ** 2).sum(axis=2)
    guess = [labels[i] for i in d.argmin(axis=1)]
    out = {}
    for c in sorted(set(test_labels)):
        idx = [i for i, t in enumerate(test_labels) if t == c]
        out[c] = {"n": len(idx), "recall": sum(guess[i] == c for i in idx) / len(idx) if idx else float("nan")}
    return out


def mean_low(values, z=Z95):
    """The lower end of the normal 95 per cent interval of the mean of values, the mean less z
    standard errors; not a number where fewer than two of the values are numbers."""
    x = np.asarray(values, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return float("nan")
    return float(x.mean() - z * x.std(ddof=1) / math.sqrt(len(x)))


def anomaly_gate(per_class, bars, classes):
    """Whether every anomaly class the plan names is decoded and encoded: per_class gives each class's
    held-out crops' Dice, the name head's share named right and the probe's recall, each judged by the
    lower end of its 95 per cent interval where the round gives one (dice_low, named_low, probe_low:
    the mean's normal interval for Dice, Wilson's for the two shares), so a class passes on its crops'
    evidence and not on a lucky few; by the measure itself where no interval is given."""
    failing = []
    for c in classes:
        r = per_class.get(c)
        if not r or r.get("n", 0) == 0:
            failing.append(f"{c}: no held-out crop")
            continue
        # Written as not-at-or-above, so a measure that is not a number fails the bar.
        for measure, low, words in (("dice", "dice_low", "Dice"), ("named_right", "named_low", "named right"),
                                    ("probe_recall", "probe_low", "probe recall")):
            value = r.get(low, r.get(measure, float("nan")))
            if not (isinstance(value, (int, float)) and value >= bars[measure]):
                said = f"{value:.3f}" if isinstance(value, (int, float)) else str(value)
                failing.append(f"{c}: {words}{' lower bound' if low in r else ''} {said} below {bars[measure]}")
    return {"pass": not failing, "failing": failing}


# ---------------------------------------------------------------- latency

def time_naming(namer, packs, chosen, runs=500):
    """Seconds per frame of the 2-D naming path, one run at a time as frames come: its features and
    every hypothesis's score against the fitted tables, which are stacked before the clock starts.
    The runs timed are spread evenly over every length, view and anchor the packs hold."""
    every = [(k, i) for k, p in sorted(packs.items()) for i in range(len(p["person"]))]
    if not every:
        return []
    picks = sorted(set(np.linspace(0, len(every) - 1, min(runs, len(every))).round().astype(int).tolist()))
    seconds = []
    for j in picks:
        k, i = every[j]
        p = packs[k]
        view, anchor = str(p["view"][i]), str(p["anchor"][i])
        namer.table(view, k, anchor)
        points = p["points"][i:i + 1]
        t0 = time.perf_counter()
        namer.name(view, anchor, batch_features(points, chosen))[0].argmax(axis=1)
        seconds.append(time.perf_counter() - t0)
    return seconds


def latency_gate(seconds, bars):
    s = np.asarray(seconds, float)
    if len(s) == 0:
        return {"pass": False, "why": "nothing timed"}
    p50, p95 = np.percentile(s, [50, 95])
    return {"pass": bool(p95 * 1000 <= bars["p95_ms"]), "n": int(len(s)), "p50_ms": float(p50 * 1000),
            "p95_ms": float(p95 * 1000), "max_ms": float(s.max() * 1000), "budget_ms": bars["p95_ms"]}


# ---------------------------------------------------------------- the space plan

def space_plan(blocks, free_disk, free_ram, disk_share=0.9, ram_share=0.8):
    """How many units of work fit at once: blocks maps each block to its measured bytes on disk and
    peak resident bytes per unit (a phantom row, a pair's case, a round); the plan is the most units
    whose summed disk and memory fit in the shares of what is free, the binding block named."""
    disk_per = sum(b.get("disk_bytes", 0) for b in blocks.values())
    ram_per = max([b.get("rss_bytes", 0) for b in blocks.values()] or [0])
    by_disk = int(free_disk * disk_share // disk_per) if disk_per > 0 else None
    by_ram = int(free_ram * ram_share // ram_per) if ram_per > 0 else None
    limits = [x for x in (by_disk, by_ram) if x is not None]
    units = max(1, min(limits)) if limits else 1
    binding = "disk" if by_disk is not None and (by_ram is None or by_disk <= by_ram) else "memory"
    return {"units_at_once": units, "binding": binding if limits else "none measured", "disk_per_unit": disk_per,
            "ram_per_unit": ram_per, "free_disk": int(free_disk), "free_ram": int(free_ram), "blocks": blocks}


# ---------------------------------------------------------------- the controller

# ---------------------------------------------------------------- the training watch
#
# The owner's words of 2026-10-31 04:18 UTC: track the objective and the loss as training goes,
# watch for answers that cannot be right, and go on only while a run makes progress, over some fifty
# epochs. Within a round the network trains a check at a time (every_epochs), each check's loss and
# held measures written down; a check whose numbers cannot be right stops the run; training rests
# once the held measures have gained nothing for patience_epochs, and starts again only when the
# rows it trains on have grown; the loop ends once patience_rounds rounds in a row raised no measure.

WATCH_KEYS = ("every_epochs", "patience_epochs", "min_gain", "explode", "warm_epochs", "watch_per_class",
              "patience_rounds")
LOSS_FLOOR = 0.01   # the explode test's best loss is taken as at least this, so a loss near nought never trips it


def insane(point, best_loss, watch, bound_mm):
    """Why one check's numbers cannot be right, or None: a loss or a held measure that is not a
    number, a loss over watch['explode'] times the best check's, a Dice outside 0 to 1, a surface
    distance below nought or past the crop's longest side (bound_mm), or, once warm_epochs have
    passed, no held crop with any predicted surface, the network collapsed to empty masks."""
    for name in ("loss", "loss_last", "held_dice", "held_distance_mm"):
        value = point.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return f"{name} is not a number at step {point.get('step')}"
    if best_loss is not None and point["loss"] > watch["explode"] * max(best_loss, LOSS_FLOOR):
        return (f"the loss {point['loss']:.4g} at step {point['step']} is over {watch['explode']:g} times "
                f"its best check's {best_loss:.4g}")
    if not 0.0 <= point["held_dice"] <= 1.0:
        return f"a held Dice of {point['held_dice']:.4g} at step {point['step']}"
    if not 0.0 <= point["held_distance_mm"] <= bound_mm * (1 + 1e-6):
        return (f"a held surface distance of {point['held_distance_mm']:.4g} mm at step {point['step']}, "
                f"outside 0 to the crop's {bound_mm:.1f} mm")
    crops = int(point.get("crops") or 0)
    if point["epoch"] >= watch["warm_epochs"] and crops and int(point.get("surface_missing", 0)) >= crops:
        return f"collapsed: no held crop has a predicted surface after {point['epoch']:.1f} epochs"
    return None


def watch_step(state, point, watch):
    """The watch after one check, and whether the check gained: a held distance below the last
    gaining one by min_gain of itself, or a held Dice above the last gaining one by min_gain. Keeps
    the last gaining values and their epoch, step and round, the best loss and the epochs since the
    last gain."""
    s = dict(state)
    gained = False
    if s.get("best_distance_mm") is None or point["held_distance_mm"] < s["best_distance_mm"] * (1 - watch["min_gain"]):
        s["best_distance_mm"], gained = point["held_distance_mm"], True
    if s.get("best_dice") is None or point["held_dice"] > s["best_dice"] + watch["min_gain"]:
        s["best_dice"], gained = point["held_dice"], True
    if gained or s.get("best_epoch") is None:
        s.update(best_epoch=point["epoch"], best_step=point["step"], best_round=point["round"])
    s["best_loss"] = point["loss"] if s.get("best_loss") is None else min(s["best_loss"], point["loss"])
    s["epoch"] = point["epoch"]
    s["since_best"] = point["epoch"] - s["best_epoch"]
    return s, gained


def stalled(state, watch):
    """Whether training has gained nothing on the held measures for patience_epochs."""
    return state.get("best_epoch") is not None and state.get("since_best", 0.0) >= watch["patience_epochs"]


def round_measures(record):
    """The measures the loop's progress is judged by, each larger for better and on one scale, so one
    min_gain serves them all: the held Dice; the log of the held distance and of the latency's 95th
    percentile, negated, so a share of either is a gain; each anomaly class's worst lower bound
    against its bar, averaged; the mean lower bound of the phantom cells and of the real cells; and
    the presence share's lower bound. A measure the round could not give is left out."""
    out = {}
    held = record.get("held") or {}
    gates = record.get("gates") or {}

    def number(x):
        return isinstance(x, (int, float)) and math.isfinite(x)

    if number(held.get("dice")):
        out["held_dice"] = float(held["dice"])
    fingerprint = record.get("fingerprint") or {}
    if number(fingerprint.get("objective")):
        out["objective"] = float(fingerprint["objective"])
    if number(held.get("distance_mm")) and held["distance_mm"] > 0:
        out["held_distance"] = -math.log(held["distance_mm"])
    per_class = ((gates.get("anomaly") or {}).get("per_class") or {})
    worst = []
    for r in per_class.values():
        lows = [r.get(k, r.get(m)) for k, m in (("dice_low", "dice"), ("named_low", "named_right"), ("probe_low", "probe_recall"))]
        worst.append(min(x if number(x) else 0.0 for x in lows))
    if worst:
        out["anomaly"] = float(np.mean(worst))
    for arm in ("phantom", "real"):
        lows = [c["low"] for key, c in (record.get("cells") or {}).items() if arm_of(key.split("/")[0]) == arm]
        if lows:
            out[f"cells_{arm}"] = float(np.mean(lows))
    presence = gates.get("presence") or {}
    if number(presence.get("low")):
        out["presence"] = float(presence["low"])
    latency = gates.get("latency") or {}
    if number(latency.get("p95_ms")) and latency["p95_ms"] > 0:
        out["latency"] = -math.log(latency["p95_ms"])
    return out


# The measures the loop's progress is judged by: each is read off rows, persons or frames that stay
# the same from round to round, so a change in it is the network's or the controller's doing. The
# phantom cells and the latency are recorded but judge nothing: the gate's phantom persons are drawn
# anew every round and the latency is a timing, so their noise alone would read as a gain and keep a
# loop that has stopped improving going.
PROGRESS_MEASURES = ("held_dice", "held_distance", "objective", "anomaly", "cells_real", "presence")


def loop_progress(progress, measures, watch):
    """The loop's progress after a round: each steady measure's best so far (PROGRESS_MEASURES),
    whether this round raised any of them by min_gain, and how many rounds in a row raised none. The
    first round's measures are the first bests and count as a gain."""
    measures = {k: v for k, v in measures.items() if k in PROGRESS_MEASURES}
    best = dict(progress.get("best") or {})
    raised = [k for k, v in measures.items() if k not in best or v > best[k] + watch["min_gain"]]
    for k, v in measures.items():
        best[k] = max(v, best.get(k, v))
    flat = 0 if raised else int(progress.get("flat_rounds", 0)) + 1
    return {"best": best, "raised": raised, "flat_rounds": flat}


def watch_problems(plan):
    """What keeps the plan's watch from holding, in words."""
    w = plan.get("watch")
    if not isinstance(w, dict):
        return ["the plan has no watch"]
    out = [f"watch has no {k}" for k in WATCH_KEYS if k not in w]
    if out:
        return out
    for k in WATCH_KEYS:
        if not isinstance(w[k], (int, float)) or isinstance(w[k], bool) or w[k] <= 0:
            out.append(f"watch {k} is a number above 0, not {w[k]!r}")
    for k in ("watch_per_class", "patience_rounds"):
        if not isinstance(w[k], int):
            out.append(f"watch {k} is a whole number")
    if not out and w["explode"] <= 1:
        out.append("watch explode is above 1, a multiple of the best loss")
    if not out and w["patience_epochs"] < w["every_epochs"]:
        out.append("watch patience_epochs is at least every_epochs, or no check could see it pass")
    return out


GATES = ("convergence", "anomaly", "fingerprint", "presence", "real_naming", "latency")
CLASSES = ("typical", "lumbar_rib", "no_rib_t12", "six_lumbar", "four_lumbar", "t13")
PLAN_KEYS = ("plan", "purpose", "class", "rounds", "gates", "words", "steps_per_round", "classes", "phantom_rows",
             "fingerprint", "pairs", "presence", "bars", "start", "limits", "latency_runs", "watch")
START_KEYS = ("phantoms_per_class", "w_name", "fingerprint_persons", "max_landmarks", "presence_floor")
PLAN_CLASSES = ("smoke", "loop")


def plan_problems(plan):
    """What keeps a plan (grid/qaloop/<plan>.json) from running, in words; empty where it holds."""
    if not isinstance(plan, dict):
        return ["the plan is not a JSON object"]
    out = [f"the plan has no {k}" for k in PLAN_KEYS if k not in plan]
    if out:
        return out
    if plan["class"] not in PLAN_CLASSES:
        out.append(f"class is one of {', '.join(PLAN_CLASSES)}, not {plan['class']!r}")
    if not isinstance(plan["rounds"], int) or plan["rounds"] < 1:
        out.append("rounds is a whole number of at least 1")
    unknown = [g for g in plan["gates"] if g not in GATES]
    if unknown or not plan["gates"]:
        out.append(f"gates are some of {', '.join(GATES)}, not {plan['gates']!r}")
    classes = [c for c in plan["classes"] if c not in CLASSES]
    if classes or "typical" not in plan["classes"]:
        out.append(f"classes are some of {', '.join(CLASSES)}, typical among them, not {plan['classes']!r}")
    missing = [k for k in START_KEYS if k not in plan["start"]]
    if missing:
        out.append(f"start has no {', '.join(missing)}")
    for gate in plan["gates"]:
        if gate not in plan["bars"]:
            out.append(f"bars has no {gate}")
    if plan["class"] == "loop" and plan["pairs"].get("stand_ins"):
        out.append("a loop plan never names stand-ins: its real gates are asked of real frames or not at all")
    if not isinstance(plan["steps_per_round"], int) or plan["steps_per_round"] < 1:
        out.append("steps_per_round is a whole number of at least 1")
    out += watch_problems(plan)
    if not missing:
        out += limits_problems(plan)
    return out


# The levers whose plan limit may be null: the memory alone bounds them, measured every round (the
# owner's words of 2026-10-31, that the one guard wanted is how much space each block's output needs,
# so the memory does not choke). The others are the range the controller searches, never a resource.
MEMORY_BOUND = ("phantoms_per_class", "fingerprint_persons")


def limits_problems(plan):
    """What keeps the plan's limits from holding: each lever's limit a number no smaller than its
    start, or null for a lever the memory alone bounds."""
    out = []
    limits, start = plan["limits"], plan["start"]
    if not isinstance(limits, dict):
        return ["limits is a JSON object"]
    for key in START_KEYS:
        if key not in limits:
            out.append(f"limits has no {key}")
        elif limits[key] is None:
            if key not in MEMORY_BOUND:
                out.append(f"limits: {key} is a number, since only {', '.join(MEMORY_BOUND)} are bounded by the memory alone")
        elif not isinstance(limits[key], (int, float)) or isinstance(limits[key], bool):
            out.append(f"limits: {key} is a number or null, not {limits[key]!r}")
        elif isinstance(start.get(key), (int, float)) and limits[key] < start[key]:
            out.append(f"limits: {key} {limits[key]} is below its start {start[key]}")
    return out


def grown(value, factor, limit, cast=float):
    """value times factor, no further than the limit (None for none); the value itself where it is
    at the limit."""
    if limit is None:
        return cast(value * factor)
    return cast(min(value * factor, limit)) if value < limit else value


def tightest(*caps):
    """The smallest of the caps that are set, or None where none is."""
    set_ = [c for c in caps if c is not None]
    return min(set_) if set_ else None


def controller(record, state, plan):
    """The next round from this round's record (tools/qaloop_round.py's gates.json): done when every
    gate the plan asks passes; stopped where a gate could not be asked for want of data (its result
    says why); not met when the rounds run out or no failing gate has a change left in the plan's
    ranges or the measured memory; else one change for each failing gate that has one, the changes
    and the gates left with none said in words."""
    gates = record.get("gates", {})
    asked = list(plan.get("gates", GATES))
    results = {g: gates.get(g) for g in asked}
    missing = [g for g, r in results.items() if r is None or r.get("missing")]
    passing = [g for g, r in results.items() if r and r.get("pass")]
    failing = [g for g in asked if g not in passing]
    round_ = int(state.get("round", 0))
    watch = plan.get("watch") or {}
    progress = loop_progress(state.get("progress") or {}, round_measures(record), watch) if watch else {}
    common = {"passing": passing, "failing": failing, "changes": [], "stuck": [], "progress": progress}
    if missing:
        whys = "; ".join(f"{g}: {(results[g] or {}).get('missing') or 'not run'}" for g in missing)
        return {**common, "branch": "done", "verdict": "stopped", "why": f"missing data: {whys}"}
    if not failing:
        return {**common, "branch": "done", "verdict": "met", "why": "every gate passes"}
    if round_ + 1 >= int(plan["rounds"]):
        return {**common, "branch": "done", "verdict": "not met",
                "why": f"{plan['rounds']} rounds run; failing {', '.join(failing)}"}
    if watch and progress["flat_rounds"] >= int(watch["patience_rounds"]):
        best = ", ".join(f"{k} {v:.3f}" for k, v in sorted(progress["best"].items()))
        return {**common, "branch": "done", "verdict": "not met",
                "why": f"no progress: {progress['flat_rounds']} rounds in a row raised no measure by "
                       f"{watch['min_gain']}; failing {', '.join(failing)}; best {best}"}
    limits = plan.get("limits", {})
    nxt = dict(plan.get("start", {}), **state.get("config", {}))
    changes, stuck = [], []
    # Training that has gained nothing on the held measures for the watch's patience has converged
    # as far as these rows take it: the data may change, and training rests until it does.
    resting = bool((record.get("watch") or {}).get("stalled"))
    converged = "convergence" not in asked or results["convergence"]["pass"] or resting
    if "convergence" in failing:
        if resting:
            stuck.append("convergence: training rests, the held measures gained nothing in "
                         f"{watch.get('patience_epochs')} epochs; it trains again once the rows grow")
        else:
            changes.append("convergence: train on, the loss has not settled")
    if "anomaly" in failing:
        anomaly_change(nxt, limits, record, plan, converged, changes, stuck)
    chosen = len((record.get("fingerprint") or {}).get("chosen") or []) if record.get("fingerprint") else None
    if "latency" in failing:
        # First, so the cap it sets binds the landmarks the other gates would add this same round.
        latency_change(nxt, chosen, changes, stuck)
    if "fingerprint" in failing:
        fingerprint_change(nxt, limits, results["fingerprint"], (record.get("space") or {}).get("persons_fit"), changes,
                           stuck, chosen)
    if "presence" in failing:
        floor = round(min(nxt["presence_floor"] + 0.1, limits.get("presence_floor", 0.5)), 3)
        if floor > nxt["presence_floor"]:
            nxt["presence_floor"] = floor
            changes.append(f"presence: landmarks whose mean edge percentile on the selection's frames is below "
                           f"{floor:.2f} leave the pool")
        else:
            stuck.append(f"presence: the floor is at its limit {nxt['presence_floor']}")
    if "real_naming" in failing:
        real = results["real_naming"]
        if not within_reach(real):
            stuck.append("real naming: every failing cell is beyond the ceiling of the pool's landmarks on real frames")
        elif any(c.startswith("fingerprint: up to") for c in changes):
            changes.append("real naming: the fingerprint's added landmarks serve it too")
        elif nxt["max_landmarks"] < landmark_top(nxt, limits) and (chosen is None or chosen >= nxt["max_landmarks"]):
            nxt["max_landmarks"] = min(nxt["max_landmarks"] + 2, landmark_top(nxt, limits))
            changes.append(f"real naming: up to {nxt['max_landmarks']} landmarks")
        else:
            stuck.append(f"real naming: landmarks at {nxt['max_landmarks']}, as many as the plan, the latency and "
                         f"the search allow")
    common = {**common, "stuck": stuck}
    if not changes:
        return {**common, "branch": "done", "verdict": "not met",
                "why": "no change left in the plan's ranges or the measured memory: " + "; ".join(stuck)}
    return {**common, "branch": "again", "verdict": "running", "why": "; ".join(changes), "changes": changes,
            "config": nxt}


def latency_change(nxt, chosen, changes, stuck):
    """The latency gate's change: at most two landmarks fewer than this round named with, held as a cap
    the fingerprint and real naming never raise past, since the naming path's time grows with them."""
    used = int(chosen) if chosen else int(nxt["max_landmarks"])
    if used > 2:
        cap = max(2, used - 2)
        nxt["landmark_cap"] = cap
        nxt["max_landmarks"] = min(int(nxt["max_landmarks"]), cap)
        changes.append(f"latency: at most {cap} landmarks from now on")
    else:
        stuck.append("latency: two landmarks already")


def anomaly_change(nxt, limits, record, plan, converged, changes, stuck):
    """The anomaly gate's change: more phantoms per class while the memory holds them, then a heavier
    name head; nothing while training has not converged, since the data is not yet the question."""
    if not converged:
        changes.append("anomaly: waits for the loss to settle before the data changes")
        return
    space = record.get("space") or {}
    gate_rows = int((plan.get("phantom_rows") or {}).get("gate_per_class", 2))
    fit = space.get("rows_fit")
    by_memory = max(1, int(fit) // max(1, len(plan["classes"])) - gate_rows) if fit is not None else None
    cap = tightest(limits.get("phantoms_per_class"), by_memory)
    # With neither a limit nor a measure of the memory nothing says how many rows fit, so none are added.
    more = grown(int(nxt["phantoms_per_class"]), 2, cap, int) if cap is not None else nxt["phantoms_per_class"]
    if more > nxt["phantoms_per_class"]:
        changes.append(f"anomaly: phantoms per class {nxt['phantoms_per_class']} to {more}")
        nxt["phantoms_per_class"] = more
        return
    weight = grown(float(nxt["w_name"]), 2, float(limits.get("w_name", 1.6)))
    if weight > nxt["w_name"]:
        nxt["w_name"] = round(weight, 6)
        changes.append(f"anomaly: the name head's weight to {nxt['w_name']}")
        return
    stuck.append(f"anomaly: phantoms per class at {nxt['phantoms_per_class']} (the memory and the plan hold no more) "
                 f"and the name head's weight at its limit {nxt['w_name']}")


def landmark_top(nxt, limits):
    """The most landmarks the controller may ask for: the plan's limit, and below it the cap the
    latency gate set once the naming path ran too slow, so the two gates never undo each other."""
    top = int(limits.get("max_landmarks", len(LANDMARKS)))
    cap = nxt.get("landmark_cap")
    return min(top, int(cap)) if cap is not None else top


def fingerprint_change(nxt, limits, result, persons_fit, changes, stuck, chosen=None):
    """The fingerprint's change. Where a failing cell is within reach and the search took every
    landmark it was allowed (chosen, this round's count), two more landmarks, which move the choice
    toward the whole pool; then, with every landmark of the range in, where the search stopped short
    of its allowance on its own, or where every failing cell is beyond the ceiling, twice the
    selection's persons a type, as many as the memory holds (persons_fit, measured this round),
    which fit the namer's tables better. The ceiling is measured at the selection's size, so the
    cells beyond one frame of the pool's landmarks are named as the finding only once the memory
    holds no more persons."""
    reach = within_reach(result)
    top = landmark_top(nxt, limits)
    full = chosen is None or int(chosen) >= int(nxt["max_landmarks"])
    if reach and full and nxt["max_landmarks"] < top:
        nxt["max_landmarks"] = min(nxt["max_landmarks"] + 2, top)
        changes.append(f"fingerprint: up to {nxt['max_landmarks']} landmarks")
        return
    cap = tightest(limits.get("fingerprint_persons"), int(persons_fit) if persons_fit is not None else None)
    persons = grown(int(nxt["fingerprint_persons"]), 2, cap, int) if cap is not None else nxt["fingerprint_persons"]
    if persons > nxt["fingerprint_persons"]:
        again = "" if reach else ", every failing cell beyond the ceiling at this size, so the ceiling is measured again"
        changes.append(f"fingerprint: persons per type {nxt['fingerprint_persons']} to {persons}{again}")
        nxt["fingerprint_persons"] = persons
        return
    if not reach:
        beyond = ", ".join(result.get("beyond_ceiling") or [])
        stuck.append(f"fingerprint: beyond the ceiling of the pool's landmarks in one frame at {nxt['fingerprint_persons']} "
                     f"persons a type, as many as the plan and the memory hold ({beyond})")
        return
    stuck.append(f"fingerprint: landmarks at {nxt['max_landmarks']}, the whole range, and persons at "
                 f"{nxt['fingerprint_persons']}, as many as the plan and the memory hold")
