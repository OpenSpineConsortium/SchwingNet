"""The chain of levels (chain.py) as two PyMC models, the two ways round the shared offsets.

A field's bodies share the patient's size and offsets, so given the path alone their values do
not factor along the chain, and pymc-extras' forward algorithm, which needs an emission per body,
cannot sum the path out of rule.py's closed form. TODO.md item P step e asks for both ways round
it, and the owner's words of 27 October 2026, 16:43 UTC, point to the second: "make sure to
account for this feature existing as well
https://www.pymc.io/projects/extras/en/latest/developer/extending_marginalization.html".

- `sampled` (a): the size and every offset are free variables, so given them each body's values
  are independent normals, and pymc-extras' own marginalisation of `DiscreteMarkovChain`
  (`pmx.marginalize`) sums the path out by the forward algorithm. NUTS samples the size and the
  offsets, one plus one per measure for every field, and body_posterior_sampled averages each
  draw's forward-backward marginals, the Rao-Blackwellised estimate. It needs every value read.
- `enumerated` (b): the offsets are integrated in closed form, rule.py's, and the path is summed
  out by a marginalisation of this module's own, built as the linked page builds one: a
  `MarginalRV` subclass (MarginalChainOfLevelsRV, an `EnumerableMarginalRV`); a node rewriter
  registered in pymc-extras' marginal rewrite database, which the page calls
  `marginal_rewrites_db` and pymc-extras 0.15.1 names `marginal_ir_rewrites_db`, matching a
  marginalised chain whose one dependent is this module's emission (PathEmission) and run in
  place of pymc-extras' own rewrite for the chain, which refuses an emission whose core
  dimensions take in the body; its log density, which enumerates the chain's support paths
  (chain.support_paths, read once from the chain's start and transitions when the log density is
  built, so they must be constants, or data not changed after it) and takes the logsumexp of the closed form plus each path's prior over them; and a
  `marginalized_conditional`, the posterior over the support paths given the field and the size,
  so that pymc-extras' `recover()` gives the path back. NUTS samples only the size. Its density
  given the size is exact, and with the size integrated on rule.py's nodes it is chain.py's
  exact rule: the tests hold its density given the size to a dense normal from scipy within
  1e-10, and chain.path_logev to the same normal integrated on the nodes within 1e-9.

pymc-extras is imported only here, so the rest of the package runs without it.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

from . import chain as CH
from .rule import SYNTH

EMISSION = "PathEmission"
QUERY_INCLUDE = ("chain_of_levels", "basic")
LOG2PI = math.log(2.0 * math.pi)
_REGISTERED = False
FLOOR = 1e-300                      # (a)'s probability of a move the chain forbids (sampled's docstring)


def _core(p, ndim: int):
    """A parameter every field shares, with the batch dimensions PyMC pads it with taken off."""
    return p[(0,) * (p.ndim - ndim)] if p.ndim > ndim else p


def _constant(var) -> np.ndarray:
    """The value of a chain parameter that depends on no random variable: a constant or data."""
    from pytensor.graph.basic import Constant
    if isinstance(var, Constant):
        return np.asarray(var.data)
    try:
        return np.asarray(var.eval())
    except Exception as e:
        raise ValueError("the chain of levels enumerates its paths from its start and transitions, which must be "
                         "constants or data, not random: %s" % e)


# ---- (b): the emission and the marginalisation of this module's own ---------------------------

def path_closed_form(value, names, log_s, read, mu, sd, rho, noise, power):
    """log p(field | path, size) summed over the measures, rule.py's closed form for one path per
    field: value and read (*batch, M, B), names (*batch, B) indices into the table's levels, log_s
    (*batch), mu and sd (M, L), noise and power (M)."""
    import pytensor.tensor as pt
    s = pt.exp(power[:, None] * log_s[..., None, None])                       # (*batch, M, 1)
    muk = pt.moveaxis(mu[:, names], 0, -2)                                    # (*batch, M, B)
    sdk = pt.moveaxis(sd[:, names], 0, -2)
    delta = s * s * (1.0 - rho * rho) * sdk * sdk + (noise * noise)[:, None]
    d = read / delta
    r = value - s * muk
    u = s * rho * sdk
    q1 = (r * r * d).sum(-1)
    q2 = (r * u * d).sum(-1)
    a = (u * u * d).sum(-1)
    ld = (read * pt.log(delta)).sum(-1)
    ll = -0.5 * (q1 - q2 * q2 / (1.0 + a) + ld + pt.log1p(a) + read.sum(-1) * LOG2PI)
    return ll.sum(-1)


def _emission_logp(value, state, log_s, read, mu, sd, state_name, rho, noise, power):
    names = _core(state_name, 1)[state]
    return path_closed_form(value, names, log_s, read, _core(mu, 2), _core(sd, 2), _core(rho, 0), _core(noise, 1),
                            _core(power, 1))


def _emission_random(state, log_s, read, mu, sd, state_name, rho, noise, power, rng=None, size=None):
    """A field's values given its path and size, with no floor, as the likelihood has none."""
    state, log_s, read = np.asarray(state), np.asarray(log_s, float), np.asarray(read, float)
    mu, sd = _core(np.asarray(mu, float), 2), _core(np.asarray(sd, float), 2)
    names = _core(np.asarray(state_name), 1)[state]
    rho, noise, power = float(_core(np.asarray(rho), 0)), _core(np.asarray(noise, float), 1), _core(np.asarray(power, float), 1)
    M, B = read.shape[-2:]
    batch = tuple(size) if size is not None else np.broadcast_shapes(names.shape[:-1], log_s.shape, read.shape[:-2])
    names = np.broadcast_to(names, batch + (B,))
    m = np.moveaxis(mu[:, names], 0, -2)
    v = np.moveaxis(sd[:, names], 0, -2)
    s = np.exp(power[:, None] * np.broadcast_to(log_s, batch)[..., None, None])
    z = rng.normal(size=batch + (M, 1))
    x = s * (m + v * (rho * z + math.sqrt(1.0 - rho * rho) * rng.normal(size=batch + (M, B)))) + noise[:, None] * rng.normal(size=batch + (M, B))
    return np.where(np.broadcast_to(read, batch + (M, B)) > 0, x, 0.0)


def _chain_parts(chain_rv):
    """The chain's start law and transitions as NumPy arrays, with any padded batch dimensions
    taken off, and the symbolic ones for the path prior."""
    import pymc as pm
    node = chain_rv.owner
    P = node.op.dist_params(node)[0]
    starts = [i for i in node.inputs if i.owner is not None and isinstance(i.owner.op, type(pm.Categorical.dist(p=[1.0]).owner.op))]
    if len(starts) != 1:
        raise ValueError("the chain of levels needs a Categorical start law")
    p0 = starts[0].owner.op.dist_params(starts[0].owner)[0]
    p0, P = _core(p0, 1), _core(P, 3)
    return p0, P, _constant(p0), _constant(P)


def _path_prior(p0, P, paths):
    import pytensor.tensor as pt
    pa = pt.as_tensor(paths)
    lp = pt.log(p0)[pa[:, 0]]
    for t in range(paths.shape[1] - 1):
        lp = lp + pt.log(P[t, pa[:, t], pa[:, t + 1]])
    return lp                                                                    # (H,)


def _joint(chain_rv, emission, chain_vv):
    """log p(path) + log p(field | path, size) over every support path, (H, *batch), and the paths."""
    import pytensor.tensor as pt
    from pymc.pytensorf import resolve_shapes
    from pytensor.graph import vectorize_graph
    p0, P, p0v, Pv = _chain_parts(chain_rv)
    paths = CH.support_paths(p0v, Pv)
    batch = tuple(resolve_shapes(tuple(chain_rv.shape)))[:-1]
    dom = pt.broadcast_to(pt.as_tensor(paths).reshape((paths.shape[0],) + (1,) * len(batch) + (paths.shape[1],)),
                          (paths.shape[0], *batch, paths.shape[1]))
    emissions = vectorize_graph(emission, replace={chain_vv: dom})                 # (H, *batch)
    prior = _path_prior(p0, P, paths).reshape((paths.shape[0],) + (1,) * len(batch))
    return emissions + prior, paths


def register() -> None:
    """Register the marginalisation with pymc-extras, once per process."""
    global _REGISTERED
    if _REGISTERED:
        return
    import pymc as pm
    import pytensor.tensor as pt
    from pymc.logprob.abstract import _logprob
    from pymc.logprob.basic import conditional_logp
    from pytensor.graph import node_rewriter
    from pytensor.graph.replace import graph_replace
    from pymc_extras.distributions import DiscreteMarkovChain
    from pymc_extras.model.marginal.distributions.core import inline_ofg_outputs, marginalized_conditional
    from pymc_extras.model.marginal.distributions.enumerable import DUMMY_ZERO, EnumerableMarginalRV
    from pymc_extras.model.marginal.rewrites import MarginalSubgraph, extract_marginal_subgraph, marginal_ir_rewrites_db

    class MarginalChainOfLevelsRV(EnumerableMarginalRV):
        """A chain of levels summed out by enumerating its support paths under the closed form."""

    @node_rewriter(tracks=[MarginalSubgraph])
    def chain_of_levels_marginal(fgraph, node):
        inputs, outputs = extract_marginal_subgraph(node)
        rv = outputs[0]
        if not isinstance(rv.owner.op, DiscreteMarkovChain):
            return None
        deps = outputs[1:1 + node.op.n_dependent_rvs]
        if len(deps) != 1 or getattr(deps[0].owner.op, "name", None) != EMISSION:
            return None
        n_batch = rv.type.ndim - 1                          # the chain's batch dimensions; its last is the body
        dims = (tuple(range(n_batch)) + (None, n_batch),)   # the emission is (*batch, measure, body)
        typed = MarginalChainOfLevelsRV(inputs=inputs, outputs=outputs, dims_connections=dims,
                                        marginalized_name=node.op.marginalized_name,
                                        marginalized_dims=node.op.marginalized_dims, n_dependent_rvs=1)
        new = typed(*inputs)
        new = list(new) if isinstance(new, (list, tuple)) else [new]
        return new[:len(node.outputs)]

    marginal_ir_rewrites_db.register("chain_of_levels_marginal", chain_of_levels_marginal, "chain_of_levels")

    @_logprob.register(MarginalChainOfLevelsRV)
    def chain_of_levels_logp(op, values, *inputs, **kwargs):
        chain_rv, dep = inline_ofg_outputs(op, inputs)[:2]
        chain_vv = chain_rv.clone()
        emission = conditional_logp(rv_values={dep: values[0], chain_rv: chain_vv}, **kwargs)[values[0]]
        joint, _ = _joint(chain_rv, emission, chain_vv)
        return (pt.logsumexp(joint, axis=0), *((DUMMY_ZERO,) * (len(values) - 1)))

    def _posterior_logp(value, logits, table):
        match = pt.all(pt.eq(value[..., None, :], table), axis=-1)
        norm = logits - pt.logsumexp(logits, axis=-1, keepdims=True)
        return pt.logsumexp(pt.where(match, norm, -np.inf), axis=-1)

    def _posterior_dist(logits, table, size):
        return table[pm.Categorical.dist(logit_p=logits, size=size)]

    @marginalized_conditional.register(MarginalChainOfLevelsRV)
    def chain_of_levels_conditional(op, inputs, dep_rvs):
        inner = op.fgraph.unfreeze()
        chain_rv, dep = inner.outputs[0], inner.outputs[1]
        chain_vv, dep_dummy = chain_rv.clone(), dep.type()
        emission = conditional_logp({chain_rv: chain_vv, dep: dep_dummy})[dep_dummy]
        joint, paths = _joint(chain_rv, emission, chain_vv)
        rv = pm.CustomDist.dist(pt.moveaxis(joint, 0, -1), pt.as_tensor(paths), dist=_posterior_dist,
                                logp=_posterior_logp, signature="(h),(h,b)->(b)", class_name="PathPosterior")
        replace = dict(zip(inner.inputs, inputs))
        replace[dep_dummy] = dep_rvs[0]
        [rv] = graph_replace([rv], replace=replace, strict=False)
        return rv

    _REGISTERED = True


def rewrite_query():
    """The query pmx.marginalize takes for (b): this module's rewrite in place of pymc-extras' own
    for the chain."""
    from pytensor.graph.rewriting.db import RewriteDatabaseQuery
    return RewriteDatabaseQuery(include=list(QUERY_INCLUDE), exclude=["discrete_markov_chain_marginal"])


def _coords(F: int, M: int, B: int, measures: Optional[Sequence[str]]):
    return {"field": np.arange(F), "measure": list(measures) if measures is not None else list(range(M)),
            "body": np.arange(B)}


def floored(p: np.ndarray, floor: float = FLOOR) -> np.ndarray:
    """A law, or each row of transitions, with every zero raised to floor and renormalised."""
    p = np.maximum(np.asarray(p, float), floor)
    return p / p.sum(-1, keepdims=True)


def _chain_variable(chain: CH.Chain, floor: float = 0.0):
    import pymc as pm
    import pymc_extras as pmx
    P, init = (floored(chain.P, floor), floored(chain.init, floor)) if floor > 0 else (chain.P, chain.init)
    return pmx.DiscreteMarkovChain("state", P=P, init_dist=pm.Categorical.dist(p=init),
                                   steps=chain.n_bodies - 1, time_varying_P=True, dims=("field", "body"))


def enumerated(X: np.ndarray, chain: CH.Chain, mu_ext: np.ndarray, sd_ext: np.ndarray, noise: np.ndarray,
               power: np.ndarray, synth: dict = SYNTH, measures: Optional[Sequence[str]] = None, marginalize: bool = True):
    """(b): the size free, the path summed out by this module's marginalisation, the offsets in
    closed form. X is (fields, measures, bodies), NaN where not read; the table is over chain.NAMES."""
    import pymc as pm
    import pymc_extras as pmx
    X = np.asarray(X, float)
    F, M, B = X.shape
    if chain.n_bodies != B or B < 2:
        raise ValueError("a chain for %d bodies, fields of %d; the chain needs two bodies or more" % (chain.n_bodies, B))
    register()
    read = np.isfinite(X)
    with pm.Model(coords=_coords(F, M, B, measures)) as model:
        log_s = pm.Normal("log_s", 0.0, float(synth["scale_sd"]), dims="field")
        state = _chain_variable(chain)
        pm.CustomDist("x", state, log_s, read.astype(float), np.asarray(mu_ext, float), np.asarray(sd_ext, float),
                      chain.state_name.astype(np.int64), float(synth["rho"]), np.asarray(noise, float),
                      np.asarray(power, float), logp=_emission_logp, random=_emission_random,
                      signature="(b),(),(m,b),(m,l),(m,l),(s),(),(m),(m)->(m,b)", class_name=EMISSION,
                      observed=np.where(read, X, 0.0), dims=("field", "measure", "body"))
    return pmx.marginalize(model, ["state"], rewrite_query=rewrite_query()) if marginalize else model


def sampled(X: np.ndarray, chain: CH.Chain, mu_ext: np.ndarray, sd_ext: np.ndarray, noise: np.ndarray,
            power: np.ndarray, synth: dict = SYNTH, measures: Optional[Sequence[str]] = None, marginalize: bool = True):
    """(a): the size and the offsets free, each body's values normal given them, the path summed
    out by pymc-extras' own forward algorithm. Every value must be read. The forward algorithm
    takes its gradient through log P, which is not finite at a state no move reaches (the first
    level after the first body, or a start that does not fit), and NUTS then diverges on every
    draw; so here every move and start of probability zero is given FLOOR, a cost of about 691
    nats each, which leaves the log density as it was to far below rounding unless a path that
    breaks the chain's law fits the field some 655 nats better than every path that keeps it, the 691
    less the 37 below which a double's rounding hides a term."""
    import pymc as pm
    import pymc_extras as pmx
    import pytensor.tensor as pt
    X = np.asarray(X, float)
    F, M, B = X.shape
    if chain.n_bodies != B or B < 2:
        raise ValueError("a chain for %d bodies, fields of %d; the chain needs two bodies or more" % (chain.n_bodies, B))
    if not np.isfinite(X).all():
        raise ValueError("the sampled chain needs every value read")
    rho = float(synth["rho"])
    with pm.Model(coords=_coords(F, M, B, measures)) as model:
        log_s = pm.Normal("log_s", 0.0, float(synth["scale_sd"]), dims="field")
        z = pm.Normal("z", 0.0, 1.0, dims=("field", "measure"))
        state = _chain_variable(chain, FLOOR)
        names = pt.as_tensor(chain.state_name.astype(np.int64))[state]            # (F, B)
        mk = pt.moveaxis(pt.as_tensor(np.asarray(mu_ext, float))[:, names], 0, -2)   # (F, M, B)
        sk = pt.moveaxis(pt.as_tensor(np.asarray(sd_ext, float))[:, names], 0, -2)
        s = pt.exp(pt.as_tensor(np.asarray(power, float))[None, :, None] * log_s[:, None, None])
        mean = s * (mk + rho * sk * z[:, :, None])
        sigma = pt.sqrt(s * s * (1 - rho * rho) * sk * sk + pt.as_tensor(np.asarray(noise, float))[None, :, None] ** 2)
        pm.Normal("x", mu=mean, sigma=sigma, observed=X, dims=("field", "measure", "body"))
    return pmx.marginalize(model, ["state"]) if marginalize else model


def body_posterior_sampled(idata, X: np.ndarray, chain: CH.Chain, mu_ext: np.ndarray, sd_ext: np.ndarray,
                           noise: np.ndarray, power: np.ndarray, t: int, synth: dict = SYNTH, chunk: int = 50,
                           n_batches: int = 1):
    """(a)'s posterior of body t's name, (fields, NAMES), Rao-Blackwellised: each draw's (size,
    offsets) gives the state marginals by the forward-backward algorithm (chain.forward_backward),
    and the draws' marginals are averaged; with the means of each chain's draws cut into n_batches
    batches of one size, the per-chain means at 1, for a Monte Carlo error (batch_means)."""
    post = idata.posterior
    log_s = np.asarray(post["log_s"].values, float)               # (chains, draws, F)
    z = np.asarray(post["z"].values, float)                       # (chains, draws, F, M)
    size, used = _batches(log_s.shape[1], n_batches)
    sums = np.zeros((log_s.shape[0], n_batches, X.shape[0], len(CH.NAMES)))
    for c in range(log_s.shape[0]):
        for d0 in range(0, used, chunk):
            d1 = min(d0 + chunk, used)
            le = CH.state_loglik(X, chain, mu_ext, sd_ext, log_s[c, d0:d1], z[c, d0:d1], float(synth["rho"]), noise, power)
            marg, _ = CH.forward_backward(le, chain.init, chain.P)
            np.add.at(sums[c], np.arange(d0, d1) // size, CH.state_body_posterior(marg, chain, t))
    return batch_means(sums / size)


def body_posterior_enumerated(idata, X: np.ndarray, paths: CH.Paths, mu_ext: np.ndarray, sd_ext: np.ndarray,
                              noise: np.ndarray, power: np.ndarray, t: int, synth: dict = SYNTH, chunk: int = 25,
                              n_batches: int = 1):
    """(b)'s posterior of body t's name, (fields, NAMES), Rao-Blackwellised: each draw's size gives
    p(path | field, size) in closed form, averaged over the draws; with the means of each chain's
    draws cut into n_batches batches of one size, the per-chain means at 1 (batch_means)."""
    log_s = np.asarray(idata.posterior["log_s"].values, float)    # (chains, draws, F)
    C_, D, F = log_s.shape
    size, used = _batches(D, n_batches)
    sums = np.zeros((C_, n_batches, F, len(CH.NAMES)))
    for c in range(C_):
        for d0 in range(0, used, chunk):
            d1 = min(d0 + chunk, used)
            ll = path_loglik_numpy(X, paths.names, mu_ext, sd_ext, log_s[c, d0:d1], float(synth["rho"]),
                                   noise, power) + paths.log_prior
            p = np.exp(ll - ll.max(-1, keepdims=True))
            p /= p.sum(-1, keepdims=True)
            for d in range(p.shape[0]):
                sums[c, (d0 + d) // size] += CH.body_posterior(p[d], paths.names, t)
    return batch_means(sums / size)


def _batches(draws: int, n_batches: int):
    """The draws in a batch, and the draws used: the last draws of a chain, fewer than n_batches,
    that fill no batch are left out of the mean and the error alike, as model.hypothesis_posterior
    leaves them, so the two describe the same draws."""
    size = draws // n_batches
    if n_batches < 1 or size < 1:
        raise ValueError("%d draws make no %d batches" % (draws, n_batches))
    return size, size * n_batches


def batch_means(means: np.ndarray):
    """The posterior and the batches' means, (chains * batches, fields, NAMES), from each chain's
    batch means (chains, batches, fields, NAMES); the Monte Carlo error of the posterior is their
    SD over the square root of their count (mcse)."""
    batches = means.reshape((-1,) + means.shape[2:])
    return batches.mean(0), batches


def mcse(batches: np.ndarray) -> np.ndarray:
    """The Monte Carlo standard error of the mean of the batches' means, (fields, NAMES): their SD
    over the square root of their count, as model.hypothesis_posterior takes it."""
    return batches.std(axis=0, ddof=1) / math.sqrt(batches.shape[0])


def path_loglik_numpy(X: np.ndarray, names: np.ndarray, mu: np.ndarray, sd: np.ndarray, log_s: np.ndarray,
                      rho: float, noise: np.ndarray, power: np.ndarray) -> np.ndarray:
    """path_closed_form in NumPy: (draws, fields, paths) for log_s (draws, fields)."""
    X = np.asarray(X, float)
    read = np.isfinite(X).astype(float)
    x = np.where(read > 0, X, 0.0)[None, :, None]                 # (1, F, 1, M, B)
    w = read[None, :, None]
    s = np.exp(np.asarray(power, float)[None, None, None, :, None] * np.asarray(log_s, float)[:, :, None, None, None])
    muk = np.moveaxis(mu[:, names], 0, -2)[None, None]            # (1, 1, H, M, B)
    sdk = np.moveaxis(sd[:, names], 0, -2)[None, None]
    delta = s * s * (1 - rho * rho) * sdk * sdk + (np.asarray(noise, float) ** 2)[:, None]
    d = w / delta
    r = x - s * muk
    u = s * rho * sdk
    q1, q2, a = (r * r * d).sum(-1), (r * u * d).sum(-1), (u * u * d).sum(-1)
    ld = (w * np.log(delta)).sum(-1)
    return (-0.5 * (q1 - q2 * q2 / (1 + a) + ld + np.log1p(a) + w.sum(-1) * LOG2PI)).sum(-1)
