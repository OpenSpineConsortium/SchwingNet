"""The naming rule and the column generator as PyMC models: step d of TODO.md item P.

    m = model.naming(X, hyp, mu, sd, keys, noise=errors, power=powers)   # the rule: the level summed out, log s free
    idata = model.sample(m)                             # NUTS on the size alone
    post, se = model.hypothesis_posterior(m, idata)     # p(level | x), Rao-Blackwellised, and its error
    logev = model.quadrature_evidence(m)                # its likelihoods integrated on rule.py's nodes

Three models over the same table and the same covariates (covariates.py), each a pm.Model with
named dimensions:

- `naming` is the rule. Given a hypothesis h (the level of every body of the field) and the
  patient's size s, a field's values have rule.py's closed-form density, and h is summed out
  exactly inside the observed variable's log density by a logsumexp over every hypothesis, so
  the one free variable is the continuous log s, which NUTS samples. The posterior over
  hypotheses is then the average over the draws of p(h | x, s), the Rao-Blackwellised estimate:
  no sampler ever moves a discrete level (the owner's word of 27 October 2026, 09:46 UTC, on
  Metropolis bottlenecks), and the average has a smaller error than counting sampled levels
  would. `quadrature_evidence` integrates over log s, on rule.py's Gauss-Hermite nodes instead
  of by sampling, each hypothesis's likelihood, the term the observed density sums, built from
  the model's own variables and size prior: the exact rule computed from the model's graph.
- `fixed_level` is the development baseline: the level of every body is known, and three of the
  generator's continuous variables are explicit, the patient's size, the patient's offset in
  each measure and the population's coefficient of height, while each body's own draw and the
  error are integrated in closed form, so ArviZ's trace, summary and forest plots apply as they
  stand. It is where item 5's spines of known level, with their covariates, will estimate what
  the naming model takes as given: beta_height is free in it today, while the hooks of weight,
  age and sex are data held at zero, as in the naming model, and the SD of log s and rho are
  constants, each needing a prior in its place before it can be estimated.
- `generator` is columns.py's generator as a forward model; pm.draw gives columns that match
  the NumPy generator's in distribution, though not draw for draw, since the random streams
  differ.

Height enters every model through the size prior (covariates.py): the naming model integrates
its coefficient out in closed form, since it scores each patient alone, while the fixed-level
model and the generator keep it as one variable shared by every patient. Weight, age and sex
enter through hooks held as data at zero, so the graph shows where item 5's estimates will go.
Each measure's error is its own, the data `measure_error` (measures.errors: 1 mm for a length,
in its own units for an area and an angle), and so is its power of the size, the data
`size_power` (measures.powers: 1 for a length, 2 for an area, 0 for an angle), as in rule.py and
compiled.py: wherever a model has the size s, a measure has s^p, so a length scales with s, an
area with its square and an angle not at all, and the generator floors a value at 0.5 only where
it scales with the size, an angle having no floor.

`mermaid` writes a model's graph, PyMC's own analysis of its variables, parents and plates, as
Mermaid text, which GitHub draws in Markdown; graphs/ holds the three models' graphs and the
README shows them.
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS
from . import columns as C
from . import covariates as CV
from .compiled import Hypotheses, hypotheses
from .rule import GH_NODES, SYNTH, check_prior_held, quadrature

LOG2PI = math.log(2.0 * math.pi)
HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH_DIR = os.path.join(HERE, "graphs")
NAMING_SIGNATURE = "(),(m,b),(m),(m,l),(m,l),(h,b),(h),(),(m),(m)->(m,b)"
N_BATCHES = 20          # batches per chain for hypothesis_posterior's Monte Carlo error


# ---- the covariates, as data and as pieces of the graph -------------------------------------

COVARIATES = ["height_cm", "weight_kg", "age_years", "male"]


def covariate_data(covs: Sequence[CV.Covariates], dim: str, measures: Sequence[str], cm: CV.CovariateModel) -> dict:
    """Each patient's covariates as pm.Data, (patients, covariate) with male coded 1 for a man and
    0 for a woman, beside a mask of which are known (pm.Data takes no NaN: an unknown value is 0
    and its mask 0), and the hooks as data at their values, so the graph shows where each one
    enters even while it is zero."""
    import pymc as pm
    values = np.array([[c.height_cm, c.weight_kg, c.age_years, 1.0 if c.sex == "M" else 0.0 if c.sex == "F" else np.nan]
                       for c in covs], float).reshape(len(covs), len(COVARIATES))
    known = np.isfinite(values)
    return {
        "covariates": pm.Data("covariates", np.where(known, values, 0.0), dims=(dim, "covariate")),
        "covariate_known": pm.Data("covariate_known", known.astype(float), dims=(dim, "covariate")),
        "sex_effect": pm.Data("sex_effect", float(cm.sex_size)),
        "weight_effect": pm.Data("weight_effect", np.array([cm.weight_effects.get(m, 0.0) for m in measures]), dims="measure"),
        "age_effect": pm.Data("age_effect", np.array([cm.age_effects.get(m, 0.0) for m in measures]), dims="measure"),
    }


def _where_known(data: dict, name: str, if_unknown, fn):
    """fn of one covariate where it is known and if_unknown where it is not, the placeholder
    kept out of fn so that neither a value nor a gradient through it is ever NaN or infinite."""
    import pytensor.tensor as pt
    i = COVARIATES.index(name)
    known = data["covariate_known"][:, i] > 0
    return pt.switch(known, fn(pt.switch(known, data["covariates"][:, i], 1.0)), if_unknown)


def size_location(data: dict, cm: CV.CovariateModel, beta):
    """The mean of log s, beta log(height / reference) plus the sex hook, and log(height /
    reference) itself; both 0 for a patient whose height and sex are unknown."""
    import pytensor.tensor as pt
    dlogh = _where_known(data, "height_cm", 0.0, lambda h: pt.log(h / cm.height_ref))
    share = CV.REFERENCE["male"][0]
    male = _where_known(data, "male", 0.0, lambda m: m - share)
    return beta * dlogh + data["sex_effect"] * male, dlogh


def mean_factor(data: dict):
    """exp(gamma_weight w + gamma_age a) for every patient and measure, w and a the weight and
    age standardised on Panjabi's twelve specimens and 0 where unknown: all ones while the hooks
    are zero."""
    import pytensor.tensor as pt
    (wm, ws), (am, asd) = CV.REFERENCE["weight_kg"], CV.REFERENCE["age_years"]
    zw = _where_known(data, "weight_kg", 0.0, lambda w: (w - wm) / ws)
    za = _where_known(data, "age_years", 0.0, lambda a: (a - am) / asd)
    return pt.exp(zw[:, None] * data["weight_effect"][None, :] + za[:, None] * data["age_effect"][None, :])


def _settings(synth: dict, cm: Optional[CV.CovariateModel]) -> CV.CovariateModel:
    return CV.CovariateModel(scale_sd=float(synth["scale_sd"])) if cm is None else cm


def _errors(synth: dict, noise: Optional[np.ndarray], n_measures: int) -> np.ndarray:
    """Each measure's own error, synth's noise_mm for every one when none is given."""
    errors = np.full(n_measures, float(synth["noise_mm"])) if noise is None else np.asarray(noise, float)
    if errors.shape != (n_measures,):
        raise ValueError("one error per measure: %d measures, noise %r" % (n_measures, errors.shape))
    return errors


def _powers(power: Optional[np.ndarray], n_measures: int) -> np.ndarray:
    """Each measure's power of the size, 1 for every one, a length's, when none is given."""
    powers = np.ones(n_measures) if power is None else np.asarray(power, float)
    if powers.shape != (n_measures,):
        raise ValueError("one power of the size per measure: %d measures, power %r" % (n_measures, powers.shape))
    return powers


def _scaled(log_s, power):
    """s^p as exp(p log s): the size itself, to the bit, where p is 1."""
    import pytensor.tensor as pt
    return pt.exp(power * log_s)


# ---- the naming rule ----------------------------------------------------------------------

def hypothesis_loglik(x, read, factor, mu, sd, idx, log_s, rho, noise, power):
    """log p(field | hypothesis, size) summed over the measures, (fields, hypotheses): rule.py's
    closed form, written elementwise over (fields, measures, hypotheses, bodies) because here
    every field has a size of its own where rule.py shares one grid of sizes across fields, each
    measure's s its power of the size. x is zero where read is 0, and a value not read drops out
    of every sum."""
    import pytensor.tensor as pt
    s = _scaled(log_s[:, None, None, None], power[None, :, None, None])     # (F, M, 1, 1)
    muk = factor[:, :, None, None] * mu[:, idx][None]           # (F, M, H, B)
    sdk = sd[:, idx][None]                                      # (1, M, H, B)
    xb = x[:, :, None, :]                                       # (F, M, 1, B)
    w = read[:, :, None, :]
    delta = s * s * (1.0 - rho * rho) * sdk * sdk + (noise * noise)[None, :, None, None]
    d = w / delta
    r = xb - s * muk
    u = s * rho * sdk
    q1 = (r * r * d).sum(axis=-1)
    q2 = (r * u * d).sum(axis=-1)
    a = (u * u * d).sum(axis=-1)
    ld = (w * pt.log(delta)).sum(axis=-1)
    ll = -0.5 * (q1 - q2 * q2 / (1.0 + a) + ld + pt.log1p(a) + w.sum(axis=-1) * LOG2PI)   # (F, M, H)
    return ll.sum(axis=1)


def _core(p, ndim: int):
    """A parameter every field shares, with the batch dimensions PyMC pads it with taken off."""
    return p[(0,) * (p.ndim - ndim)] if p.ndim > ndim else p


def _naming_logp(value, log_s, read, factor, mu, sd, idx, log_prior, rho, noise, power):
    import pytensor.tensor as pt
    ll = hypothesis_loglik(value, read, factor, _core(mu, 2), _core(sd, 2), _core(idx, 2), log_s,
                           _core(rho, 0), _core(noise, 1), _core(power, 1))
    lp = _core(log_prior, 1)
    return pt.logsumexp(ll + lp, axis=-1) - pt.logsumexp(lp)


def _naming_random(log_s, read, factor, mu, sd, idx, log_prior, rho, noise, power, rng=None, size=None):
    """A draw from the density the logp scores: a hypothesis from the prior, then the field's
    values under it with no floor, as the likelihood has none, and zero where nothing is read."""
    log_s, read, factor = np.asarray(log_s, float), np.asarray(read, float), np.asarray(factor, float)
    mu, sd = _core(np.asarray(mu, float), 2), _core(np.asarray(sd, float), 2)
    idx, log_prior = _core(np.asarray(idx), 2).astype(int), _core(np.asarray(log_prior, float), 1)
    rho, noise = float(_core(np.asarray(rho), 0)), _core(np.asarray(noise, float), 1)
    power = _core(np.asarray(power, float), 1)
    M, B = read.shape[-2:]
    batch = tuple(size) if size is not None else np.broadcast_shapes(log_s.shape, read.shape[:-2], factor.shape[:-1])
    log_s = np.broadcast_to(log_s, batch)
    read = np.broadcast_to(read, batch + (M, B))
    factor = np.broadcast_to(factor, batch + (M,))
    p = np.exp(log_prior - log_prior.max())
    h = rng.choice(len(p), size=batch, p=p / p.sum())
    lv = idx[h]                                                 # batch + (B,)
    m = np.moveaxis(mu[:, lv], 0, -2)                           # batch + (M, B)
    v = np.moveaxis(sd[:, lv], 0, -2)
    s = np.exp(power[:, None] * log_s[..., None, None])         # batch + (M, 1)
    z = rng.normal(size=batch + (M, 1))
    e = rng.normal(size=batch + (M, B))
    n = rng.normal(size=batch + (M, B))
    x = s * (factor[..., None] * m + v * (rho * z + math.sqrt(1.0 - rho * rho) * e)) + noise[:, None] * n
    return np.where(read > 0, x, 0.0)


def hypothesis_labels(hyp: Hypotheses, levels: Sequence[str]) -> List[str]:
    """Each hypothesis by its first body's level, with its pattern of offsets where there are
    several patterns: "T12" or "T12 (0 2 4)"."""
    if len(hyp.patterns) == 1:
        return [levels[k] for k in hyp.place]
    return ["%s (%s)" % (levels[k], " ".join(map(str, hyp.patterns[p]))) for k, p in zip(hyp.place, hyp.pattern)]


def naming(X: np.ndarray, hyp: Hypotheses, mu: np.ndarray, sd: np.ndarray, measures: Sequence[str],
           levels: Optional[Sequence[str]] = None, synth: dict = SYNTH, covs: Optional[Sequence[CV.Covariates]] = None,
           cm: Optional[CV.CovariateModel] = None, log_prior: Optional[np.ndarray] = None,
           noise: Optional[np.ndarray] = None, power: Optional[np.ndarray] = None):
    """The rule as a PyMC model over fields X (fields, measures, bodies), NaN where not read,
    scored under every hypothesis of `hyp` with the table (measures, levels), each measure's
    error `noise` and its power of the size `power` (1 for every one, a length's, by default);
    `covs` gives each field's patient, unknown by default, which leaves the
    archive's size prior. A log prior over the hypotheses is normalised in the density, as
    rule.py's posterior normalises it, so that the observed density is a density whatever the
    prior's sum, one set later with pm.set_data included."""
    import pymc as pm
    import pytensor.tensor as pt
    X = np.asarray(X, float)
    F, M, B = X.shape
    levels = list(LEVELS) if levels is None else list(levels)
    if mu.shape != (M, len(levels)) or sd.shape != mu.shape:
        raise ValueError("the table is (measures, levels) = (%d, %d): mu %r, sd %r" % (M, len(levels), mu.shape, sd.shape))
    if hyp.levels.shape[1] != B or hyp.n_levels != len(levels):
        raise ValueError("the hypotheses place %d bodies in %d levels; X has %d bodies, the table %d levels"
                         % (hyp.levels.shape[1], hyp.n_levels, B, len(levels)))
    covs = CV.unknown(F) if covs is None else list(covs)
    if len(covs) != F:
        raise ValueError("%d patients' covariates for %d fields" % (len(covs), F))
    cm = _settings(synth, cm)
    H = len(hyp)
    lp = np.full(H, -math.log(H)) if log_prior is None else np.asarray(log_prior, float)
    if lp.shape != (H,):
        raise ValueError("the prior has %d entries for %d hypotheses" % (lp.size, H))
    present = np.isfinite(X)
    rho, errors, powers = float(synth["rho"]), _errors(synth, noise, M), _powers(power, M)
    coords = {"field": np.arange(F), "measure": list(measures), "body": np.arange(B), "level": levels,
              "hypothesis": hypothesis_labels(hyp, levels), "covariate": COVARIATES}
    with pm.Model(coords=coords) as model:
        table_mean = pm.Data("table_mean", mu, dims=("measure", "level"))
        table_sd = pm.Data("table_sd", sd, dims=("measure", "level"))
        hl = pm.Data("hypothesis_levels", hyp.levels.astype(np.int64), dims=("hypothesis", "body"))
        log_prior_ = pm.Data("log_prior", lp, dims="hypothesis")
        read = pm.Data("read", present.astype(float), dims=("field", "measure", "body"))
        error = pm.Data("measure_error", errors, dims="measure")
        size_power = pm.Data("size_power", powers, dims="measure")
        data = covariate_data(covs, "field", measures, cm)
        loc, dlogh = size_location(data, cm, cm.beta_height)
        scale = pt.sqrt(cm.scale_sd ** 2 + (cm.beta_height_sd * dlogh) ** 2)
        log_s = pm.Normal("log_s", mu=loc, sigma=scale, dims="field")
        factor = mean_factor(data)
        x = pm.CustomDist("x", log_s, read, factor, table_mean, table_sd, hl, log_prior_, rho, error, size_power,
                          logp=_naming_logp, random=_naming_random, signature=NAMING_SIGNATURE, class_name="MixtureOverLevels",
                          observed=np.where(present, X, 0.0), dims=("field", "measure", "body"))
    # p(h | x, s) is a function of log s alone: kept beside the model, not registered in it, so
    # that sampling never stores it and the graph shows the generative structure only
    model.schwingcheck = {"hypothesis_loglik": hypothesis_loglik(x, read, factor, table_mean, table_sd, hl, log_s, rho, error,
                                                                 size_power),
                          "size_prior": (loc, scale)}
    return model


def sample(model, draws: int = 1000, tune: int = 1000, chains: int = 2, seed: int = 0,
           var_names: Sequence[str] = ("log_s",), **kwargs):
    """NUTS, the chains one after another, keeping `var_names` only: the naming model's per-draw
    hypothesis likelihoods are recomputed by hypothesis_posterior rather than stored."""
    import pymc as pm
    with model:
        return pm.sample(draws=draws, tune=tune, chains=chains, cores=1, random_seed=seed,
                         var_names=list(var_names), progressbar=False, **kwargs)


def _of_log_s(model, out):
    """A compiled function of the size alone, log s (fields,) -> out, every other variable of the
    model replaced by its value (the observed x by the data)."""
    [graph] = model.replace_rvs_by_values([out])
    return model.compile_fn(graph, inputs=[model.rvs_to_values[model["log_s"]]], point_fn=False)


def hypothesis_posterior(model, idata, n_batches: int = N_BATCHES) -> Tuple[np.ndarray, np.ndarray]:
    """p(h | x) for every field, (fields, hypotheses): the mean over the posterior draws of log s
    of p(h | x, s), and its Monte Carlo standard error by batch means, each chain's draws cut into
    n_batches batches of one size. The last draws of a chain, fewer than n_batches, that fill no
    batch are left out of the mean and the error alike, so the two describe the same draws, and
    the draws are summed batch by batch, so the memory taken grows with the batches and not with
    the draws."""
    draws = np.asarray(idata.posterior["log_s"].values)            # (chains, draws, fields)
    nc, nd, F = draws.shape
    size = nd // n_batches
    if size < 1:
        raise ValueError("%d draws make no %d batches" % (nd, n_batches))
    lp = np.asarray(model["log_prior"].get_value(), float)
    fn = _of_log_s(model, model.schwingcheck["hypothesis_loglik"])
    sums = np.zeros((nc, n_batches, F, lp.size))
    for c in range(nc):
        for d in range(size * n_batches):
            a = fn(draws[c, d]) + lp
            a = np.exp(a - a.max(axis=1, keepdims=True))
            sums[c, d // size] += a / a.sum(axis=1, keepdims=True)
    batches = sums.reshape(nc * n_batches, F, lp.size) / size
    return batches.mean(axis=0), batches.std(axis=0, ddof=1) / math.sqrt(batches.shape[0])


def size_prior(model) -> Tuple[np.ndarray, np.ndarray]:
    """Each field's size prior in the naming model, the mean and SD of log s, from the model's own
    graph, so that a height set later with pm.set_data is the one it gives."""
    F = len(model.coords["field"])
    loc, scale = model.compile_fn(list(model.schwingcheck["size_prior"]), inputs=[], point_fn=False)()
    return np.broadcast_to(np.asarray(loc, float), (F,)), np.broadcast_to(np.asarray(scale, float), (F,))


def quadrature_evidence(model, scale_sd: float = SYNTH["scale_sd"], n_nodes: int = GH_NODES,
                        nodes: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> np.ndarray:
    """log p(field | hypothesis), (fields, hypotheses), integrating the model's own
    hypothesis_loglik over log s on the Gauss-Hermite nodes of N(0, scale_sd^2), rule.py's, or on
    the nodes given (rule.trapezoid), each field weighted by the model's own size prior for it,
    the nodes' weights times the ratio of that prior to theirs: the exact rule computed from the
    PyMC graph instead of sampled. Nodes on which a field's prior is not whole are refused
    (rule.check_prior_held), as the trapezoid's of the default reach are for a known height
    outside 161 to 175 cm."""
    sizes, logw = quadrature(scale_sd, n_nodes) if nodes is None else nodes
    F = len(model.coords["field"])
    ll_fn = _of_log_s(model, model.schwingcheck["hypothesis_loglik"])
    prior_fn = model.compile_logp(vars=[model["log_s"]], sum=False, jacobian=False)
    t_nodes = np.log(sizes)
    weights = np.empty((len(t_nodes), F))                           # (J, F): each field's weight on each node
    for j, (tj, lwj) in enumerate(zip(t_nodes, logw)):
        prior = np.asarray(prior_fn({"log_s": np.full(F, tj)})[0], float)
        base = -0.5 * (tj / scale_sd) ** 2 - math.log(scale_sd) - 0.5 * LOG2PI
        weights[j] = lwj + prior - base
    check_prior_held(weights.T, t_nodes, lambda: size_prior(model))
    terms = np.stack([ll_fn(np.full(F, tj)) + weights[j][:, None] for j, tj in enumerate(t_nodes)])   # (J, F, H)
    top = terms.max(axis=0)
    return top + np.log(np.exp(terms - top).sum(axis=0))


# ---- the development baseline: every level known -------------------------------------------

def fixed_level(X: np.ndarray, field_levels: np.ndarray, mu: np.ndarray, sd: np.ndarray, measures: Sequence[str],
                levels: Optional[Sequence[str]] = None, synth: dict = SYNTH,
                covs: Optional[Sequence[CV.Covariates]] = None, cm: Optional[CV.CovariateModel] = None,
                noise: Optional[np.ndarray] = None, power: Optional[np.ndarray] = None):
    """Fields X (fields, measures, bodies) whose bodies' levels are known, field_levels (fields,
    bodies) as indices into the table's levels, with three of the generator's continuous
    variables explicit: log s per patient on the height prior, the patient's offset z in each
    measure, and beta_height shared by every patient. Each value read is normal given s and z,
    the body's own draw and the measure's own error integrated in closed form, as columns.py
    draws them, s being each measure's power of the size; integrating z out too gives rule.py's
    covariance Delta + u u'."""
    import pymc as pm
    import pytensor.tensor as pt
    X = np.asarray(X, float)
    F, M, B = X.shape
    levels = list(LEVELS) if levels is None else list(levels)
    field_levels = np.asarray(field_levels, np.int64)
    if field_levels.shape != (F, B):
        raise ValueError("field_levels is (fields, bodies) = (%d, %d), got %r" % (F, B, field_levels.shape))
    covs = CV.unknown(F) if covs is None else list(covs)
    cm = _settings(synth, cm)
    rho, errors, powers = float(synth["rho"]), _errors(synth, noise, M), _powers(power, M)
    present = np.isfinite(X)
    fi, mi, bi = np.nonzero(present)
    coords = {"field": np.arange(F), "measure": list(measures), "body": np.arange(B), "level": levels,
              "reading": np.arange(len(fi)), "covariate": COVARIATES}
    with pm.Model(coords=coords) as model:
        table_mean = pm.Data("table_mean", mu, dims=("measure", "level"))
        table_sd = pm.Data("table_sd", sd, dims=("measure", "level"))
        fl = pm.Data("field_levels", field_levels, dims=("field", "body"))
        error = pm.Data("measure_error", errors, dims="measure")
        size_power = pm.Data("size_power", powers, dims="measure")
        data = covariate_data(covs, "field", measures, cm)
        beta = pm.Normal("beta_height", mu=cm.beta_height, sigma=cm.beta_height_sd)
        loc, _ = size_location(data, cm, beta)
        log_s = pm.Normal("log_s", mu=loc, sigma=cm.scale_sd, dims="field")
        z = pm.Normal("offset", mu=0.0, sigma=1.0, dims=("field", "measure"))
        factor = mean_factor(data)
        s = _scaled(log_s[fi], size_power[mi])
        lev = fl[fi, bi]
        m = table_mean[mi, lev] * factor[fi, mi]
        v = table_sd[mi, lev]
        pm.Normal("x", mu=s * (m + rho * v * z[fi, mi]), sigma=pt.sqrt(s * s * (1.0 - rho * rho) * v * v + error[mi] ** 2),
                  observed=X[present], dims="reading")
    return model


# ---- the generator ------------------------------------------------------------------------

def _layout(ref, measures: Sequence[str], phenotypes: Sequence[str], n: int, blend: float):
    """Each column's phenotype, level names, transitional position and its (measures, bodies)
    means and SDs, padded to the widest phenotype listed, drawn or not, as columns.py pads them;
    no draw is made here."""
    phen = [phenotypes[c % len(phenotypes)] for c in range(n)]
    prof = {p: C.profiles(ref, measures, p, blend) for p in dict.fromkeys(phenotypes)}
    width = max(len(prof[p][0]) for p in prof)
    M = len(measures)
    mean, spread, present = np.zeros((n, M, width)), np.zeros((n, M, width)), np.zeros((n, width))
    for p, (lv, _, mu, sd) in prof.items():
        rows = [c for c in range(n) if phen[c] == p]
        mean[rows, :, :len(lv)] = mu
        spread[rows, :, :len(lv)] = sd
        present[rows, :len(lv)] = 1.0
    levels = [list(prof[p][0]) for p in phen]
    transitional = [prof[p][1] for p in phen]
    return phen, levels, transitional, mean, spread, present


def generator(ref: Dict[str, Dict[str, tuple]], measures: Sequence[str], phenotypes: Sequence[str], n: int,
              synth: dict = C.SYNTH, r_between: float = 0.0, covs: Optional[Sequence[CV.Covariates]] = None,
              cm: Optional[CV.CovariateModel] = None, noise: Optional[np.ndarray] = None,
              power: Optional[np.ndarray] = None):
    """columns.py's generator over n columns, the phenotypes cycled in turn as there, as a PyMC
    forward model: value = max(s^p (mu f + sd (rho z + sqrt(1 - rho^2) e)) + noise n, 0.5) with f
    the weight and age hooks' factor (1 today), noise each measure's own error and p its power of
    the size, the floor only where p is not 0, as columns.py floors. Returns the model; `draw`
    makes the columns."""
    import pymc as pm
    import pytensor.tensor as pt
    measures = list(measures)
    phen, levels, transitional, mean, spread, present = _layout(ref, measures, phenotypes, n, synth["blend"])
    covs = CV.unknown(n) if covs is None else list(covs)
    cm = _settings(synth, cm)
    M, W = len(measures), mean.shape[2]
    rho, errors, powers = float(synth["rho"]), _errors(synth, noise, M), _powers(power, M)
    coords = {"column": np.arange(n), "measure": measures, "body": np.arange(W), "covariate": COVARIATES}
    with pm.Model(coords=coords) as model:
        column_mean = pm.Data("column_mean", mean, dims=("column", "measure", "body"))
        column_sd = pm.Data("column_sd", spread, dims=("column", "measure", "body"))
        body_present = pm.Data("body_present", present, dims=("column", "body"))
        error = pm.Data("measure_error", errors, dims="measure")
        size_power = pm.Data("size_power", powers, dims="measure")
        data = covariate_data(covs, "column", measures, cm)
        beta = pm.Normal("beta_height", mu=cm.beta_height, sigma=cm.beta_height_sd)
        loc, _ = size_location(data, cm, beta)
        log_s = pm.Normal("log_s", mu=loc, sigma=cm.scale_sd, dims="column")
        if abs(r_between) < 1e-12:
            z = pm.Normal("offset", mu=0.0, sigma=1.0, dims=("column", "measure"))
        else:
            z = pm.MvNormal("offset", mu=np.zeros(M), cov=C.exchangeable(M, r_between), dims=("column", "measure"))
        e = pm.Normal("level_draw", mu=0.0, sigma=1.0, dims=("column", "measure", "body"))
        s = _scaled(log_s[:, None, None], size_power[None, :, None])         # (column, measure, 1)
        loc_x = s * (column_mean * mean_factor(data)[:, :, None]
                     + column_sd * (rho * z[:, :, None] + math.sqrt(1.0 - rho * rho) * e))
        raw = pm.Normal("raw", mu=loc_x, sigma=error[None, :, None], dims=("column", "measure", "body"))
        floored = pt.switch(size_power[None, :, None] > 0, pt.maximum(raw, C.FLOOR), raw)
        pm.Deterministic("value", pt.switch(body_present[:, None, :] > 0, floored, np.nan),
                         dims=("column", "measure", "body"))
    model.schwingcheck = dict(phenotype=phen, levels=levels, transitional_at=transitional,
                              blend=synth["blend"], r_between=r_between, synth=dict(synth), noise=errors.tolist(),
                              power=powers.tolist())
    return model


def draw(model, seed: int) -> C.Columns:
    """The generator model's columns, (column, body, measure) as columns.py lays them out."""
    import pymc as pm
    lay = model.schwingcheck
    value, log_s = pm.draw([model["value"], model["log_s"]], random_seed=seed)
    synth = lay["synth"]
    return C.Columns(values=np.transpose(value, (0, 2, 1)), levels=lay["levels"], measures=list(model.coords["measure"]),
                     phenotype=list(lay["phenotype"]), scale=np.exp(log_s), transitional_at=list(lay["transitional_at"]),
                     blend=lay["blend"], seed=seed,
                     meta=dict(r_between=lay["r_between"], rho=synth["rho"], noise_mm=lay["noise"],
                               scale_sd=synth["scale_sd"], n=len(lay["phenotype"]), engine="pymc", power=lay["power"]))


# ---- the graphs ---------------------------------------------------------------------------

_SHAPES = {"Data": '%s[("%s ~ Data")]', "Free Random Variable": '%s(["%s ~ %s"])',
           "Observed Random Variable": '%s(["%s ~ %s"])', "Deterministic": '%s["%s ~ Deterministic"]',
           "Potential": '%s{"%s ~ Potential"}'}


def mermaid(model) -> str:
    """The model's graph as Mermaid text: PyMC's ModelGraph, which finds every variable, its
    parents and its plate (the dimensions it spans, the plates of a plate diagram), written in
    Mermaid's classic shapes and in a fixed order. pm.model_to_mermaid orders its plates by a
    hash that changes from one process to the next and uses shapes older Mermaid cannot draw."""
    from pymc.model_graph import ModelGraph, random_variable_symbol
    graph = ModelGraph(model)
    plates = graph.get_plates()
    nodes = sorted(graph.nodes(plates=plates), key=lambda node: str(node.var.name))
    lines = ["graph TD"]
    for node in nodes:
        name, kind = str(node.var.name), node.node_type.value
        if kind in ("Free Random Variable", "Observed Random Variable"):
            lines.append("    " + _SHAPES[kind] % (name, name, random_variable_symbol(node.var)))
        else:
            lines.append("    " + _SHAPES[kind] % (name, name))
        if kind == "Observed Random Variable":
            lines.append("    style %s fill:#d9d9d9,color:#000000" % name)
    lines += ["    %s --> %s" % (parent, child) for child, parent in sorted(graph.edges())]
    label = lambda info: " x ".join(name if name else str(length) for name, length in zip(info.names, info.lengths))
    labelled = sorted((label(plate.dim_info), sorted(str(v.var.name) for v in plate.variables))
                      for plate in plates if plate.dim_info)
    for i, (label, members) in enumerate(labelled):
        lines.append('    subgraph plate%d ["%s"]' % (i + 1, label))
        lines += ["        %s" % m for m in members]
        lines.append("    end")
    return "\n".join(lines) + "\n"


def canonical_models() -> Dict[str, object]:
    """The three models on the archive's seven measures as the README draws them: a field of three
    consecutive bodies named over the twenty places they fit, the same field at a known place,
    and the generator over the six phenotypes."""
    from . import measures as MS
    seven = MS.select(MS.SPINEPS_7)
    keys = [MS.archive_key(m) for m in seven]
    mu, sd = MS.arrays(seven)
    errors, powers = MS.errors(seven), MS.powers(seven)
    X = np.full((1, len(keys), 3), 20.0)
    return {
        "naming": naming(X, hypotheses(len(LEVELS), [[0, 1, 2]]), mu, sd, keys, noise=errors, power=powers),
        "fixed_level": fixed_level(X, np.array([[10, 11, 12]]), mu, sd, keys, noise=errors, power=powers),
        "generator": generator(MS.reference(seven), keys, C.PHENOTYPES, len(C.PHENOTYPES), noise=errors, power=powers),
    }


def graph_path(name: str) -> str:
    return os.path.join(GRAPH_DIR, "%s.mmd" % name)


def write_graphs() -> List[str]:
    os.makedirs(GRAPH_DIR, exist_ok=True)
    paths = []
    for name, m in canonical_models().items():
        with open(graph_path(name), "w", encoding="ascii", newline="\n") as fh:
            fh.write(mermaid(m))
        paths.append(graph_path(name))
    return paths


def check_graphs() -> List[str]:
    """The names of the committed graphs that differ from what write_graphs would write."""
    stale = []
    for name, m in canonical_models().items():
        try:
            with open(graph_path(name), encoding="ascii") as fh:
                committed = fh.read()
        except OSError:
            committed = None
        if committed != mermaid(m):
            stale.append(name)
    return stale
