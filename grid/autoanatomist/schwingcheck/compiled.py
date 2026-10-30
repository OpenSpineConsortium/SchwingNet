"""The exact rule as one compiled PyTensor function: step d's reference for the PyMC model.

    rule = compiled.ExactRule(mu, sd, noise=errors, power=powers)   # the table, (measures, levels), each measure's error and power
    hyp = compiled.hypotheses(len(LEVELS), [[0, 1, 2]])      # every place of one pattern
    out = rule.evaluate(X, hyp)                              # log evidence and posterior
    prepared = rule.prepare(hyp)                             # the table's side alone, built once
    out = rule.evaluate(X, hyp, prepared=prepared)           # the same answer from the fields' side alone

The arithmetic is rule.py's, written as a PyTensor graph and compiled once per process by
PyTensor's default backend (Numba): given a hypothesis (the level of every body in the field)
and the patient's size s, each measure's values are jointly normal with mean s^p mu and
covariance Delta + u u', Delta carrying the measure's own error and p the measure's power of the
size (1 for a length, 2 for an area, 0 for an angle), whose log density has the Sherman-Morrison
closed form; the size is integrated by quadrature over log s, rule.py's Gauss-Hermite nodes or
its trapezoid grid; the measures multiply; the hypotheses are normalised by a logsumexp. Nothing is
sampled, so the level k is never a random variable a sampler has to move through (the owner's
word of 27 October 2026, 09:46 UTC, on avoiding Metropolis bottlenecks): it is enumerated and
summed out exactly, and NUTS in model.py only ever sees the continuous size.

Three things generalise rule.py without changing its contiguous, complete answers:

- A hypothesis is any row of level indices, not only a start k with fixed offsets, so a field
  whose gap pattern is unknown (TODO.md 4c) is scored over every (pattern, place) pair in one
  call, and the posterior over places alone is the sum over patterns (`hypotheses`, `marginal`).
- The size prior may differ by field, as it does once a patient's height shifts it
  (covariates.py): the quadrature keeps one set of nodes in log s and each field carries its own
  log weights, the Gauss-Hermite weights times the ratio of its prior to the nodes' own. With the
  archive's prior the ratio is one and the weights are the archive's to the last bit. Nodes on
  which a field's prior is not whole are refused, as the trapezoid's of the default reach are for
  a height outside 161 to 175 cm (rule.check_prior_held).
- A measure's mean may be scaled field by field, as the weight and age hooks of covariates.py
  scale it once they are not zero: fields that share one row of factors go through one call with
  the table's means scaled, so while the hooks are zero every field goes through the archive's
  table and nothing changes.

Every sum over bodies is the same batched matrix product as rule.py's, so no Python loop runs
per place or body, nor per field while the fields share one row of mean factors, as every field
does while the hooks are zero: fields go through in chunks only to bound memory. Each further
row of factors is one more call, so with a weight or age hook on it is one call per patient
whose weight or age is known, one per field where each field is a patient of its own, slower
though the same answer; a graph taking the factors on the fields' side of the product would
make it one call again.

The product has two sides: the table's, the (measures, 3 x bodies, 4 x nodes x hypotheses)
blocks that depend on the table, the nodes and the hypotheses alone, and the fields'. `evaluate`
builds both on every call. A service that names many fields under one set of hypotheses builds
the table's side once (`prepare`, as rule.py's callers build rule.table_blocks once) and hands it
to `evaluate`, which then computes the fields' side alone, with the same answer to the bit. The
build-up study times the compiled rule so (curve.py), as it times rule.py with its blocks built
once: the blocks grow with every measure, body, node and hypothesis, (32, 27, 15,736) doubles or
109 MB at 32 measures and 9 bodies on the trapezoid's 281 nodes, and a one-field call that built
them would time the table with the field.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .rule import GH_NODES, SYNTH, check_prior_held, quadrature, size_factors

LOG2PI = math.log(2.0 * math.pi)
CHUNK = 256             # fields per call: the product's output is (measures, fields, 4 x nodes x hypotheses)


@dataclass(frozen=True)
class Hypotheses:
    """Every hypothesis a field is scored under: the level index of each of its bodies (H, B),
    the place (the level index of its first body) and the pattern each row belongs to."""
    levels: np.ndarray          # (H, B) int, indices into the table's levels
    place: np.ndarray           # (H,) int
    pattern: np.ndarray         # (H,) int, index into `patterns`
    patterns: Tuple[Tuple[int, ...], ...]
    n_levels: int

    def __len__(self) -> int:
        return len(self.place)


def hypotheses(n_levels: int, patterns: Sequence[Sequence[int]]) -> Hypotheses:
    """Every (pattern, place) pair: for each pattern of offsets (0 first, increasing), every start
    at which its last body still fits a column of n_levels. Patterns need the same number of
    bodies. One pattern gives rule.py's places in rule.py's order."""
    pats = [tuple(int(o) for o in p) for p in patterns]
    if not pats:
        raise ValueError("no pattern of offsets")
    if len({len(p) for p in pats}) != 1:
        raise ValueError("every pattern needs the same number of bodies: %r" % (pats,))
    rows, place, pattern = [], [], []
    for i, p in enumerate(pats):
        o = np.asarray(p, int)
        if o[0] != 0 or np.any(np.diff(o) <= 0):
            raise ValueError("offsets start at 0 and increase: %r" % (p,))
        K = n_levels - int(o[-1])
        if K <= 0:
            raise ValueError("a field spanning %d bodies does not fit a column of %d" % (int(o[-1]) + 1, n_levels))
        rows.append(np.arange(K)[:, None] + o[None, :])
        place.append(np.arange(K))
        pattern.append(np.full(K, i))
    return Hypotheses(levels=np.concatenate(rows), place=np.concatenate(place), pattern=np.concatenate(pattern),
                      patterns=tuple(pats), n_levels=n_levels)


def size_log_weights(nodes_log_s: np.ndarray, logw: np.ndarray, base_sd: float,
                     mean: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Per-field log weights for integrating over log s ~ N(mean_f, sd_f^2) on the nodes of the
    rule for N(0, base_sd^2): the nodes' weights times the ratio of the two densities at each
    node. Where mean_f is 0 and sd_f is base_sd the ratio is exactly one. Nodes on which a field's
    prior is not whole are refused (rule.check_prior_held): the trapezoid of the default reach
    holds a known height's prior only from 161 to 175 cm."""
    mean, sd = np.asarray(mean, float), np.asarray(sd, float)
    t = np.asarray(nodes_log_s, float)[None, :]
    m, s = mean[:, None], sd[:, None]
    same = (m == 0.0) & (s == base_sd)
    ratio = (-0.5 * ((t - m) / s) ** 2 - np.log(s)) - (-0.5 * (t / base_sd) ** 2 - math.log(base_sd))
    out = np.asarray(logw, float)[None, :] + np.where(same, 0.0, ratio)
    check_prior_held(out, t[0], lambda: (mean, sd))
    return out


def _table_part(mu, sd, idx, sizes, rho, noise):
    """The table's side of the closed form, (M, 3B, 4JH): what each field's sums multiply, a
    function of the table, the sizes and the hypotheses alone, as rule.table_blocks is."""
    import pytensor.tensor as pt
    muk = mu[:, idx][:, None]                                   # (M, 1, H, B)
    sdk = sd[:, idx][:, None]
    s = sizes[:, :, None, None]                                 # (M, J, 1, 1)
    delta = s * s * (1.0 - rho * rho) * sdk * sdk + (noise * noise)[:, None, None, None]   # (M, J, H, B)
    d = 1.0 / delta
    u = s * rho * sdk
    sm = s * muk
    # the four sums of the closed form as one matrix per measure: rows x^2, x, w per body,
    # columns q1, q2, a, ld, each over (J, H)
    zero = pt.zeros_like(d)
    col_x2 = [d, zero, zero, zero]
    col_x = [-2.0 * sm * d, u * d, zero, zero]
    col_w = [sm * sm * d, -sm * u * d, u * u * d, pt.log(delta)]

    def block(cols):
        # (M, 4, J, H, B) -> (M, B, 4 * J * H)
        st = pt.stack(cols, axis=1)
        return st.transpose(0, 4, 1, 2, 3).reshape((st.shape[0], st.shape[4], -1))

    return pt.concatenate([block(col_x2), block(col_x), block(col_w)], axis=1)     # (M, 3B, 4JH)


def _field_part(x, w, blocks, J, H, logw, log_prior, masks):
    """The fields' side: their sums against the table's blocks, the closed form, the size
    integrated out and the hypotheses normalised; log evidence (R, F, H) and the posterior."""
    import pytensor.tensor as pt
    left = pt.concatenate([x * x, x, w], axis=2).dimshuffle(1, 0, 2)               # (M, F, 3B)
    sums = pt.matmul(left, blocks)                                                  # (M, F, 4JH)
    sums = sums.reshape((sums.shape[0], sums.shape[1], 4, J, H))
    q1, q2, a, ld = sums[:, :, 0], sums[:, :, 1], sums[:, :, 2], sums[:, :, 3]
    n_eff = w.sum(axis=2).T[:, :, None, None]                                       # (M, F, 1, 1)
    ll = -0.5 * (q1 - q2 * q2 / (1.0 + a) + ld + pt.log1p(a) + n_eff * LOG2PI)     # (M, F, J, H)
    per = pt.tensordot(masks, ll, axes=[[1], [0]])                                  # (R, F, J, H)
    logev = pt.logsumexp(per + logw[None, :, :, None], axis=2)                      # (R, F, H)
    a_post = logev + log_prior[None, None, :]
    post = pt.exp(a_post - pt.logsumexp(a_post, axis=2, keepdims=True))
    return [logev, post]


def _table_inputs():
    import pytensor.tensor as pt
    return [pt.matrix("mu"),            # (M, L)
            pt.matrix("sd"),            # (M, L)
            pt.lmatrix("idx"),          # (H, B)
            pt.matrix("sizes"),         # (M, J): each measure's power of each node's size
            pt.scalar("rho"),
            pt.vector("noise")]         # (M,), each measure's own error


def _field_inputs():
    import pytensor.tensor as pt
    return [pt.tensor3("x"),            # (F, M, B), zero where not read
            pt.tensor3("w"),            # (F, M, B), 1 where read, 0 where not
            pt.matrix("logw"),          # (F, J)
            pt.vector("log_prior"),     # (H,)
            pt.matrix("masks")]         # (R, M): which measures each answer uses


def _graph():
    """The symbolic rule: inputs and the two outputs, log evidence (R, F, H) and the posterior."""
    mu, sd, idx, sizes, rho, noise = _table_inputs()
    x, w, logw, log_prior, masks = _field_inputs()
    blocks = _table_part(mu, sd, idx, sizes, rho, noise)
    out = _field_part(x, w, blocks, sizes.shape[1], idx.shape[0], logw, log_prior, masks)
    return [x, w, mu, sd, idx, sizes, logw, log_prior, masks, rho, noise], out


_FUNCTION = None
_TABLE = None
_FIELDS = None


def function():
    """The compiled rule, built once per process; PyTensor caches the compiled code on disk."""
    global _FUNCTION
    if _FUNCTION is None:
        import pytensor
        inputs, outputs = _graph()
        _FUNCTION = pytensor.function(inputs, outputs, on_unused_input="ignore")
    return _FUNCTION


def table_function():
    """The table's side alone, compiled once per process: (mu, sd, idx, sizes, rho, noise) to the
    blocks (M, 3B, 4JH), which ExactRule.prepare builds once for a service's hypotheses."""
    global _TABLE
    if _TABLE is None:
        import pytensor
        inputs = _table_inputs()
        _TABLE = pytensor.function(inputs, _table_part(*inputs))
    return _TABLE


def fields_function():
    """The fields' side alone, compiled once per process: (x, w, blocks, J, H, logw, log_prior,
    masks) to the log evidence and the posterior, given blocks prepared beforehand."""
    global _FIELDS
    if _FIELDS is None:
        import pytensor
        import pytensor.tensor as pt
        x, w, logw, log_prior, masks = _field_inputs()
        blocks, J, H = pt.tensor3("blocks"), pt.lscalar("J"), pt.lscalar("H")
        _FIELDS = pytensor.function([x, w, blocks, J, H, logw, log_prior, masks],
                                    _field_part(x, w, blocks, J, H, logw, log_prior, masks))
    return _FIELDS


class ExactRule:
    """The exact rule over a table, compiled: `evaluate` scores fields under hypotheses and
    returns the log evidence and the posterior for every subset of measures asked."""

    def __init__(self, mu: np.ndarray, sd: np.ndarray, synth: dict = SYNTH, n_nodes: int = GH_NODES,
                 noise: Optional[np.ndarray] = None, power: Optional[np.ndarray] = None,
                 nodes: Optional[Tuple[np.ndarray, np.ndarray]] = None):
        self.mu = np.ascontiguousarray(mu, float)
        self.sd = np.ascontiguousarray(sd, float)
        if self.mu.shape != self.sd.shape or self.mu.ndim != 2:
            raise ValueError("the table is (measures, levels): mu %r, sd %r" % (self.mu.shape, self.sd.shape))
        M = self.mu.shape[0]
        # each measure's own error, synth's noise_mm for every one by default, as in rule.py
        self.noise = np.full(M, float(synth["noise_mm"])) if noise is None else np.ascontiguousarray(noise, float)
        if self.noise.shape != (M,):
            raise ValueError("one error per measure: %d measures, noise %r" % (M, self.noise.shape))
        self.synth = dict(synth)
        # rule.py's nodes, Gauss-Hermite by default or the ones given (rule.trapezoid), and each
        # measure's power of each node's size, the size itself for a length
        self.sizes, self.logw = quadrature(float(synth["scale_sd"]), n_nodes) if nodes is None else \
            (np.asarray(nodes[0], float), np.asarray(nodes[1], float))
        self.power = np.ones(M) if power is None else np.asarray(power, float)
        self.scaled = np.ascontiguousarray(size_factors(self.sizes, self.power, M))
        self.f = function()

    @property
    def n_levels(self) -> int:
        return self.mu.shape[1]

    def prepare(self, hyp: Hypotheses) -> np.ndarray:
        """The table's blocks under these hypotheses, (measures, 3 x bodies, 4 x nodes x
        hypotheses), built once, as a service builds rule.table_blocks once for a pattern of
        offsets; evaluate given them computes only the fields' side."""
        if hyp.n_levels != self.n_levels:
            raise ValueError("the hypotheses are for %d levels, the table has %d" % (hyp.n_levels, self.n_levels))
        idx = np.ascontiguousarray(hyp.levels, np.int64)
        return table_function()(self.mu, self.sd, idx, self.scaled, float(self.synth["rho"]), self.noise)

    def evaluate(self, X: np.ndarray, hyp: Hypotheses, subsets: Optional[Dict[str, Sequence[int]]] = None,
                 log_prior: Optional[np.ndarray] = None, logw: Optional[np.ndarray] = None,
                 factors: Optional[np.ndarray] = None, chunk: int = CHUNK,
                 prepared: Optional[np.ndarray] = None) -> Dict[str, Dict[str, np.ndarray]]:
        """{subset: {"logev": (F, H), "post": (F, H)}} for X (fields, measures, bodies) with NaN
        where a value was not read. `logw` (F, J) overrides the size prior field by field
        (size_log_weights); `log_prior` (H,) the uniform prior over hypotheses; `factors` (F, M)
        scales each field's table means (CovariateModel.mean_factors), ones by default;
        `prepared`, the blocks prepare(hyp) gave, skips building them, with no factors."""
        X = np.asarray(X, float)
        if X.ndim != 3:
            raise ValueError("X is (fields, measures, bodies), got shape %r" % (X.shape,))
        F, M, B = X.shape
        if M != self.mu.shape[0]:
            raise ValueError("X has %d measures, the table %d" % (M, self.mu.shape[0]))
        if hyp.levels.shape[1] != B:
            raise ValueError("the hypotheses place %d bodies, X has %d" % (hyp.levels.shape[1], B))
        if hyp.n_levels != self.n_levels:
            raise ValueError("the hypotheses are for %d levels, the table has %d" % (hyp.n_levels, self.n_levels))
        H = len(hyp)
        names = ["all"] if subsets is None else list(subsets)
        masks = np.zeros((len(names), M))
        for r, name in enumerate(names):
            masks[r, list(range(M)) if subsets is None else list(subsets[name])] = 1.0
        lp = np.full(H, -math.log(H)) if log_prior is None else np.asarray(log_prior, float)
        if lp.shape != (H,):
            raise ValueError("the prior has %d entries for %d hypotheses" % (lp.size, H))
        lw = np.broadcast_to(self.logw, (F, len(self.logw))) if logw is None else np.asarray(logw, float)
        if lw.shape != (F, len(self.logw)):
            raise ValueError("logw is (fields, nodes) = (%d, %d), got %r" % (F, len(self.logw), lw.shape))
        fac = np.ones((F, M)) if factors is None else np.asarray(factors, float)
        if fac.shape != (F, M):
            raise ValueError("factors is (fields, measures) = (%d, %d), got %r" % (F, M, fac.shape))
        present = np.isfinite(X)
        x0 = np.where(present, X, 0.0)
        w = present.astype(float)
        idx = np.ascontiguousarray(hyp.levels, np.int64)
        logev = np.empty((len(names), F, H))
        post = np.empty((len(names), F, H))
        if prepared is not None:
            if factors is not None:
                raise ValueError("prepared blocks hold the table's means unscaled: give no factors with them")
            J = len(self.logw)
            if prepared.shape != (M, 3 * B, 4 * J * H):
                raise ValueError("prepared blocks are (%d, %d, %d), got %r" % (M, 3 * B, 4 * J * H, prepared.shape))
            ff = fields_function()
            for c0 in range(0, F, max(1, chunk)):
                f = slice(c0, c0 + chunk)
                le, po = ff(np.ascontiguousarray(x0[f]), np.ascontiguousarray(w[f]), prepared, J, H,
                            np.ascontiguousarray(lw[f]), lp, masks)
                logev[:, f] = le
                post[:, f] = po
            return {name: {"logev": logev[r], "post": post[r]} for r, name in enumerate(names)}
        rows, group = np.unique(fac, axis=0, return_inverse=True)
        for g, row in enumerate(rows):
            mu = np.ascontiguousarray(self.mu * row[:, None])
            fields = np.flatnonzero(group.reshape(-1) == g)
            for c0 in range(0, len(fields), max(1, chunk)):
                f = fields[c0:c0 + chunk]
                le, po = self.f(np.ascontiguousarray(x0[f]), np.ascontiguousarray(w[f]), mu, self.sd, idx,
                                self.scaled, np.ascontiguousarray(lw[f]), lp, masks,
                                float(self.synth["rho"]), self.noise)
                logev[:, f] = le
                post[:, f] = po
        return {name: {"logev": logev[r], "post": post[r]} for r, name in enumerate(names)}

    def name(self, X: np.ndarray, offsets: Sequence[int], subsets: Optional[Dict[str, Sequence[int]]] = None,
             log_prior: Optional[np.ndarray] = None, logw: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
        """rule.name's answer: the posterior over places for one known pattern of offsets."""
        hyp = hypotheses(self.n_levels, [offsets])
        out = self.evaluate(X, hyp, subsets, log_prior, logw)
        return {k: v["post"] for k, v in out.items()}


def marginal(post: np.ndarray, hyp: Hypotheses, over: str = "place") -> np.ndarray:
    """The posterior summed over the other part of each hypothesis: over places, (F, n_levels)
    with the mass of every pattern that starts there; over patterns, (F, patterns)."""
    post = np.asarray(post, float)
    if over == "place":
        out = np.zeros((post.shape[0], hyp.n_levels))
        np.add.at(out.T, hyp.place, post.T)
        return out
    if over == "pattern":
        out = np.zeros((post.shape[0], len(hyp.patterns)))
        np.add.at(out.T, hyp.pattern, post.T)
        return out
    raise ValueError("over is place or pattern, not %r" % over)
