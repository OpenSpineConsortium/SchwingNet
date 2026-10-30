"""The exact Bayes rule over places, vectorised: fields, places, measures and nodes at once.

The model is the archive's (archive/bordercall/exact.py, its docstring): a field of bodies at
known offsets o_1 < ... < o_B from its first body sits at one of K = L - o_B places in a column
of L levels, and given the place and the patient's size s each length measure's values are
jointly normal with mean s mu and covariance Delta + u u' (Delta diagonal, u = s rho sd), so
the log density has the Sherman-Morrison closed form; the size is integrated out by
Gauss-Hermite quadrature over log s ~ N(0, scale_sd^2), the measures multiply, and a uniform
prior over places gives the posterior. Two things are new here and leave the contiguous,
complete case unchanged but for rounding (the log likelihoods agree with exact.py's to about
1e-11, the posteriors to 1e-13):

- gaps: the bodies' offsets index the table, (0, 1, 2) for three consecutive bodies, (0, 2, 4)
  for every other body, so the places are the starts at which the last offset still fits;
- missing values: a value that is NaN drops out of its measure's sums with weight zero. On any
  subset of bodies the covariance keeps the form Delta + u u' on that subset, so the weighted
  sums are the exact marginal likelihood; a measure missing on every body contributes a
  constant and a field with nothing gets the prior back.

Each measure has its own measurement error, `noise` (one value per measure, in its own units,
measures.errors gives the selected measures'), and synth's noise_mm, the archive's 1 mm, stands
in for every measure when none is given; with 1 mm for every measure the two are the same to the
bit.

Each measure scales with its own power of the size, `power` (measures.powers: 1 for a length, 2
for an area, 0 for an angle; TODO.md, item P step 4): wherever the archive's closed form has s,
a measure's has s^p, so its mean is s^p mu, its spread s^p sd and its error unscaled. With every
power 1, the default, the factor is the size itself and the answers are those of the rule before
step e to the bit, and so the archive's within the 1e-11 above.

The size is integrated over log s ~ N(0, scale_sd^2) by the archive's 161-node Gauss-Hermite rule
by default (`quadrature`), or by the trapezoid rule on an even grid of log s (`trapezoid`), which
`name` takes as `nodes` and `loglik` as its `sizes`. The trapezoid's grid holds N(0, scale_sd^2)
whole, but not a field's own prior once a known height moves and widens it, and the compiled rule
and the naming model refuse nodes that cut a field's prior off (check_prior_held). The more
measures a field has, the narrower the posterior of its size, and once that is about as narrow as
the Gauss-Hermite nodes are apart near the middle (0.017 in log s) their sum drifts from the
integral. With all 32 measures of the pool on 40 typical columns (examples/quadrature_check.py,
seed 1234), the posterior SD of log s at the true place was 0.018 to 0.027 at one body, 0.014 to
0.018 at three and 0.011 to 0.013 at nine; the Gauss-Hermite log evidence at the true place was
off by at most 3.4e-10, 1.1e-5 and 6.9e-4, and the posterior over places by at most 6e-11, 1e-7
and 1e-12, since the error is nearly the same at every place that matters. The trapezoid rule on
an even grid of a smooth bump converges faster than any power of its step, so a step of 0.004 in
log s, about a third of the narrowest SD measured, agreed with a grid four times as fine to
3.4e-13 in the log evidence at the true place and 1.4e-14 in the posterior over places (the tests
hold it to a grid twice as fine). At places far from the truth the values ask for a size far out
in the prior's tail, past the trapezoid's grid of 8 prior SDs, where the node at the grid's edge
takes the whole sum, so that every trapezoid grid of that reach, the finer one included, falls
short of the log evidence by up to hundreds there, while the Gauss-Hermite rule, whose outermost
node lies at 24 prior SDs, reaches the size asked for: against the closed form summed on a grid of
step 0.0005 out to 40 prior SDs, at the three places of each width where the two rules part most,
Gauss-Hermite was off by at most 2.7e-3, the trapezoid by up to 693 and the grid four times as
fine by up to 694 (examples/quadrature_check.py). Those places hold too little of the posterior
for either to matter, which is why the errors of the posterior above are over every place and
those of the log evidence at the true place. The build-up study of step e is to integrate on the
trapezoid throughout, since a table estimated from a few people can narrow the posterior further.

Every sum over bodies is one batched matrix product, (measures, fields, bodies) by (measures,
bodies, nodes x places), so no Python loop runs per field, per place or per body. Fields are
scored in chunks only to bound memory (loglik keeps (fields, nodes, measures, places) doubles).
"""
from __future__ import annotations

import math
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy as np

GH_NODES = 161
TRAPEZOID_STEP = 0.004      # in log s: about a third of the narrowest posterior SD of log s 32 measures gave
TRAPEZOID_REACH = 8.0       # the grid's half-width in SDs of N(0, scale_sd^2), whose mass beyond it is 1e-15
PRIOR_HELD = 1e-12          # in log mass: how far from the whole of a field's own size prior its nodes may hold
LOG2PI = math.log(2.0 * math.pi)
SYNTH = {"rho": 0.5, "noise_mm": 1.0, "scale_sd": 0.07}      # the archive's generator settings


def quadrature(scale_sd: float, n_nodes: int = GH_NODES) -> Tuple[np.ndarray, np.ndarray]:
    """Sizes and log weights for integrating over log s ~ N(0, scale_sd^2); one node when there
    is no size spread, since then s is 1. The archive's, unchanged."""
    if scale_sd <= 0:
        return np.ones(1), np.zeros(1)
    x, w = np.polynomial.hermite.hermgauss(n_nodes)
    return np.exp(math.sqrt(2.0) * scale_sd * x), np.log(w / math.sqrt(math.pi))


def trapezoid(scale_sd: float, step: float = TRAPEZOID_STEP, reach: float = TRAPEZOID_REACH) -> Tuple[np.ndarray, np.ndarray]:
    """Sizes and log weights for integrating over log s ~ N(0, scale_sd^2) by the trapezoid rule
    on an even grid of log s from -reach to reach prior SDs, the step given or the nearest finer
    one that fits the grid evenly, the weights the prior's density times the step, normalised to
    sum to one so that a field with nothing read gets the prior back exactly; one node when there
    is no size spread, since then s is 1."""
    if scale_sd <= 0:
        return np.ones(1), np.zeros(1)
    half = reach * scale_sd
    n = int(math.ceil(2.0 * half / step - 1e-9)) + 1
    t = np.linspace(-half, half, n)
    logw = -0.5 * (t / scale_sd) ** 2
    logw -= logsumexp(logw[None, :], 1)[0]
    return np.exp(t), logw


def check_prior_held(log_weights: np.ndarray, nodes_log_s: np.ndarray,
                     priors: Callable[[], Tuple[np.ndarray, np.ndarray]]) -> None:
    """Refuse, with ValueError, nodes on which a field's own size prior does not sum to one within
    PRIOR_HELD in log mass, log_weights (fields, nodes) being each field's weights on them. The
    nodes are built for N(0, scale_sd^2), and a field's own prior, as a known height makes it, is
    moved and widened, so that the trapezoid's grid, which ends TRAPEZOID_REACH of the nodes' SDs
    out, cuts it off where a tall or a short patient's size lies, and the integral over the size is
    wrong there, while the Gauss-Hermite nodes, whose outermost lie 24 SDs out, still hold it. With
    covariates.py's settings the trapezoid of the default reach holds the prior of a height from 161
    to 175 cm only, one of reach 30 from 108 to 262 cm and the Gauss-Hermite nodes from 117 to
    242 cm. `priors` gives every field's prior, the mean and SD of log s, and is called only to word
    the refusal."""
    held = logsumexp(np.asarray(log_weights, float), 1)
    off = np.flatnonzero(~(np.abs(held) <= PRIOR_HELD))
    if off.size == 0:
        return
    f = int(off[np.argmax(np.nan_to_num(np.abs(held[off]), nan=np.inf))])
    mean, sd = priors()
    t = np.asarray(nodes_log_s, float)
    raise ValueError("the nodes of the size, from log s %.3f to %.3f, hold a log mass of %.3g of field %d's size prior "
                     "N(%.4f, %.4f^2), and %d of %d fields' priors are more than %g from whole on them in log mass: "
                     "widen the grid (rule.trapezoid's reach) or integrate on the Gauss-Hermite nodes"
                     % (t.min(), t.max(), float(held[f]), f, mean[f], sd[f], off.size, held.size, PRIOR_HELD))


def size_factors(sizes: np.ndarray, power: Optional[np.ndarray], n_measures: int) -> np.ndarray:
    """s^p for every measure's power p and every quadrature size, (measures, nodes): the size
    itself, to the bit, where p is 1 (every measure when no power is given), its square where p
    is 2 and one where p is 0."""
    s = np.asarray(sizes, float)[None, :]
    p = np.ones(n_measures) if power is None else np.asarray(power, float)
    if p.shape != (n_measures,):
        raise ValueError("power is one power of the size per measure, %d of them; got %r" % (n_measures, p))
    p = p[:, None]
    out = np.power(s, p)
    out = np.where(p == 2.0, s * s, out)
    out = np.where(p == 1.0, s, out)
    return np.where(p == 0.0, 1.0, out)


def places_of(n_levels: int, offsets: Sequence[int]) -> int:
    """How many starts a field with these offsets has in a column of n_levels."""
    offsets = np.asarray(offsets, int)
    if offsets.ndim != 1 or len(offsets) == 0:
        raise ValueError("a field needs at least one body")
    if offsets[0] != 0 or np.any(np.diff(offsets) <= 0):
        raise ValueError("offsets start at 0 and increase: %r" % (list(offsets),))
    k = n_levels - int(offsets[-1])
    if k <= 0:
        raise ValueError("a field spanning %d bodies does not fit a column of %d" % (int(offsets[-1]) + 1, n_levels))
    return k


def errors_of(synth: dict, n_measures: int, noise: Optional[np.ndarray] = None) -> np.ndarray:
    """Each measure's measurement error: the one given, else synth's noise_mm for every measure."""
    if noise is None:
        return np.full(n_measures, float(synth["noise_mm"]))
    noise = np.asarray(noise, float)
    if noise.shape != (n_measures,) or not np.all(noise > 0):
        raise ValueError("noise is one positive error per measure, %d of them; got %r" % (n_measures, noise))
    return noise


def table_blocks(offsets: Sequence[int], mu: np.ndarray, sd: np.ndarray, synth: dict, sizes: np.ndarray,
                 noise: Optional[np.ndarray] = None, power: Optional[np.ndarray] = None) -> np.ndarray:
    """Everything the likelihood needs from the table, the sizes and the offsets, as one matrix
    per measure that the fields' sums multiply: (measures, 3 bodies, 4, places, nodes). The three
    row blocks are what each field supplies per body, x^2, x and the weight w (1 where the value
    is read, 0 where it is NaN); the four column blocks are the sums the closed form takes:

        q1 = sum w (x - s mu)^2 d        from x^2 d, -2 x s mu d, w s^2 mu^2 d
        q2 = sum w (x - s mu) u d        from x u d, -w s mu u d
        a  = sum w u^2 d                 from w u^2 d
        ld = sum w log Delta             from w log Delta

    with d = 1/Delta, Delta = s^2 (1 - rho^2) sd^2 + noise^2 and u = s rho sd at the body's
    level under each place, noise the measure's own error and s, for a measure whose power of the
    size is not 1, s^p (size_factors)."""
    offsets = np.asarray(offsets, int)
    M, L = mu.shape
    K = places_of(L, offsets)
    B = len(offsets)
    J = len(sizes)
    rho = float(synth["rho"])
    noise = errors_of(synth, M, noise)[:, None, None, None]            # (M, 1, 1, 1)
    idx = np.arange(K)[:, None] + offsets[None, :]                     # (K, B)
    muk, sdk = mu[:, idx], sd[:, idx]                                   # (M, K, B)
    s = size_factors(sizes, power, M)[:, :, None, None]                 # (M, J, 1, 1)
    muk, sdk = muk[:, None], sdk[:, None]                               # (M, 1, K, B)
    delta = s * s * (1.0 - rho * rho) * sdk * sdk + noise * noise       # (M, J, K, B)
    d = 1.0 / delta
    u = s * rho * sdk
    sm = s * muk
    blocks = np.zeros((M, 3, B, 4, J, K))
    put = lambda row, col, v: blocks.__setitem__((slice(None), row, slice(None), col), np.transpose(v, (0, 3, 1, 2)))
    put(0, 0, d)                                # x^2 -> q1
    put(1, 0, -2.0 * sm * d)                    # x   -> q1
    put(2, 0, sm * sm * d)                      # w   -> q1
    put(1, 1, u * d)                            # x   -> q2
    put(2, 1, -sm * u * d)                      # w   -> q2
    put(2, 2, u * u * d)                        # w   -> a
    put(2, 3, np.log(delta))                    # w   -> ld
    return blocks.reshape(M, 3 * B, 4 * J * K)


BLOCK = 32          # fields per matrix product: the sums of 32 fields fit the cache, 2,000 do not


def loglik(X: np.ndarray, offsets: Sequence[int], mu: np.ndarray, sd: np.ndarray, synth: dict = SYNTH,
           n_nodes: int = GH_NODES, sizes: Optional[np.ndarray] = None,
           blocks: Optional[np.ndarray] = None, block: int = BLOCK, noise: Optional[np.ndarray] = None,
           power: Optional[np.ndarray] = None) -> np.ndarray:
    """Per-measure log likelihood of every field at every place and quadrature size:
    (fields, places, measures, nodes). X is (fields, measures, bodies) with NaN for a value not
    read; mu and sd are the table's means and population SDs, (measures, levels); noise is each
    measure's error (synth's noise_mm for every one when it is not given) and power each one's
    power of the size (1 for every one when it is not given). One batched
    matrix product does every sum over bodies for every field, place, measure and node; the
    fields go through it `block` at a time only because the product's four sums for 2,000
    fields are 700 MB, which is slower to write than to compute (the block is a cache size,
    not a loop over fields: the same product with the same result at any block)."""
    X = np.asarray(X, float)
    if X.ndim != 3:
        raise ValueError("X is (fields, measures, bodies), got shape %r" % (X.shape,))
    F, M, B = X.shape
    offsets = np.asarray(offsets, int)
    if len(offsets) != B:
        raise ValueError("%d offsets for %d bodies" % (len(offsets), B))
    if mu.shape != sd.shape or mu.shape[0] != M:
        raise ValueError("the table is (measures, levels): mu %r, sd %r, X has %d measures" % (mu.shape, sd.shape, M))
    K = places_of(mu.shape[1], offsets)
    if sizes is None:
        sizes, _ = quadrature(synth["scale_sd"], n_nodes)
    J = len(sizes)
    if blocks is None:
        blocks = table_blocks(offsets, mu, sd, synth, sizes, noise, power)
    out = np.empty((F, K, M, J))
    for f0, f1, ll in loglik_blocks(X, blocks, J, K, block):
        out[f0:f1] = np.transpose(ll, (1, 3, 0, 2))                      # (f, K, M, J)
    return out


def loglik_blocks(X: np.ndarray, blocks: np.ndarray, n_nodes: int, n_places: int, block: int = BLOCK):
    """loglik's arithmetic, block by block of fields, in the order the matrix product gives it:
    (f0, f1, ll) with ll the log likelihood of fields f0 to f1 as (measures, fields, nodes,
    places), the layout in which a sum over measures is cheapest, which loglik turns round to (fields,
    places, measures, nodes)."""
    F, M, B = X.shape
    J, K = n_nodes, n_places
    present = np.isfinite(X)
    w = present.astype(float)
    x = np.where(present, X, 0.0)
    left = np.ascontiguousarray(np.transpose(np.concatenate([x * x, x, w], axis=2), (1, 0, 2)))   # (M, F, 3B)
    n_eff = w.sum(2).T                                                   # (M, F)
    for f0 in range(0, F, max(1, block)):
        f1 = min(F, f0 + block)
        sums = np.matmul(left[:, f0:f1], blocks).reshape(M, f1 - f0, 4, J, K)
        q1, q2, a, ld = sums[:, :, 0], sums[:, :, 1], sums[:, :, 2], sums[:, :, 3]
        yield f0, f1, -0.5 * (q1 - q2 * q2 / (1.0 + a) + ld + np.log1p(a) + n_eff[:, f0:f1, None, None] * LOG2PI)


def logsumexp(a: np.ndarray, axis: int) -> np.ndarray:
    top = np.max(a, axis=axis, keepdims=True)
    return np.squeeze(top, axis) + np.log(np.exp(a - top).sum(axis))


def log_evidence(LL: np.ndarray, logw: np.ndarray, measures: Optional[Sequence[int]] = None) -> np.ndarray:
    """log p(field | place) over the measures named (all by default), the size integrated out:
    (fields, places)."""
    part = LL if measures is None else LL[:, :, list(measures), :]
    return logsumexp(part.sum(2) + logw, axis=2)


def posterior(logev: np.ndarray, log_prior: Optional[np.ndarray] = None) -> np.ndarray:
    """The posterior over places, uniform beforehand unless a prior is given."""
    a = logev if log_prior is None else logev + log_prior
    p = np.exp(a - a.max(1, keepdims=True))
    return p / p.sum(1, keepdims=True)


def name(X: np.ndarray, offsets: Sequence[int], mu: np.ndarray, sd: np.ndarray, synth: dict = SYNTH,
         n_nodes: int = GH_NODES, log_prior: Optional[np.ndarray] = None,
         subsets: Optional[Dict[str, Sequence[int]]] = None, chunk: int = 2000,
         noise: Optional[np.ndarray] = None, power: Optional[np.ndarray] = None,
         nodes: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> Dict[str, np.ndarray]:
    """The posterior over places for every field, (fields, places), under every named subset of
    the measures (all of them under the key `all` when none is named), chunk by chunk; noise is
    each measure's error, synth's noise_mm for every one by default, power each one's power of
    the size, 1 by default, and nodes the sizes and log weights of the quadrature, the archive's
    Gauss-Hermite rule of n_nodes by default (`trapezoid` gives the other)."""
    X = np.asarray(X, float)
    sizes, logw = quadrature(synth["scale_sd"], n_nodes) if nodes is None else nodes
    keys = {"all": list(range(X.shape[1]))} if subsets is None else {k: list(v) for k, v in subsets.items()}
    parts: Dict[str, list] = {k: [] for k in keys}
    for c0 in range(0, X.shape[0], chunk):
        LL = loglik(X[c0:c0 + chunk], offsets, mu, sd, synth, sizes=sizes, noise=noise, power=power)
        for k, idx in keys.items():
            parts[k].append(posterior(log_evidence(LL, logw, idx), log_prior))
    return {k: np.concatenate(v) if v else np.zeros((0, places_of(mu.shape[1], offsets))) for k, v in parts.items()}


def dense_loglik(X: np.ndarray, offsets: Sequence[int], mu: np.ndarray, sd: np.ndarray, synth: dict,
                 sizes: np.ndarray, noise: Optional[np.ndarray] = None, power: Optional[np.ndarray] = None) -> np.ndarray:
    """The same density by a dense multivariate normal on the bodies present, measure by measure
    and field by field: slow, independent of the closed form, kept for the tests."""
    from scipy.stats import multivariate_normal
    X = np.asarray(X, float)
    F, M, B = X.shape
    offsets = np.asarray(offsets, int)
    K = places_of(mu.shape[1], offsets)
    rho, errors = synth["rho"], errors_of(synth, M, noise)
    p = np.ones(M) if power is None else np.asarray(power, float)
    out = np.zeros((F, K, M, len(sizes)))
    for f in range(F):
        for k in range(K):
            for m in range(M):
                keep = np.isfinite(X[f, m])
                if not keep.any():
                    continue
                lv = k + offsets[keep]
                for j, s in enumerate(sizes):
                    g = s ** p[m]
                    sdv = g * sd[m, lv]
                    cov = rho * rho * np.outer(sdv, sdv) + np.diag((1.0 - rho * rho) * sdv * sdv + errors[m] ** 2)
                    out[f, k, m, j] = multivariate_normal(mean=g * mu[m, lv], cov=cov).logpdf(X[f, m, keep])
    return out


def credible_sets(post: np.ndarray, level: float = 0.99) -> Tuple[np.ndarray, np.ndarray]:
    """The smallest set of places holding `level` of the posterior: its size, and each place's
    membership (fields, places). The archive's."""
    order = np.argsort(-post, axis=1)
    sp = np.take_along_axis(post, order, axis=1)
    before = np.cumsum(sp, axis=1) - sp
    keep_sorted = before < level
    member = np.zeros_like(post, bool)
    np.put_along_axis(member, order, keep_sorted, axis=1)
    return keep_sorted.sum(1), member
