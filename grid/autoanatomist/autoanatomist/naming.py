"""The chain of levels as a differentiable naming layer, in JAX.

This is schwingcheck/chain.py's model made a layer a network can be trained through: given a
field of B bodies read in order down a column, each with its measurements, the posterior of each
body's name and of the column's type, and the gradient of anything computed from them with
respect to the measurements. chain.py is the reference, and the tests hold this module to it
within 1e-9 in float64 wherever the two describe the same model.

What it adds to chain.py:

- a fourth type, four_lumbar (C3 to L4, the sacralized column: schwingcheck.columns' phenotype of
  that name, whose profiles are the typical column's), beside typical, six_lumbar and t13. Its
  bodies read the typical column's names with the typical column's values, so on a field that
  shows neither end of the column it changes the prior alone;
- anchors: `top`, the field's first body is the column's first level (C3, the body under C2), and
  `bottom`, its last body is the column's last (the body on the sacrum), each a condition put on
  the chain by the same h-transform that conditions it on fitting. Under the bottom anchor a
  sacralized column's last body is L4, a six-lumbar column's L6 and a typical one's L5, so the
  values can tell the three apart; neither anchor is on unless asked for;
- the exact answer in JAX (path_logev): rule.py's closed form for every name path and every node
  of the size, summed in log space and differentiable in the measurements, with each value's own
  error where one is given (a network's uncertainty about its own measurement), not only each
  measure's; and
- the forward pass with a temperature gamma (soft_forward), smax_gamma(x) = gamma logsumexp(x /
  gamma) in place of logsumexp: gamma 1 is the forward algorithm, whose value is the log
  evidence and whose gradient in the emissions is every body's state marginals, the
  forward-backward algorithm by automatic differentiation; gamma towards 0 is the Viterbi
  algorithm, whose value is the best path's score and whose gradient is that path (Mensch and
  Blondel, Differentiable dynamic programming for structured prediction and attention, ICML 2018).
  The forward pass needs emissions that factor along the chain, which the model's do given the
  size and each measure's shared offset (state_loglik). With rho 0 there is no shared offset, and
  the pass run at each node of the size and summed over the nodes is exact (forward_logev), which
  the tests hold to the enumeration at rho 0; at the model's rho of 0.5 only the enumeration is.

The weights, the step law and its cut are chain.py's stated choices (chain.WEIGHTS, SKIP,
MAX_STEP); four_lumbar's weight, 0.05 like each other variant's, is this module's choice, and the
weights are renormalised over the types a chain is built with, so chain.py's three types keep
chain.py's weights exactly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import jax
import jax.numpy as jnp
import numpy as np

from schwingcheck import chain as CH
from schwingcheck import columns as C
from schwingcheck import measures as MS
from schwingcheck import rule as R

from .specs import SEVEN

TYPES = ("typical", "four_lumbar", "six_lumbar", "t13")
NAMES = list(CH.NAMES)                      # C3 to L5, then L6 and T13: chain.py's names, in its order
NAME_INDEX = dict(CH.NAME_INDEX)
WEIGHTS = dict(CH.WEIGHTS, four_lumbar=0.05)
NEG = -1e30                                 # log of an impossible move: finite, so no gradient is 0 * inf


# ---- the chain, in NumPy, as chain.build makes it, with a fourth type and the anchors ----------

def type_levels(kind: str):
    """The level names down a column of this type, as schwingcheck.columns lays it out."""
    if kind not in TYPES:
        raise ValueError("the naming layer's types are %r, not %r" % (TYPES, kind))
    return list(C.phenotype_levels(kind)[0])


def fit(n: int, steps: np.ndarray, B: int, bottom: bool = False) -> np.ndarray:
    """h (B, n): the step law's probability that a path at position p after body t still fits
    the column with its remaining bodies, and ends on the column's last level under the bottom
    anchor (chain._fit when bottom is off)."""
    h = np.zeros((B, n))
    if bottom:
        h[B - 1, n - 1] = 1.0
    else:
        h[B - 1] = 1.0
    for t in range(B - 2, -1, -1):
        for k, g in enumerate(steps, start=1):
            h[t, :n - k] += g * h[t + 1, k:]
    return h


@dataclass(frozen=True)
class Chain:
    """chain.Chain's fields and the two anchors: the states (type, position, name), the start law
    init (S,) and the transitions P (n_bodies - 1, S, S), block diagonal by type."""
    types: Tuple[str, ...]
    weights: Tuple[float, ...]
    steps: Tuple[float, ...]
    n_bodies: int
    top: bool
    bottom: bool
    state_type: np.ndarray
    state_pos: np.ndarray
    state_name: np.ndarray
    init: np.ndarray
    P: np.ndarray

    @property
    def n_states(self) -> int:
        return len(self.state_type)


def _weights(types: Tuple[str, ...], weights: Optional[Sequence[float]]) -> np.ndarray:
    w = np.array([WEIGHTS[t] for t in types] if weights is None else weights, float)
    if w.shape != (len(types),) or np.any(w <= 0):
        raise ValueError("one positive weight per type: %r for %r" % (list(w), types))
    return w / w.sum()


def _steps(steps: Sequence[float]) -> np.ndarray:
    g = np.asarray(steps, float)
    if g.ndim != 1 or len(g) == 0 or np.any(g < 0) or abs(g.sum() - 1.0) > 1e-12:
        raise ValueError("steps is a law over 1 to K: %r" % (list(g),))
    return g


def _type_block(n: int, g: np.ndarray, B: int, top: bool, bottom: bool, kind: str):
    """One type's starts, each with the probability that its field fits (normalised in build, as
    chain.build normalises them), and its transitions (B - 1, n, n)."""
    h = fit(n, g, B, bottom)
    start = h[0] * (np.arange(n) == 0) if top else h[0]
    if start.sum() <= 0:
        raise ValueError("no field of %d bodies fits a %s column%s" % (B, kind, " under the anchors" if top or bottom else ""))
    Pt = np.zeros((max(B - 1, 0), n, n))
    for t in range(B - 1):
        for p in range(n):
            if h[t, p] <= 0:
                Pt[t, p, p] = 1.0           # a state no fitting path reaches at t: any row will do
                continue
            for k, gk in enumerate(g, start=1):
                if p + k < n:
                    Pt[t, p, p + k] = gk * h[t + 1, p + k] / h[t, p]
    return start, Pt


def build(types: Sequence[str] = TYPES, weights: Optional[Sequence[float]] = None,
          steps: Sequence[float] = (1.0,), n_bodies: int = 3, top: bool = False,
          bottom: bool = False) -> Chain:
    """The chain for fields of n_bodies over these types, chain.build's construction with the
    anchors put in by the h-transform: the last body's fit is the column's last level under
    `bottom`, and the start is the column's first level under `top`."""
    types = tuple(types)
    g, w, B = _steps(steps), _weights(types, weights), int(n_bodies)
    if B < 1:
        raise ValueError("a field has at least one body")
    st, sp, sn, init, blocks = [], [], [], [], []
    for ti, kind in enumerate(types):
        names = type_levels(kind)
        start, Pt = _type_block(len(names), g, B, top, bottom, kind)
        st += [ti] * len(names)
        sp += list(range(len(names)))
        sn += [NAME_INDEX[x] for x in names]
        init.append(w[ti] * start / start.sum())
        blocks.append(Pt)
    S = len(st)
    P = np.zeros((max(B - 1, 0), S, S))
    o = 0
    for Pt in blocks:
        n = Pt.shape[1]
        P[:, o:o + n, o:o + n] = Pt
        o += n
    return Chain(types=types, weights=tuple(w.tolist()), steps=tuple(g.tolist()), n_bodies=B, top=bool(top),
                 bottom=bool(bottom), state_type=np.array(st), state_pos=np.array(sp), state_name=np.array(sn),
                 init=np.concatenate(init), P=P)


def paths_of(chain: Chain) -> CH.Paths:
    """The chain's distinct name paths, each with its prior and its types' mass: chain.paths_of,
    which reads only the fields this module's Chain shares with chain.py's."""
    return CH.paths_of(chain)


def log_laws(chain: Chain) -> Tuple[np.ndarray, np.ndarray]:
    """log init (S,) and log P (B - 1, S, S), NEG where a start or a move is impossible."""
    with np.errstate(divide="ignore"):
        return (np.where(chain.init > 0, np.log(chain.init), NEG),
                np.where(chain.P > 0, np.log(chain.P), NEG))


# ---- the exact answer: rule.py's closed form on every name path ----------------------------------

def _per_value(noise, X) -> bool:
    return jnp.ndim(noise) == 3


def path_loglik(X, names, mu_ext, sd_ext, noise, power, sizes, rho):
    """log p(measure m's values | name path h, size node j), (F, M, J, H): rule.py's closed form
    (loglik_blocks) with the bodies' levels read off each path, so

        q1 = sum w (x - s^p mu)^2 / Delta,  q2 = sum w (x - s^p mu) u / Delta,  a = sum w u^2 / Delta,
        ld = sum w log Delta,  Delta = s^2p (1 - rho^2) sd^2 + noise^2,  u = s^p rho sd,

    over the bodies b, w 1 where a value is read and 0 where it is NaN, and the log likelihood is
    -(q1 - q2^2 / (1 + a) + ld + log1p(a) + n log 2 pi) / 2. X is (F, M, B), names (H, B) indices
    into NAMES, mu_ext and sd_ext (M, NAMES), sizes (J,), noise each measure's error (M,) or each
    value's (F, M, B), read only where the value is, so whatever it holds at a NaN value counts
    for nothing. With a measure's error the sums over the bodies are matrix products, as in
    rule.py; with each value's they are taken directly, over arrays of (F, M, J, H, B), which in
    float32 hold 1.2 MB per field at three bodies (H 92), 7.6 MB at five (339), 77 MB at eight
    (2,140) and 1.15 GB at twelve (21,274) with rule.py's 161 nodes, a few of them per field, so a
    long field takes each measure's error, fewer nodes or a smaller batch."""
    X = jnp.asarray(X)
    read = jnp.isfinite(X)
    w = read.astype(X.dtype)
    x = jnp.where(read, X, 0.0)
    s = jnp.power(jnp.asarray(sizes, X.dtype)[None, :], jnp.asarray(power, X.dtype)[:, None])   # (M, J)
    mu = jnp.asarray(mu_ext, X.dtype)[:, names]                                               # (M, H, B)
    sd = jnp.asarray(sd_ext, X.dtype)[:, names]
    noise = jnp.asarray(noise, X.dtype)
    if _per_value(noise, X):
        noise = jnp.where(read, noise, 1.0)
    s_ = s[:, :, None, None]                                                                  # (M, J, 1, 1)
    u = s_ * rho * sd[:, None]                                                                # (M, J, H, B)
    m_ = s_ * mu[:, None]                                                                     # (M, J, H, B)
    spread = s_ * s_ * (1.0 - rho * rho) * sd[:, None] ** 2
    n_eff = w.sum(-1)[:, :, None, None]                                                       # (F, M, 1, 1)
    if _per_value(noise, X):
        delta = spread[None] + (noise ** 2)[:, :, None, None, :]                              # (F, M, J, H, B)
        r = x[:, :, None, None, :] - m_[None]
        wd = w[:, :, None, None, :] / delta
        q1 = jnp.sum(wd * r * r, -1)
        q2 = jnp.sum(wd * r * u[None], -1)
        a = jnp.sum(wd * u[None] ** 2, -1)
        ld = jnp.sum(w[:, :, None, None, :] * jnp.log(delta), -1)
    else:
        delta = spread + (noise ** 2)[:, None, None, None]                                    # (M, J, H, B)
        d = 1.0 / delta
        mm = lambda v, k: jnp.einsum("fmb,mjhb->fmjh", v, k)
        q1 = mm(w * x * x, d) - 2.0 * mm(w * x, m_ * d) + mm(w, m_ * m_ * d)
        q2 = mm(w * x, u * d) - mm(w, m_ * u * d)
        a = mm(w, u * u * d)
        ld = mm(w, jnp.log(delta))
    return -0.5 * (q1 - q2 * q2 / (1.0 + a) + ld + jnp.log1p(a) + n_eff * R.LOG2PI)


def path_logev(X, names, mu_ext, sd_ext, noise, power, nodes, rho=R.SYNTH["rho"],
               measures: Optional[Sequence[int]] = None):
    """log p(field | name path), the size integrated on the nodes (sizes, log weights), (F, H),
    over the measures named (every one by default): chain.path_logev in JAX."""
    sizes, logw = nodes
    ll = path_loglik(X, names, mu_ext, sd_ext, noise, power, sizes, rho)
    if measures is not None:
        ll = ll[:, list(measures)]
    return jax.nn.logsumexp(ll.sum(1) + jnp.asarray(logw, ll.dtype)[None, :, None], axis=1)


def body_posterior(post, names, n_names: int = len(NAMES)):
    """Each body's name posterior (F, B, NAMES) from the path posterior (F, H) and the paths'
    names (H, B)."""
    return jnp.einsum("fh,hbn->fbn", post, jax.nn.one_hot(names, n_names, dtype=post.dtype))


def log_body_posterior(log_path, names, n_names: int = len(NAMES)):
    """The log of each body's name posterior (F, B, NAMES) from the log path posterior (F, H) and
    the paths' names (H, B): the logsumexp over the paths that give body b the name n, so a
    posterior too small for exp in float32 keeps its logarithm and its gradient; NEG + log H where
    no path gives the name."""
    gives = jax.nn.one_hot(names, n_names, dtype=log_path.dtype) > 0                       # (H, B, N)
    terms = jnp.where(gives[None], log_path[:, :, None, None], NEG)                        # (F, H, B, N)
    return jax.nn.logsumexp(terms, axis=1)


# ---- the forward pass with a temperature ---------------------------------------------------------

def smax(x, axis: int, gamma):
    """gamma logsumexp(x / gamma): logsumexp at gamma 1, the maximum as gamma goes to 0. The
    scores are taken about their maximum, and a score NEG below it, whose quotient by a small gamma
    passes float32's range (below a gamma of about 3e-9), is held at NEG, so the pass and its
    gradient stay finite at any gamma."""
    m = jax.lax.stop_gradient(jnp.max(x, axis=axis, keepdims=True))
    z = jnp.maximum((x - m) / gamma, NEG)
    return jnp.squeeze(m, axis=axis) + gamma * jax.nn.logsumexp(z, axis=axis)


def soft_forward(log_e, log_init, logP, gamma=1.0):
    """The smoothed best score over the chain's paths, (...): log_e (..., B, S) the bodies'
    emissions, log_init (S,), logP (B - 1, S, S). At gamma 1 it is log p(field), the forward
    algorithm; its gradient in log_e is each body's state marginals (soft_marginals).

    The loop over the bodies is unrolled, since a field has a handful of them: written as a
    lax.scan, the pass differentiated with gamma under 1 gave an infinite value in float64 on
    JAX 0.12 (the tests hold the unrolled pass to the Viterbi path at gamma 1e-4)."""
    logP = jnp.asarray(logP, log_e.dtype)
    a = log_init + log_e[..., 0, :]
    for t in range(1, log_e.shape[-2]):
        a = smax(a[..., :, None] + logP[t - 1], -2, gamma) + log_e[..., t, :]
    return smax(a, -1, gamma)


def soft_marginals(log_e, log_init, logP, gamma=1.0):
    """(value (...), marginals (..., B, S)): the forward value and its gradient in the emissions,
    the posterior state marginals at gamma 1 and the best path as gamma goes to 0."""
    value, pull = jax.vjp(lambda le: soft_forward(le, log_init, logP, gamma), log_e)
    return value, pull(jnp.ones_like(value))[0]


def state_loglik(X, state_name, mu_ext, sd_ext, log_s, z, rho, noise, power):
    """log p(body's values | state, size, offsets), (D, F, B, S): chain.state_loglik in JAX. Given
    the patient's size and each measure's offset z the bodies are independent, each value normal
    about s^p (mu + rho sd z) with variance s^2p (1 - rho^2) sd^2 + noise^2; log_s is (D, F), z
    (D, F, M), noise (M,) or (F, M, B), read only where the value is; a value not read adds
    nothing, whatever its noise holds."""
    X = jnp.asarray(X)
    read = jnp.isfinite(X)
    x = jnp.where(read, X, 0.0)                                                               # (F, M, B)
    mu = jnp.asarray(mu_ext, X.dtype)[:, state_name]                                          # (M, S)
    sd = jnp.asarray(sd_ext, X.dtype)[:, state_name]
    s = jnp.exp(jnp.asarray(power, X.dtype)[None, None, :] * jnp.asarray(log_s, X.dtype)[..., None])   # (D, F, M)
    mean = s[..., None] * (mu + rho * sd * jnp.asarray(z, X.dtype)[..., None])                # (D, F, M, S)
    noise = jnp.asarray(noise, X.dtype)
    if _per_value(noise, X):
        noise = jnp.where(read, noise, 1.0)
    err2 = (noise ** 2)[None, :, :, :, None] if _per_value(noise, X) else (noise ** 2)[None, None, :, None, None]
    var = ((s * s)[..., None] * (1.0 - rho * rho) * sd ** 2)[:, :, :, None, :] + err2           # (D, F, M, B|1, S)
    r = x[None, :, :, :, None] - mean[:, :, :, None, :]                                       # (D, F, M, B, S)
    ll = -0.5 * (r * r / var + jnp.log(2.0 * jnp.pi * var))
    return jnp.sum(ll * read[None, :, :, :, None], 2)                                         # (D, F, B, S)


def forward_logev(X, chain: Chain, mu_ext, sd_ext, noise, power, nodes, gamma=1.0):
    """The forward pass at rho 0, run at every node of the size and smoothed over the nodes:
    (value (F,), state marginals (F, B, S)). At gamma 1 the value is log p(field) with no shared
    offset, exact, and the marginals are the posterior's; the size's node is summed out of them."""
    sizes, logw = nodes
    log_init, logP = log_laws(chain)
    log_s = jnp.log(jnp.asarray(sizes, jnp.asarray(X).dtype))
    F, M = jnp.shape(X)[0], jnp.shape(X)[1]
    ls = jnp.broadcast_to(log_s[:, None], (len(sizes), F))
    z = jnp.zeros((len(sizes), F, M), ls.dtype)

    def total(le):
        v = soft_forward(le, log_init, logP, gamma)                                           # (J, F)
        return smax(v + jnp.asarray(logw, v.dtype)[:, None], 0, gamma)

    le = state_loglik(X, chain.state_name, mu_ext, sd_ext, ls, z, 0.0, noise, power)          # (J, F, B, S)
    value, pull = jax.vjp(total, le)
    return value, pull(jnp.ones_like(value))[0].sum(0)


def state_names(marg, state_name, n_names: int = len(NAMES)):
    """Each body's name posterior (..., B, NAMES) from its state marginals (..., B, S)."""
    return jnp.einsum("...bs,sn->...bn", marg, jax.nn.one_hot(state_name, n_names, dtype=marg.dtype))


# ---- the layer: a chain, its paths and a table, ready for a network ------------------------------

@dataclass(frozen=True)
class Naming:
    """Everything the exact layer needs, built once: the chain and its name paths, the measures'
    table extended to NAMES, each measure's error and power of the size, the size's nodes and the
    shared offset's correlation."""
    keys: Tuple[str, ...]
    chain: Chain
    paths: CH.Paths
    mu_ext: np.ndarray
    sd_ext: np.ndarray
    noise: np.ndarray
    power: np.ndarray
    nodes: Tuple[np.ndarray, np.ndarray]
    rho: float

    @property
    def n_bodies(self) -> int:
        return self.chain.n_bodies


def prepare(keys: Sequence[str] = tuple(SEVEN), types: Sequence[str] = TYPES,
            weights: Optional[Sequence[float]] = None, steps: Optional[Sequence[float]] = None,
            n_bodies: int = 3, top: bool = False, bottom: bool = False,
            nodes: Optional[Tuple[np.ndarray, np.ndarray]] = None, rho: float = R.SYNTH["rho"]) -> Naming:
    """The layer for fields of n_bodies with these measures (scanimport's names, which are the
    measures registry's), the step law chain.step_law() unless given, and rule.py's 161
    Gauss-Hermite nodes of the size unless others are given."""
    ms = MS.select(list(keys))
    mu, sd = MS.arrays(ms)
    mu_e, sd_e = CH.extended_table(mu, sd)
    chain = build(types, weights, CH.step_law() if steps is None else steps, n_bodies, top, bottom)
    return Naming(keys=tuple(keys), chain=chain, paths=paths_of(chain), mu_ext=mu_e, sd_ext=sd_e,
                  noise=MS.errors(ms), power=MS.powers(ms),
                  nodes=R.quadrature(R.SYNTH["scale_sd"]) if nodes is None else nodes, rho=float(rho))


def posteriors(nm: Naming, X, noise=None) -> Dict[str, jnp.ndarray]:
    """The exact posteriors of a batch of fields X (F, M, B), values in nm.keys' order down the
    column, NaN where not read: log_path (F, H), log_body and body (F, B, NAMES), type (F, types),
    log_evidence (F,). noise is each value's error (F, M, B) when the measurements carry their
    own, else each measure's."""
    noise = nm.noise if noise is None else noise
    ev = path_logev(X, nm.paths.names, nm.mu_ext, nm.sd_ext, noise, nm.power, nm.nodes, nm.rho)
    log_path = jax.nn.log_softmax(ev + jnp.asarray(nm.paths.log_prior, ev.dtype)[None], axis=-1)
    post = jnp.exp(log_path)
    log_body = log_body_posterior(log_path, nm.paths.names)
    return {"log_path": log_path, "log_body": log_body, "body": jnp.exp(log_body),
            "type": post @ jnp.asarray(nm.paths.type_mass, post.dtype), "log_evidence": jax.nn.logsumexp(
                ev + jnp.asarray(nm.paths.log_prior, ev.dtype)[None], axis=-1)}


def body_loss(nm: Naming, X, true_names, noise=None):
    """The mean over fields of -sum over bodies of log p(body b is named true_names[f, b] | X),
    true_names (F, B) indices into NAMES: the naming layer's loss, differentiable in X. It is
    taken in the log (log_body_posterior), so far from the table, where a true name's posterior
    is below float32's smallest number, the loss is still its value and its gradient still pulls."""
    log_body = posteriors(nm, X, noise)["log_body"]
    lp = jnp.take_along_axis(log_body, jnp.asarray(true_names)[..., None], axis=-1)[..., 0]
    return -jnp.mean(jnp.sum(lp, -1))
