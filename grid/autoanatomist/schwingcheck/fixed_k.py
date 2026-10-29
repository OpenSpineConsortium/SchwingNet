"""The fixed-k NUTS review: the owner's prompt in TODO.md's queue of 27 October 2026, 09:44 UTC,
answered in its two parts, each claim backed by a run of this module.

    python -m schwingcheck.fixed_k run        # records/fixed-k-2026-10-29/fixed_k.json
    python -m schwingcheck.fixed_k table --table known|free|sharp|tail|spread|categorical
    python -m schwingcheck.fixed_k figures    # into records/fixed-k-2026-10-29/figures/
    python -m schwingcheck.fixed_k check      # whether the README carries the record's tables

One model in four states, on synthetic fields of the typical column, drawn by curve.draw_pool with
every measure of the pool for the same patients and cut to the seven SPINEPS measures:

- known: every body's level fixed (model.fixed_level), NUTS on the patients' sizes, their offsets
  and beta_height; ArviZ's summary, trace and forest read it as they stand, and log s's posterior
  in closed form, integrated on a grid, is what NUTS should give.
- free: the same model written for one field (free_level) with its place, the level of its first
  body, a Categorical over the places with a uniform prior; PyMC samples it with a compound step,
  NUTS on the size and the offsets and CategoricalGibbsMetropolis on the place, with PyMC's default
  proposal, uniform, and with the proportional one, which proposes a place other than the current
  one by its conditional probability, as Liu's Metropolised Gibbs does, but accepts it with a ratio
  computed from that probability renormalised over the other places, where Liu's takes it whole.
- marginal: free_level with the place summed out by pymc-extras' marginalize, so that NUTS samples
  the size and the offsets alone, and the place given back afterwards, by pymc-extras' recover,
  which draws it from its conditional at each draw, and by the average of that conditional over
  the draws (place_posterior), the Rao-Blackwellised estimate.
- exact: rule.py's posterior over the places, the offsets integrated in closed form and the size
  on the trapezoid's nodes (rule.trapezoid), the truth each of the others is held to.

The proposal on a bare place: the same two proposals on a Categorical alone, its probabilities
fixed (run_categorical), sampled by PyMC and set beside the stationary law of each proposal's
transition matrix written out (proposal_kernel), with PyMC's own rounding: PyMC's proportional
proposal leaves a law other than the place's own stationary, or, on two places, none or each place
half, and Liu's, accepted by the whole probabilities, leaves the place's own.

The far tail: the naming model's estimate of a place's posterior below 0.001 tends to run low
(README, The naming model). The same estimator, model.hypothesis_posterior's average over the
draws of log s of p(place | field, s), is taken on NUTS's draws and on draws made independently from
the exact posterior of log s (exact_draws), many seeds of each and a few runs ten times as long, so
that what the sampler adds is told from what the estimator does on its own; and the spread of
p(place | field, s) under the exact posterior of the size, computed on the grid, says how many
independent draws an estimate of that place needs (spread_rows).

Every number is about synthetic columns drawn from Panjabi's tables, never a patient.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import time
import types
import warnings
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS
from . import columns as C
from . import compiled as K
from . import curve as CV
from . import measures as MS
from . import model as MD
from . import rule as R

SETS = ("seven", "all")
SEED, EXTRA_SEED = 1101, 1201         # curve.draw_pool's two seeds for this review's columns
N_COLUMNS = 40
SAMPLING = {"draws": 1000, "tune": 1000, "chains": 4, "seed": 7, "batches": 10}
KNOWN = {"bodies": 3, "fields": 8}
FREE = {"bodies": {"seven": 3, "all": 5}, "fields": 3, "second": 0.1}
SHARP = {"bodies": 9, "fields": 4, "set": "all"}
TAIL = {"bodies": 3, "set": "seven", "fields": 2, "runs": 16, "long_runs": 4, "long_draws": 20000,
        "draws": 2000, "tune": 1000, "chains": 4, "batches": 20, "low": 1e-6, "high": 1e-3}
CATEGORICAL = {"probs": ((0.89, 0.11), (0.889, 0.11, 0.001), (0.6, 0.3, 0.1), (0.5, 0.5)),
               "draws": 4000, "tune": 500, "chains": 4, "seed": 13, "batches": 10}
SAMPLER_STEP = 0.0005                 # the grid exact_draws draws log s from, finer than the rule's
WITHIN = (5.0, 1e-3)                  # an estimate is the exact one within five MC errors plus 0.001
QUICK = {"columns": 8, "sampling": {"draws": 100, "tune": 100, "chains": 2, "seed": 7, "batches": 5},
         "known": {"bodies": 3, "fields": 2}, "free": {"bodies": {"seven": 3, "all": 3}, "fields": 1, "second": 0.0},
         "sharp": {"bodies": 9, "fields": 1, "set": "all"},
         "tail": dict(TAIL, fields=1, runs=2, long_runs=1, long_draws=200, draws=100, tune=100, chains=2, batches=5),
         "categorical": dict(CATEGORICAL, draws=1000, tune=100, chains=2, batches=5)}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD_DIR = os.path.join(ROOT, "records", "fixed-k-2026-10-29")
RECORD = os.path.join(RECORD_DIR, "fixed_k.json")
FIGURE_DIR = os.path.join(RECORD_DIR, "figures")
README = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md")
EXAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "t11-t12-l1.csv")


# ---- the fields ----------------------------------------------------------------------------

def setting():
    """The pool, the seven's places in it, its table, errors and powers."""
    pool = MS.pool()
    keys = [m.key for m in pool]
    subsets = {"seven": [keys.index(k) for k in MS.SPINEPS_7], "all": list(range(len(pool)))}
    mu, sd = MS.arrays(pool)
    return pool, subsets, mu, sd, MS.errors(pool), MS.powers(pool)


def draw_fields(n_columns: int, bodies: int):
    """Every field of `bodies` consecutive bodies of n typical columns with every measure of the
    pool: X (fields, measures, bodies), the true place of each and its column."""
    pool = MS.pool()
    cols = CV.draw_pool(pool, "typical", SEED, EXTRA_SEED, n_columns)
    return C.fields(cols.values, list(range(bodies)))


def cut(which: str):
    """The table, errors, powers and keys of one measure set, and its places in the pool."""
    pool, subsets, mu, sd, noise, power = setting()
    idx = subsets[which]
    return mu[idx], sd[idx], noise[idx], power[idx], [pool[i].key for i in idx], idx


def exact_posterior(X: np.ndarray, bodies: int, which: str, chunk: int = 50) -> np.ndarray:
    """rule.py's posterior over the places, (fields, places), on the trapezoid's nodes."""
    mu, sd, noise, power, _, idx = cut(which)
    sizes, logw = R.trapezoid(R.SYNTH["scale_sd"])
    out = []
    for f0 in range(0, len(X), chunk):
        LL = R.loglik(X[f0:f0 + chunk][:, idx, :], list(range(bodies)), mu, sd, R.SYNTH, sizes=sizes,
                      noise=noise, power=power)
        out.append(R.posterior(R.log_evidence(LL, logw)))
    return np.concatenate(out)


def size_posterior(x: np.ndarray, bodies: int, mu, sd, noise, power, step: float = R.TRAPEZOID_STEP):
    """The exact joint posterior of the place and log s for one field (1, measures, bodies), on a
    trapezoid grid of this step: the grid of log s, the joint (places, nodes) normalised, and each
    place's likelihood given the size, log p(field | place, s) (places, nodes)."""
    sizes, logw = R.trapezoid(R.SYNTH["scale_sd"], step=step)
    LL = R.loglik(x, list(range(bodies)), mu, sd, R.SYNTH, sizes=sizes, noise=noise, power=power)[0].sum(1)
    joint = LL + logw[None, :]
    joint = np.exp(joint - joint.max())
    return np.log(sizes), joint / joint.sum(), LL


# ---- the model with the place free ---------------------------------------------------------

def free_level(x: np.ndarray, hyp: K.Hypotheses, mu: np.ndarray, sd: np.ndarray, noise: np.ndarray,
               power: np.ndarray, place: Optional[int] = None):
    """One field x (1, measures, bodies) as model.fixed_level writes a field, the patient's size and
    offsets explicit and each body's own draw and the error integrated in closed form, with its
    place a Categorical over hyp's places with a uniform prior, or fixed at `place`. Each
    hypothesis's means and SDs at every value read are constants (MUH, VH), so the place selects a
    row of them, the one way pymc-extras can sum it out."""
    import pymc as pm
    import pytensor.tensor as pt
    present = np.isfinite(x[0])
    mi, bi = np.nonzero(present)
    MUH, VH = mu[mi[None, :], hyp.levels[:, bi]], sd[mi[None, :], hyp.levels[:, bi]]     # (H, readings)
    rho = float(R.SYNTH["rho"])
    with pm.Model(coords={"measure": np.arange(x.shape[1])}) as m:
        log_s = pm.Normal("log_s", 0.0, float(R.SYNTH["scale_sd"]))
        z = pm.Normal("offset", 0.0, 1.0, dims="measure")
        k = pm.Categorical("place", p=np.full(len(hyp), 1.0 / len(hyp))) if place is None else int(place)
        s = pt.exp(pt.as_tensor(np.asarray(power, float))[mi] * log_s)
        v = pt.as_tensor(VH)[k]
        mean = s * (pt.as_tensor(MUH)[k] + rho * v * z[mi])
        pm.Normal("x", mu=mean, sigma=pt.sqrt(s * s * (1.0 - rho * rho) * v * v + pt.as_tensor(np.asarray(noise, float))[mi] ** 2),
                  observed=x[0][present])
    return m


def place_loglik(log_s: np.ndarray, z: np.ndarray, x: np.ndarray, hyp: K.Hypotheses, mu, sd, noise, power) -> np.ndarray:
    """log p(field | place, size, offsets) for draws of log s (D,) and the offsets (D, measures):
    (D, places), the density free_level's x has given them."""
    present = np.isfinite(x[0])
    mi, bi = np.nonzero(present)
    MUH, VH = mu[mi[None, :], hyp.levels[:, bi]], sd[mi[None, :], hyp.levels[:, bi]]
    rho = float(R.SYNTH["rho"])
    s = np.exp(np.asarray(power, float)[mi][None, :] * log_s[:, None])[:, None, :]          # (D, 1, R)
    mean = s * (MUH[None] + rho * VH[None] * z[:, mi][:, None, :])                        # (D, H, R)
    var = s * s * (1.0 - rho * rho) * VH[None] ** 2 + np.asarray(noise, float)[mi][None, None, :] ** 2
    r = x[0][present][None, None, :] - mean
    return -0.5 * (r * r / var + np.log(2.0 * math.pi * var)).sum(-1)


def place_posterior(idata, x: np.ndarray, hyp: K.Hypotheses, mu, sd, noise, power, n_batches: int):
    """The Rao-Blackwellised posterior over the places from draws of the size and the offsets: the
    average of p(place | field, size, offsets) over the draws, and its Monte Carlo error by batch
    means, each chain's draws cut into n_batches batches of one size."""
    log_s = np.asarray(idata.posterior["log_s"].values, float)               # (chains, draws)
    z = np.asarray(idata.posterior["offset"].values, float)                  # (chains, draws, measures)
    nc, nd = log_s.shape
    size = nd // n_batches
    batches = np.zeros((nc, n_batches, len(hyp)))
    for c in range(nc):
        ll = place_loglik(log_s[c, :size * n_batches], z[c, :size * n_batches], x, hyp, mu, sd, noise, power)
        p = np.exp(ll - ll.max(1, keepdims=True))
        p /= p.sum(1, keepdims=True)
        batches[c] = p.reshape(n_batches, size, -1).mean(1)
    b = batches.reshape(nc * n_batches, -1)
    return b.mean(0), b.std(0, ddof=1) / math.sqrt(len(b))


def counted_posterior(labels: np.ndarray, H: int, n_batches: int):
    """The share of draws at each place, (places,), and its Monte Carlo error by batch means."""
    nc, nd = labels.shape
    size = nd // n_batches
    one = np.eye(H)[labels[:, :size * n_batches]]                             # (chains, draws, H)
    b = one.reshape(nc, n_batches, size, H).mean(2).reshape(nc * n_batches, H)
    return b.mean(0), b.std(0, ddof=1) / math.sqrt(len(b))


# ---- the runs ------------------------------------------------------------------------------

def quiet():
    """PyMC's notes on each sampling held back, and the old level to put back."""
    log = logging.getLogger("pymc")
    level = log.level
    log.setLevel(logging.ERROR)
    return log, level


def nuts_stats(idata) -> dict:
    stats = idata.sample_stats
    return {"seconds": float(idata.posterior.attrs.get("sampling_time", float("nan"))),
            "steps": float(np.mean(stats["n_steps"].values)) if "n_steps" in stats else None,
            "divergences": int(np.asarray(stats["diverging"].values).sum()) if "diverging" in stats else 0}


def grid_summary(t: np.ndarray, p: np.ndarray) -> dict:
    """The mean, the SD and the 89% equal-tailed interval of a density p on the grid t, the
    interval az.summary(kind="stats") gives. Each node's mass stands for the step around it, so the
    distribution function at a node is the mass below it and half its own; the cumulative sum
    alone, which counts the whole node, would put each quantile half a step low."""
    p = p / p.sum()
    mean = float((p * t).sum())
    cdf = np.cumsum(p) - 0.5 * p
    return {"mean": mean, "sd": float(math.sqrt((p * (t - mean) ** 2).sum())),
            "eti89": [float(np.interp(0.055, cdf, t)), float(np.interp(0.945, cdf, t))]}


def run_known(n_columns: int, spec: dict, sampling: dict):
    """The affirmation: model.fixed_level on fields of known level, for each measure set, NUTS's
    posterior of log s, as az.summary gives it, against the closed form's on a grid."""
    import arviz as az
    X, truth, col = draw_fields(n_columns, spec["bodies"])
    pick = np.random.default_rng(SEED).choice(len(X), spec["fields"], replace=False)
    out, draws = [], {}
    for which in SETS:
        mu, sd, noise, power, keys, idx = cut(which)
        Xs = X[pick][:, idx, :]
        levels = truth[pick][:, None] + np.arange(spec["bodies"])[None, :]
        m = MD.fixed_level(Xs, levels, mu, sd, keys, noise=noise, power=power)
        idata = MD.sample(m, draws=sampling["draws"], tune=sampling["tune"], chains=sampling["chains"],
                          seed=sampling["seed"], var_names=["log_s", "offset", "beta_height"],
                          compute_convergence_checks=False)
        stats = az.summary(idata, var_names=["log_s"], kind="stats", round_to="none")
        diag = az.summary(idata, var_names=["log_s"], kind="diagnostics", round_to="none")
        beta = az.summary(idata, var_names=["beta_height"], kind="all", round_to="none")
        plots = arviz_plots(idata)
        rows = []
        for i, f in enumerate(pick):
            t, joint, _ = size_posterior(Xs[i:i + 1], spec["bodies"], mu, sd, noise, power)
            cond = joint[truth[f]] / joint[truth[f]].sum()
            g = grid_summary(t, cond)
            keep = cond > 1e-6 * cond.max()
            g["density"] = {"log_s": t[keep].tolist(), "mass": cond[keep].tolist(), "step": float(t[1] - t[0])}
            s, d = stats.iloc[i], diag.iloc[i]
            rows.append({"field": int(f), "column": int(col[f]), "place": LEVELS[truth[f]],
                         "nuts": {"mean": float(s["mean"]), "sd": float(s["sd"]),
                                  "eti89": [float(s.iloc[2]), float(s.iloc[3])]},
                         "exact": g, "ess_bulk": float(d["ess_bulk"]), "ess_tail": float(d["ess_tail"]),
                         "r_hat": float(d["r_hat"]), "mcse_mean": float(d["mcse_mean"]), "mcse_sd": float(d["mcse_sd"]),
                         "z_mean": (float(s["mean"]) - g["mean"]) / float(d["mcse_mean"]),
                         "z_sd": (float(s["sd"]) - g["sd"]) / float(d["mcse_sd"])})
        out.append({"set": which, "measures": len(idx), "bodies": spec["bodies"], "fields": rows,
                    "beta_height": {"mean": float(beta["mean"].iloc[0]), "sd": float(beta["sd"].iloc[0]),
                                    "r_hat": float(beta["r_hat"].iloc[0])},
                    "summary_columns": [str(c) for c in stats.columns], "arviz_plots": plots, **nuts_stats(idata)})
        draws[which] = known_draws(idata)
    return out, draws


def arviz_plots(idata) -> Dict[str, int]:
    """az.plot_trace and az.plot_forest run on the draws as they stand, the panels each drew counted
    and the figures closed: the record's word that ArviZ's own plots read a fixed-level run."""
    import arviz as az
    from .figures import style
    plt = style()
    plt.close("all")
    out = {}
    for name, draw in (("plot_trace", az.plot_trace), ("plot_forest", az.plot_forest)):
        draw(idata, var_names=["log_s"])
        out[name + "_axes"] = int(sum(len(plt.figure(n).axes) for n in plt.get_fignums()))
        plt.close("all")
    return out


def known_draws(idata):
    """The draws of log s and beta_height and the divergences of a known run, the inputs of its
    trace and forest figures."""
    import xarray as xr
    post = idata.posterior.to_dataset()[["log_s", "beta_height"]]
    stats = idata.sample_stats.to_dataset()[["diverging"]]
    return xr.DataTree.from_dict({"posterior": post, "sample_stats": stats})


def pick_free(X: np.ndarray, exact: np.ndarray, n: int, second: float) -> np.ndarray:
    """The n fields whose second place is likeliest, those whose second place passes `second`."""
    two = np.sort(exact, 1)[:, -2]
    order = np.argsort(-two, kind="stable")
    return np.array([f for f in order if two[f] >= second][:n], dtype=int)


def sample_free(x, hyp, mu, sd, noise, power, how: str, sampling: dict):
    """free_level sampled one way: 'uniform' and 'proportional', NUTS with CategoricalGibbsMetropolis
    of that proposal on the place, or 'marginal', the place summed out by pymc-extras. The draws,
    the seconds from the start of pm.sample to its end, and the error that stopped it, if any."""
    import pymc as pm
    m = free_level(x, hyp, mu, sd, noise, power)
    kw = dict(draws=sampling["draws"], tune=sampling["tune"], chains=sampling["chains"], cores=1,
              random_seed=sampling["seed"], progressbar=False, compute_convergence_checks=False)
    t0 = time.perf_counter()
    try:
        if how == "marginal":
            import pymc_extras as pmx
            mm = pmx.marginalize(m, ["place"])
            with mm:
                idata = pm.sample(**kw)
                idata = pmx.marginal.recover(idata, model=mm, random_seed=sampling["seed"])
        else:
            with m:
                step = [pm.NUTS([m["log_s"], m["offset"]]), pm.CategoricalGibbsMetropolis([m["place"]], proposal=how)]
                idata = pm.sample(step=step, **kw)
    except ValueError as err:
        return None, time.perf_counter() - t0, str(err)
    return idata, time.perf_counter() - t0, None


def free_row(idata, x, hyp, mu, sd, noise, power, exact: np.ndarray, how: str, sampling: dict) -> dict:
    """One sampler's answer on one field against the exact posterior: the counted share at each
    place (and, for the summed-out model, the Rao-Blackwellised one), each chain's share at the
    exact top place, how often the place changes from one draw to the next, the ESS and R-hat of
    the indicator of the exact top place, and what az.summary prints for the place as a number."""
    import arviz as az
    top = int(np.argmax(exact))
    labels = np.asarray(idata.posterior["place"].values, int)
    counted, counted_se = counted_posterior(labels, len(hyp), sampling["batches"])
    ind = (labels == top).astype(float)
    k, tol = WITHIN
    out = {"how": how, "counted": counted.tolist(), "counted_se": counted_se.tolist(),
           "counted_gap": float(np.abs(counted - exact).max()),
           "counted_within": bool(np.all(np.abs(counted - exact) <= k * counted_se + tol)),
           "chain_top": ind.mean(1).tolist(), "switch": float((np.diff(labels, axis=1) != 0).mean()),
           "ess_top": _ess(ind), "rhat_top": _rhat(ind),
           "label_summary": _label_summary(idata), **nuts_stats(idata)}
    ld = az.summary(idata, var_names=["log_s"], kind="diagnostics", round_to="none")
    out["log_s_ess"], out["log_s_rhat"] = float(ld["ess_bulk"].iloc[0]), float(ld["r_hat"].iloc[0])
    if how == "marginal":
        rb, rb_se = place_posterior(idata, x, hyp, mu, sd, noise, power, sampling["batches"])
        out.update({"rb": rb.tolist(), "rb_se": rb_se.tolist(), "rb_gap": float(np.abs(rb - exact).max()),
                    "rb_within": bool(np.all(np.abs(rb - exact) <= k * rb_se + tol))})
    return out


def _ess(ind: np.ndarray) -> float:
    """ArviZ's bulk ESS of draws (chains, draws); NaN where every draw is the same."""
    import arviz as az
    import xarray as xr
    if np.all(ind == ind.flat[0]):
        return float("nan")
    return float(az.ess(xr.DataArray(ind, dims=("chain", "draw"))))


def _rhat(ind: np.ndarray) -> float:
    """ArviZ's R-hat of draws (chains, draws); NaN where every draw is the same."""
    import arviz as az
    import xarray as xr
    if np.all(ind == ind.flat[0]):
        return float("nan")
    return float(az.rhat(xr.DataArray(ind, dims=("chain", "draw"))))


def _label_summary(idata) -> dict:
    """az.summary's row for the place as it prints it: a label's mean, SD, R-hat and ESS read as if
    the label were a number."""
    import arviz as az
    s = az.summary(idata, var_names=["place"], kind="all", round_to="none")
    r = s.iloc[0]
    return {"mean": float(r["mean"]), "sd": float(r["sd"]), "r_hat": float(r["r_hat"]), "ess_bulk": float(r["ess_bulk"])}


def run_free(n_columns: int, spec: dict, sampling: dict, hows=("uniform", "proportional", "marginal")) -> List[dict]:
    """The warnings: the place free, sampled three ways on the fields with the likeliest second
    place, for each measure set at its width."""
    out = []
    for which in SETS:
        B = spec["bodies"][which]
        X, truth, col = draw_fields(n_columns, B)
        mu, sd, noise, power, _, idx = cut(which)
        ex = exact_posterior(X, B, which)
        hyp = K.hypotheses(len(LEVELS), [list(range(B))])
        for f in pick_free(X, ex, spec["fields"], spec["second"]):
            x = X[f:f + 1][:, idx, :]
            row = {"set": which, "measures": len(idx), "bodies": B, "field": int(f), "column": int(col[f]),
                   "truth": LEVELS[truth[f]], "exact": ex[f].tolist(), "places": [LEVELS[p] for p in hyp.place], "runs": []}
            for how in hows:
                idata, secs, err = sample_free(x, hyp, mu, sd, noise, power, how, sampling)
                if idata is None:
                    row["runs"].append({"how": how, "error": err, "wall_s": secs})
                    continue
                row["runs"].append(dict(free_row(idata, x, hyp, mu, sd, noise, power, ex[f], how, sampling), wall_s=secs))
            out.append(row)
    return out


def run_sharp(n_columns: int, spec: dict, sampling: dict) -> List[dict]:
    """The proportional proposal where the place is all but certain: every measure of the pool at nine bodies,
    each run's error if it stopped, and each other sampler's answer."""
    B, which = spec["bodies"], spec["set"]
    X, truth, col = draw_fields(n_columns, B)
    mu, sd, noise, power, _, idx = cut(which)
    pick = np.random.default_rng(SEED + 1).choice(len(X), spec["fields"], replace=False)
    ex = exact_posterior(X[pick], B, which)
    hyp = K.hypotheses(len(LEVELS), [list(range(B))])
    out = []
    for j, f in enumerate(pick):
        x = X[f:f + 1][:, idx, :]
        row = {"set": which, "measures": len(idx), "bodies": B, "field": int(f), "column": int(col[f]),
               "truth": LEVELS[truth[f]], "exact_top": float(ex[j].max()), "exact_place": LEVELS[hyp.place[int(np.argmax(ex[j]))]],
               "runs": []}
        for how in ("uniform", "proportional", "marginal"):
            idata, secs, err = sample_free(x, hyp, mu, sd, noise, power, how, sampling)
            if idata is None:
                row["runs"].append({"how": how, "error": err, "wall_s": secs})
                continue
            r = free_row(idata, x, hyp, mu, sd, noise, power, ex[j], how, sampling)
            row["runs"].append({k: r[k] for k in ("how", "counted_gap", "counted_within", "switch", "seconds", "steps",
                                                  "divergences", "log_s_ess", "log_s_rhat") if k in r}
                               | ({"rb_gap": r["rb_gap"], "rb_within": r["rb_within"]} if "rb_gap" in r else {})
                               | {"wall_s": secs})
        out.append(row)
    return out


# ---- the proposal on a bare place --------------------------------------------------------------

def bare_log_density(p: Sequence[float]) -> np.ndarray:
    """log p(place = c) for each value c as PyMC's compiled log density of a Categorical of
    probabilities p gives it, the numbers metropolis_proportional takes the softmax of."""
    import pymc as pm
    with pm.Model() as m:
        pm.Categorical("place", p=np.asarray(p, float))
    logp = m.compile_logp()
    return np.array([float(logp({"place": c})) for c in range(len(p))])


def proposal_kernel(p: Sequence[float], how: str, log_density: Optional[np.ndarray] = None) -> np.ndarray:
    """The transition matrix of one step of CategoricalGibbsMetropolis on a place whose probabilities
    are p, held fixed. 'uniform', PyMC's default (astep_unif), proposes one of the other places
    uniformly and accepts it with min(1, p_j / p_i). 'proportional' proposes another place j with
    p_j / (1 - p_i) and accepts it with min(1, r), r = (1 - p_i) / (1 - p_j / (1 - p_i)), the ratio
    PyMC 6.3.2's metropolis_proportional computes from the renormalised probabilities, in floating
    point as it does: the probabilities are the softmax of the place's log density, PyMC's own
    compiled log density of a bare Categorical of probabilities p unless `log_density` gives
    another, so that the rounding is PyMC's, and the move is refused where r is not finite or not
    above 0. 'liu' is Liu's Metropolised Gibbs (1996): the same proposal, accepted with
    min(1, (1 - p_i) / (1 - p_j)), which leaves p stationary. With two places the proportional
    proposal offers the other place with probability 1, and r divides by 1 less that, which is 0 or
    a rounding error of either sign, so the chain never moves or moves at every step, as the
    rounding falls: at 0.5 and 0.5 it never moves, and at 0.89 and 0.11 r is finite and large both
    ways, so it moves at every step and its law is each place half."""
    p = np.asarray(p, float)
    if how == "proportional":
        from scipy import special
        p = special.softmax(bare_log_density(p) if log_density is None else np.asarray(log_density, float))
    else:
        p = p / p.sum()
    k = len(p)
    T = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if j == i:
                continue
            if how == "uniform":
                q, ratio = 1.0 / (k - 1), p[j] / p[i]
            else:
                q = p[j] / (1.0 - p[i])
                with np.errstate(divide="ignore", invalid="ignore"):
                    ratio = (1.0 - p[i]) / (1.0 - (q if how == "proportional" else p[j]))
            T[i, j] = q * (min(1.0, ratio) if np.isfinite(ratio) and ratio > 0 else 0.0)
        T[i, i] = 1.0 - T[i].sum()
    return T


def stationary(T: np.ndarray) -> Optional[np.ndarray]:
    """The one law pi with pi T = pi, or None where there is more than one, as there is when the
    chain cannot leave some places."""
    w, v = np.linalg.eig(T.T)
    ones = np.flatnonzero(np.abs(w - 1.0) < 1e-9)
    if len(ones) != 1:
        return None
    pi = np.real(v[:, ones[0]])
    return pi / pi.sum()


def sample_categorical(p: Sequence[float], how: str, spec: dict) -> np.ndarray:
    """A bare Categorical of probabilities p sampled by CategoricalGibbsMetropolis with the proposal
    given, alone: the draws, (chains, draws)."""
    import pymc as pm
    with pm.Model():
        place = pm.Categorical("place", p=np.asarray(p, float))
        step = pm.CategoricalGibbsMetropolis([place], proposal=how)
        idata = pm.sample(draws=spec["draws"], tune=spec["tune"], chains=spec["chains"], cores=1, step=step,
                          random_seed=spec["seed"], progressbar=False, compute_convergence_checks=False)
    return np.asarray(idata.posterior["place"].values, int)


def run_categorical(spec: dict) -> List[dict]:
    """Each proposal on each bare place: the share of the draws at each place with its Monte Carlo
    error, each chain's share at the first place, how often the place changes, and the stationary
    laws of PyMC's kernel and of Liu's."""
    out = []
    for p in spec["probs"]:
        p = list(p)
        for how in ("uniform", "proportional"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                labels = sample_categorical(p, how, spec)
            share, se = counted_posterior(labels, len(p), spec["batches"])
            pi = stationary(proposal_kernel(p, how))
            out.append({"probs": p, "how": how, "share": share.tolist(), "share_se": se.tolist(),
                        "chain_first": (labels == 0).mean(1).tolist(),
                        "switch": float((np.diff(labels, axis=1) != 0).mean()),
                        "kernel_stationary": None if pi is None else pi.tolist(),
                        "liu_stationary": stationary(proposal_kernel(p, "liu")).tolist()})
    return out


# ---- the far tail ----------------------------------------------------------------------------

def tail_fields(n_columns: int, spec: dict):
    """The README's example field and the n fields of this review's columns with the most places
    between spec's low and high: X (fields, measures, bodies) on spec's measure set, and where each
    came from."""
    B, which = spec["bodies"], spec["set"]
    mu, sd, noise, power, keys, idx = cut(which)
    from .__main__ import read_field
    x0, _ = read_field(EXAMPLE, list(MS.SPINEPS_7))
    if which != "seven" or x0.shape[2] != B:
        raise ValueError("the example field is the seven at three bodies")
    X, truth, col = draw_fields(n_columns, B)
    X = X[:, idx, :]
    ex = exact_posterior_cut(X, B, mu, sd, noise, power)
    count = ((ex > spec["low"]) & (ex < spec["high"])).sum(1)
    pick = np.argsort(-count, kind="stable")[:spec["fields"]]
    return np.concatenate([x0, X[pick]]), ["example"] + ["column %d, %s" % (col[f], LEVELS[truth[f]]) for f in pick]


def exact_posterior_cut(X, B, mu, sd, noise, power, chunk: int = 50) -> np.ndarray:
    sizes, logw = R.trapezoid(R.SYNTH["scale_sd"])
    out = []
    for f0 in range(0, len(X), chunk):
        LL = R.loglik(X[f0:f0 + chunk], list(range(B)), mu, sd, R.SYNTH, sizes=sizes, noise=noise, power=power)
        out.append(R.posterior(R.log_evidence(LL, logw)))
    return np.concatenate(out)


def exact_draws(x, B, mu, sd, noise, power, shape: Tuple[int, int], rng) -> np.ndarray:
    """Draws of log s made independently from its exact posterior given the field, the places
    summed out: a node of a grid SAMPLER_STEP apart drawn by its posterior mass, and a point
    uniformly within its step."""
    t, joint, _ = size_posterior(x, B, mu, sd, noise, power, step=SAMPLER_STEP)
    p = joint.sum(0)
    i = rng.choice(len(t), size=shape, p=p / p.sum())
    return t[i] + (rng.random(shape) - 0.5) * (t[1] - t[0])


def as_idata(log_s: np.ndarray):
    """Draws of log s (chains, draws) in the shape model.hypothesis_posterior reads."""
    return types.SimpleNamespace(posterior={"log_s": types.SimpleNamespace(values=log_s[:, :, None])})


def run_tail(n_columns: int, spec: dict, seed: int = 7) -> dict:
    """The naming model's estimate at every place, by NUTS (spec's runs, seeds seed, seed + 1, ...),
    by independent draws from the exact posterior of the size (as many runs, the same count of
    draws), and by NUTS ten times as long (long_runs), each with its Monte Carlo error, on each
    tail field; and the exact posterior from the same model on the trapezoid's nodes."""
    B = spec["bodies"]
    mu, sd, noise, power, keys, _ = cut(spec["set"])
    X, where = tail_fields(n_columns, spec)
    hyp = K.hypotheses(len(LEVELS), [list(range(B))])
    out = []
    for i, x in enumerate(X):
        x = x[None]
        m = MD.naming(x, hyp, mu, sd, keys, noise=noise, power=power)
        exact = R.posterior(MD.quadrature_evidence(m, nodes=R.trapezoid(R.SYNTH["scale_sd"])))[0]
        runs = {"nuts": [], "independent": [], "nuts_long": []}
        for r in range(spec["runs"]):
            idata = MD.sample(m, draws=spec["draws"], tune=spec["tune"], chains=spec["chains"], seed=seed + r,
                              compute_convergence_checks=False)
            post, se = MD.hypothesis_posterior(m, idata, n_batches=spec["batches"])
            runs["nuts"].append({"seed": seed + r, "post": post[0].tolist(), "se": se[0].tolist(), **nuts_stats(idata)})
            rng = np.random.default_rng(seed + r)
            draws = exact_draws(x, B, mu, sd, noise, power, (spec["chains"], spec["draws"]), rng)
            post, se = MD.hypothesis_posterior(m, as_idata(draws), n_batches=spec["batches"])
            runs["independent"].append({"seed": seed + r, "post": post[0].tolist(), "se": se[0].tolist()})
        for r in range(spec["long_runs"]):
            idata = MD.sample(m, draws=spec["long_draws"], tune=spec["tune"], chains=spec["chains"], seed=seed + 1000 + r,
                              compute_convergence_checks=False)
            post, se = MD.hypothesis_posterior(m, idata, n_batches=spec["batches"])
            runs["nuts_long"].append({"seed": seed + 1000 + r, "post": post[0].tolist(), "se": se[0].tolist(), **nuts_stats(idata)})
        out.append({"field": where[i], "exact": exact.tolist(), "places": [LEVELS[p] for p in hyp.place], "runs": runs,
                    "spread": spread_rows(x, B, mu, sd, noise, power, exact, spec)})
    return out


def spread_rows(x, B, mu, sd, noise, power, exact: np.ndarray, spec: dict) -> List[dict]:
    """For each place: q(s) = p(place | field, s), its relative spread under the exact posterior of
    log s, sqrt(E[q^2]) / E[q] - 1 squared being the variance of one independent draw's estimate
    relative to the place's posterior squared, so that the draws an estimate within 10 per cent
    needs are that over 0.01; the share of the size's posterior that carries 90 per cent of the
    place's mass; and the place's posterior on the grid."""
    t, joint, _ = size_posterior(x, B, mu, sd, noise, power, step=SAMPLER_STEP)
    ps = joint.sum(0)                                         # p(log s | field) on the grid
    q = joint / np.maximum(ps[None, :], 1e-300)               # p(place | field, s), (places, nodes)
    out = []
    for h in range(len(exact)):
        eq = float((ps * q[h]).sum())
        if eq <= 0:
            continue
        cv2 = float((ps * q[h] ** 2).sum()) / eq ** 2 - 1.0
        order = np.argsort(-q[h] * ps)
        cum = np.cumsum((q[h] * ps)[order]) / eq
        carry = float(ps[order[:int(np.searchsorted(cum, 0.9)) + 1]].sum())
        out.append({"place": LEVELS[h], "posterior": eq, "relative_variance": cv2,
                    "draws_for_10pc": cv2 / 0.01, "size_mass_carrying_90pc": carry})
    return out


# ---- the record ------------------------------------------------------------------------------

def run(n_columns: int = N_COLUMNS, quick: bool = False, log=print):
    """Every run of the review into one record, and the known runs' draws, which its trace and
    forest figures are drawn from."""
    made_by = CV.code_state()
    q = QUICK if quick else None
    sampling = dict(q["sampling"] if q else SAMPLING)
    n_columns = q["columns"] if q else n_columns
    log_, level = quiet()
    t0 = time.time()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            known, draws = run_known(n_columns, q["known"] if q else KNOWN, sampling)
            log("fixed-k: known in %.0f s" % (time.time() - t0))
            free = run_free(n_columns, q["free"] if q else FREE, sampling)
            log("fixed-k: free in %.0f s" % (time.time() - t0))
            sharp = run_sharp(n_columns, q["sharp"] if q else SHARP, sampling)
            log("fixed-k: sharp in %.0f s" % (time.time() - t0))
            tail = run_tail(n_columns, q["tail"] if q else TAIL)
            log("fixed-k: tail in %.0f s" % (time.time() - t0))
            categorical = run_categorical(q["categorical"] if q else CATEGORICAL)
            log("fixed-k: categorical in %.0f s" % (time.time() - t0))
    finally:
        log_.setLevel(level)
    return {"command": "python -m schwingcheck.fixed_k run" + (" --quick" if quick else ""),
            "columns": n_columns, "seeds": [SEED, EXTRA_SEED], "sampling": sampling, "within": list(WITHIN),
            "known_spec": q["known"] if q else KNOWN, "free_spec": q["free"] if q else FREE,
            "sharp_spec": q["sharp"] if q else SHARP, "tail_spec": q["tail"] if q else TAIL,
            "categorical_spec": q["categorical"] if q else CATEGORICAL,
            "sampler_step": SAMPLER_STEP, "machine": CV.machine(), "versions": versions(),
            "made_by": made_by, "changed_during_run": CV.changed_during(made_by, CV.code_state()),
            "known": known, "free": free, "sharp": sharp, "tail": tail, "categorical": categorical}, draws


def versions() -> dict:
    from importlib import metadata
    out = CV.versions()
    try:
        out["pymc-extras"] = metadata.version("pymc-extras")
    except metadata.PackageNotFoundError:
        out["pymc-extras"] = "not installed"
    return out


def draws_path(which: str, record: str = RECORD) -> str:
    return os.path.join(os.path.dirname(record), "known-%s.nc" % which)


def write(record: dict, draws: Dict[str, object], path: str = RECORD) -> str:
    """The record as JSON and each known run's draws as NetCDF beside it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for which, tree in draws.items():
        tree.to_netcdf(draws_path(which, path), engine="h5netcdf")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii", newline="\n") as fh:
        json.dump(record, fh, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def load_draws(which: str, record: str = RECORD):
    import xarray as xr
    return xr.open_datatree(draws_path(which, record), engine="h5netcdf")


def load(path: str = RECORD) -> dict:
    with open(path, encoding="ascii") as fh:
        return json.load(fh)


# ---- the tables --------------------------------------------------------------------------------

def _f(x: float, digits: int = 4) -> str:
    return "-" if x is None or not np.isfinite(x) else "%.*f" % (digits, x)


def _g(x: float) -> str:
    return "-" if x is None or not np.isfinite(x) else "%.3g" % x


def _set_label(r: dict) -> str:
    return "%s, %d bodies" % ("the seven" if r["set"] == "seven" else "all %d" % r["measures"], r["bodies"])


def known_table(record: dict) -> str:
    """The affirmation's table: each field's log s from NUTS on the fixed-level model, as
    az.summary gives it, beside the closed form's on a grid."""
    head = ["Measures", "Field (place)", "NUTS: mean, SD", "Closed form: mean, SD", "NUTS: 89% interval",
            "Closed form: 89% interval", "Mean off, MC errors", "SD off, MC errors", "ESS bulk", "R-hat"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for run in record["known"]:
        for r in run["fields"]:
            n, e = r["nuts"], r["exact"]
            out.append("| %s | %d (%s) | %s, %s | %s, %s | %s to %s | %s to %s | %+.1f | %+.1f | %.0f | %.3f |"
                       % (_set_label(run), r["field"], r["place"], _f(n["mean"]), _f(n["sd"]), _f(e["mean"]), _f(e["sd"]),
                          _f(n["eti89"][0]), _f(n["eti89"][1]), _f(e["eti89"][0]), _f(e["eti89"][1]),
                          r["z_mean"], r["z_sd"], r["ess_bulk"], r["r_hat"]))
    s = record["sampling"]
    notes = ["%s: %.1f s of NUTS for the %d fields together, %.1f leapfrog steps a draw, %d divergences; "
             "beta_height %.3f (SD %.3f), its prior, since no field's height is known."
             % (_set_label(run), run["seconds"], len(run["fields"]), run["steps"], run["divergences"],
                run["beta_height"]["mean"], run["beta_height"]["sd"]) for run in record["known"]]
    out += ["", "log s of each field, every level known (model.fixed_level), NUTS with %d chains of %d draws after %d "
            "tuning steps, seed %d, as az.summary(kind=\"stats\") and az.summary(kind=\"diagnostics\") give it; the closed "
            "form is the posterior of log s given the levels, integrated on a grid. " % (s["chains"], s["draws"], s["tune"], s["seed"])
            + " ".join(notes)]
    return "\n".join(out) + "\n"


def _top_two(row: dict) -> str:
    ex = np.asarray(row["exact"])
    o = np.argsort(-ex)[:2]
    return "%s %.3f, %s %.3f" % (row["places"][o[0]], ex[o[0]], row["places"][o[1]], ex[o[1]])


def free_table(record: dict) -> str:
    """The warnings' table: the place free, each sampler's answer on each field."""
    head = ["Measures", "Field (truth): exact", "Sampler", "Share at the top place (MC error)", "Each chain's share",
            "Largest gap", "Place changes a draw", "ESS, top place", "R-hat, top place", "az.summary: place mean (R-hat)",
            "ESS, log s", "Seconds"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in record["free"]:
        ex = np.asarray(row["exact"])
        top = int(np.argmax(ex))
        for r in row["runs"]:
            if "error" in r:
                out.append("| %s | %d (%s): %s | %s | stopped: %s | - | - | - | - | - | - | - | %.1f |"
                           % (_set_label(row), row["field"], row["truth"], _top_two(row), r["how"], r["error"], r["wall_s"]))
                continue
            share, se = r["counted"][top], r["counted_se"][top]
            label = "counted"
            if "rb" in r:
                share, se, label = r["rb"][top], r["rb_se"][top], "averaged"
            gap = r["rb_gap"] if "rb" in r else r["counted_gap"]
            out.append("| %s | %d (%s): %s | %s | %.3f (%.3f), %s | %s | %.3f | %.3f | %s | %s | %.2f (%.2f) | %.0f | %.1f |"
                       % (_set_label(row), row["field"], row["truth"], _top_two(row), r["how"], share, se, label,
                          " ".join("%.2f" % c for c in r["chain_top"]), gap, r["switch"], _g(r["ess_top"]),
                          _f(r["rhat_top"], 3), r["label_summary"]["mean"], r["label_summary"]["r_hat"], r["log_s_ess"],
                          r["seconds"]))
    s = record["sampling"]
    out += ["", "One field, its place free (free_level): uniform and proportional are NUTS on log s and the offsets with "
            "CategoricalGibbsMetropolis on the place, PyMC's default proposal and the proportional one, which proposes "
            "another place by its conditional probability; marginal is the place summed out by pymc-extras, NUTS alone, the share the average of the "
            "place's conditional over the draws. %d chains of %d draws after %d tuning steps, seed %d; errors by batch "
            "means, %d batches a chain." % (s["chains"], s["draws"], s["tune"], s["seed"], s["batches"])]
    return "\n".join(out) + "\n"


def sharp_table(record: dict) -> str:
    head = ["Field (truth)", "Exact: place (posterior)", "uniform: largest gap, place changes", "proportional",
            "marginal: largest gap"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---:|---|---:|"]
    for row in record["sharp"]:
        runs = {r["how"]: r for r in row["runs"]}
        u, p, m = runs["uniform"], runs["proportional"], runs["marginal"]
        cell = lambda r, key: ("stopped: %s" % r["error"]) if "error" in r else _g(r[key])
        out.append("| %d (%s) | %s (%s) | %s | %s | %s |"
                   % (row["field"], row["truth"], row["exact_place"], _f(row["exact_top"], 6),
                      cell(u, "counted_gap") + ("" if "error" in u else ", %.3f" % u["switch"]),
                      ("stopped: %s" % p["error"]) if "error" in p else "gap %s" % _g(p["counted_gap"]),
                      cell(m, "rb_gap")))
    spec = record["sharp_spec"]
    measures = record["sharp"][0]["measures"] if record["sharp"] else 0
    out += ["", "All %d measures at %d bodies, fields drawn at random: the place all but certain. The proportional "
            "proposal divides the other places' probabilities by one less the current place's, which in floating point "
            "is 0, giving NaN, or a rounding error far above what the other places hold, giving probabilities that "
            "do not sum to one." % (measures, spec["bodies"])]
    return "\n".join(out) + "\n"


def tail_stats(row: dict, method: str, low: float, high: float) -> dict:
    """One method's runs on one field: at the places whose exact posterior is between low and high,
    the median over runs and places of the estimate over the exact value, the median over places of
    the runs' mean estimate over the exact value, the share of runs low, and the share of estimates
    more than four of their errors off; at the places above 0.05, the share more than four off."""
    runs = row["runs"][method]
    ex = np.asarray(row["exact"])
    est = np.array([r["post"] for r in runs])
    se = np.array([r["se"] for r in runs])
    tail = (ex > low) & (ex < high)
    big = ex > 0.05
    ratio = est[:, tail] / ex[tail]
    off = np.abs(est - ex) > 4.0 * se
    return {"runs": len(runs), "places": int(tail.sum()),
            "median_ratio": float(np.median(ratio)) if tail.any() else float("nan"),
            "mean_ratio": float(np.median(est[:, tail].mean(0) / ex[tail])) if tail.any() else float("nan"),
            "low": float((ratio < 1.0).mean()) if tail.any() else float("nan"),
            "off4_tail": float(off[:, tail].mean()) if tail.any() else float("nan"),
            "off4_big": float(off[:, big].mean()) if big.any() else float("nan")}


METHODS = (("nuts", "NUTS"), ("independent", "independent draws"), ("nuts_long", "NUTS, ten times as long"))


def tail_table(record: dict) -> str:
    spec = record["tail_spec"]
    head = ["Field", "Draws of log s", "Runs", "Places", "Median estimate / exact", "Mean estimate / exact",
            "Runs low", "Over four errors off", "Places above 0.05: over four errors off"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in record["tail"]:
        for key, label in METHODS:
            t = tail_stats(row, key, spec["low"], spec["high"])
            out.append("| %s | %s | %d | %d | %.3f | %.3f | %.0f%% | %.0f%% | %.0f%% |"
                       % (row["field"], label, t["runs"], t["places"], t["median_ratio"], t["mean_ratio"],
                          100 * t["low"], 100 * t["off4_tail"], 100 * t["off4_big"]))
    out += ["", "The naming model's estimate at the places whose exact posterior is between %g and %g, the seven at %d "
            "bodies: model.hypothesis_posterior on NUTS's draws (%d chains of %d after %d tuning steps), on as many draws "
            "made independently from the exact posterior of log s, and on NUTS's draws %d chains of %d; %d batches a "
            "chain. Mean estimate / exact is the median over the places of the runs' mean."
            % (spec["low"], spec["high"], spec["bodies"], spec["chains"], spec["draws"], spec["tune"], spec["chains"],
               spec["long_draws"], spec["batches"])]
    return "\n".join(out) + "\n"


def spread_table(record: dict, top: int = 4) -> str:
    """For each tail field, its likeliest places and its likeliest tail places: what one independent
    draw's estimate of each varies by, and how much of the size's posterior carries it."""
    spec = record["tail_spec"]
    head = ["Field", "Place", "Posterior", "Relative variance of one draw", "Draws for 10 per cent",
            "Size's posterior carrying 90% of it"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---:|---:|---:|---:|"]
    for row in record["tail"]:
        rows = sorted(row["spread"], key=lambda r: -r["posterior"])
        tail = [r for r in rows if spec["low"] < r["posterior"] < spec["high"]]
        for r in rows[:2] + tail[:top]:
            out.append("| %s | %s | %.3g | %.3g | %s | %.3g |" % (row["field"], r["place"], r["posterior"],
                       r["relative_variance"], "{:,.0f}".format(r["draws_for_10pc"]), r["size_mass_carrying_90pc"]))
    out += ["", "q(s), the place's posterior given the size, under the exact posterior of log s on a grid %g apart: the "
            "variance of q over the square of its mean, which is the variance of one independent draw's estimate "
            "relative to the place's posterior squared, so that an estimate within 10 per cent takes that over 0.01 "
            "draws; and the share of the size's posterior on which 90 per cent of the place's mass lies." % record["sampler_step"]]
    return "\n".join(out) + "\n"


def _law(x: Optional[Sequence[float]]) -> str:
    return "not one" if x is None else ", ".join("%.3f" % v for v in x)


def categorical_table(record: dict) -> str:
    head = ["Probabilities", "Proposal", "Share at each place (MC error)", "Each chain's share at the first place",
            "Place changes a draw", "Stationary: PyMC's kernel", "Stationary: Liu's"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---|---|---:|---|---|"]
    for r in record["categorical"]:
        out.append("| %s | %s | %s | %s | %.3f | %s | %s |" % (
            ", ".join("%g" % v for v in r["probs"]), r["how"],
            ", ".join("%.3f (%.3f)" % (m, e) for m, e in zip(r["share"], r["share_se"])),
            " ".join("%.2f" % v for v in r["chain_first"]), r["switch"], _law(r["kernel_stationary"]),
            _law(r["liu_stationary"])))
    spec = record["categorical_spec"]
    out += ["", "A Categorical alone, its probabilities fixed, sampled by CategoricalGibbsMetropolis with each proposal: "
            "%d chains of %d draws after %d tuning steps, seed %d, errors by batch means, %d batches a chain. Beside it "
            "the stationary law of the proposal's transition matrix written out (proposal_kernel), PyMC's as its code "
            "computes the acceptance, with its own rounding, and Liu's Metropolised Gibbs; not one where the chain never "
            "leaves its place, as at 0.5 and 0.5, where PyMC's ratio divides by zero, while at 0.89 and 0.11 its rounding "
            "gives a ratio above one both ways, so the chain swaps places at every draw and its law is each place half."
            % (spec["chains"], spec["draws"], spec["tune"], spec["seed"], spec["batches"])]
    return "\n".join(out) + "\n"


def tables(path: str = RECORD) -> Dict[str, str]:
    record = load(path)
    return {"fixed_k:known": known_table(record), "fixed_k:free": free_table(record), "fixed_k:sharp": sharp_table(record),
            "fixed_k:tail": tail_table(record), "fixed_k:spread": spread_table(record),
            "fixed_k:categorical": categorical_table(record)}


def check(readme: str = README, path: str = RECORD) -> List[str]:
    """Whether the README carries the record's tables, by chain_study's reading of its blocks."""
    from . import chain_study as CS
    with open(readme, encoding="utf-8") as fh:
        have = CS.readme_blocks(fh.read(), "fixed_k")
    return CS.compare_blocks(have, tables(path))


# ---- the figures -------------------------------------------------------------------------------

CHAIN_STYLES = ("-", "--", ":", "-.")
SAMPLER_STYLE = {"uniform": dict(marker="o", markerfacecolor="white"),
                 "proportional": dict(marker="s", markerfacecolor="white"),
                 "marginal": dict(marker="^", markerfacecolor="black")}
TAIL_STYLE = {"nuts": dict(marker="o", markerfacecolor="white", linestyle="-"),
              "independent": dict(marker="s", markerfacecolor="black", linestyle="--"),
              "nuts_long": dict(marker="^", markerfacecolor="white", linestyle=":")}


def fig_trace(record: dict, draws, outdir: str) -> List[str]:
    """What az.plot_trace shows for the first field of the seven, in the house format: A, each
    chain's draws of log s against the draw; B, each chain's histogram beside the closed form."""
    from .figures import write_csv, save, style, letter
    plt = style()
    run = record["known"][0]
    r = run["fields"][0]
    ls = np.asarray(draws["posterior"]["log_s"].values, float)[:, :, 0]          # (chains, draws)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), gridspec_kw={"width_ratios": [1.6, 1]})
    rows = []
    for c in range(ls.shape[0]):
        axes[0].plot(np.arange(ls.shape[1]), ls[c], linestyle=CHAIN_STYLES[c % 4], linewidth=0.5, label="chain %d" % (c + 1))
        rows += [{"panel": "A", "series": "chain %d" % (c + 1), "draw": d, "log_s": float(v), "density": ""}
                 for d, v in enumerate(ls[c])]
    t, mass, step = np.asarray(r["exact"]["density"]["log_s"]), np.asarray(r["exact"]["density"]["mass"]), r["exact"]["density"]["step"]
    edges = np.linspace(ls.min(), ls.max(), 31)
    for c in range(ls.shape[0]):
        h, _ = np.histogram(ls[c], bins=edges, density=True)
        axes[1].step(edges[:-1], h, where="post", linestyle=CHAIN_STYLES[c % 4], linewidth=0.7)
        rows += [{"panel": "B", "series": "chain %d" % (c + 1), "draw": "", "log_s": float(e), "density": float(v)}
                 for e, v in zip(edges[:-1], h)]
    axes[1].plot(t, mass / step, color="black", linewidth=1.6, label="closed form")
    rows += [{"panel": "B", "series": "closed form", "draw": "", "log_s": float(a), "density": float(b / step)}
             for a, b in zip(t, mass)]
    axes[0].set_xlabel("Draw")
    axes[0].set_ylabel("log s")
    axes[1].set_xlabel("log s")
    axes[1].set_ylabel("Density")
    axes[0].legend(loc="upper right", ncol=2)
    axes[1].legend(loc="upper right")
    letter(axes[0], "A", "Each chain's draws")
    letter(axes[1], "B", "Each chain against the closed form")
    fig.tight_layout()
    caption = ("Log size of one synthetic field of three bodies, the seven SPINEPS measures, every level known: %d chains "
               "of NUTS, A by draw and B as histograms beside the posterior in closed form, what az.plot_trace shows, "
               "drawn in the house format." % ls.shape[0])
    return save(fig, outdir, "fixed_k_trace", caption) + [write_csv(outdir, "fixed_k_trace", rows)]


def fig_forest(record: dict, outdir: str) -> List[str]:
    """What az.plot_forest shows for log s of every known field, in the house format, with the
    closed form's mean and 89% interval beside NUTS's."""
    from .figures import write_csv, save, style, letter
    plt = style()
    fig, axes = plt.subplots(1, len(record["known"]), figsize=(7.2, 2.9), sharey=True)
    rows = []
    for ax, run, L in zip(np.atleast_1d(axes), record["known"], "AB"):
        for i, r in enumerate(run["fields"]):
            for off, key, mark in ((-0.15, "nuts", dict(marker="o", markerfacecolor="white")),
                                   (0.15, "exact", dict(marker="s", markerfacecolor="black"))):
                v = r[key]
                ax.plot(v["eti89"], [i + off] * 2, color="black", linewidth=0.9)
                ax.plot([v["mean"]], [i + off], linestyle="none", color="black", **mark)
                rows.append({"panel": L, "field": r["field"], "series": key, "mean": v["mean"], "lower": v["eti89"][0], "upper": v["eti89"][1]})
        ax.set_yticks(range(len(run["fields"])))
        ax.set_yticklabels(["%d (%s)" % (r["field"], r["place"]) for r in run["fields"]])
        ax.set_xlabel("log s")
        ax.invert_yaxis()
        letter(ax, L, "the seven" if run["set"] == "seven" else "all %d" % run["measures"])
    np.atleast_1d(axes)[0].plot([], [], color="black", marker="o", markerfacecolor="white", label="NUTS")
    np.atleast_1d(axes)[0].plot([], [], color="black", marker="s", markerfacecolor="black", label="closed form")
    np.atleast_1d(axes)[0].legend(loc="lower left")
    fig.tight_layout()
    caption = ("Log size of %d synthetic three-body fields, every level known: NUTS's mean and 89 per cent interval, what "
               "az.plot_forest shows, drawn in the house format beside the closed form's; A the seven SPINEPS measures, B all %d."
               % (len(record["known"][0]["fields"]), record["known"][-1]["measures"]))
    return save(fig, outdir, "fixed_k_forest", caption) + [write_csv(outdir, "fixed_k_forest", rows)]


def fig_mixing(record: dict, outdir: str) -> List[str]:
    """Each chain's share at the exact top place, for each sampler and field, beside the exact one."""
    from .figures import write_csv, save, style, letter
    plt = style()
    sets = [w for w in SETS if any(r["set"] == w for r in record["free"])]
    fig, axes = plt.subplots(1, len(sets), figsize=(7.2, 2.8), sharey=True)
    rows = []
    for ax, which, L in zip(np.atleast_1d(axes), sets, "AB"):
        fields = [r for r in record["free"] if r["set"] == which]
        for i, row in enumerate(fields):
            ex = np.asarray(row["exact"])
            top = int(np.argmax(ex))
            ax.plot([i - 0.4, i + 0.4], [ex[top]] * 2, color="black", linewidth=1.4)
            rows.append({"panel": L, "field": row["field"], "series": "exact", "chain": "", "share": float(ex[top])})
            for j, r in enumerate(row["runs"]):
                if "error" in r:
                    continue
                x = i + (j - 1) * 0.25
                ax.plot([x] * len(r["chain_top"]), r["chain_top"], linestyle="none", color="black", markersize=3.5,
                        **SAMPLER_STYLE[r["how"]])
                rows += [{"panel": L, "field": row["field"], "series": r["how"], "chain": c + 1, "share": float(v)}
                         for c, v in enumerate(r["chain_top"])]
        ax.set_xticks(range(len(fields)))
        ax.set_xticklabels(["%d" % r["field"] for r in fields])
        ax.set_xlabel("Field")
        ax.set_ylim(0, 1)
        letter(ax, L, "%s, %d bodies" % ("the seven" if which == "seven" else "all %d" % fields[0]["measures"], fields[0]["bodies"]))
    a0 = np.atleast_1d(axes)[0]
    a0.set_ylabel("Share at the exact top place")
    for how, st in SAMPLER_STYLE.items():
        a0.plot([], [], linestyle="none", color="black", label=how, **st)
    a0.plot([], [], color="black", linewidth=1.4, label="exact")
    a0.legend(loc="lower left", ncol=2)
    fig.tight_layout()
    caption = ("Each chain's share of draws at the exact top place on synthetic fields with two likely places, the place "
               "free: Metropolis-within-NUTS with PyMC's uniform and the proportional proposal, and the place summed out "
               "by pymc-extras and recovered; the bar is the exact posterior.")
    return save(fig, outdir, "fixed_k_mixing", caption) + [write_csv(outdir, "fixed_k_mixing", rows)]


def fig_tail(record: dict, outdir: str) -> List[str]:
    """The estimate over the exact posterior against the exact posterior, each method's median over
    its runs with its interquartile range, one panel a field."""
    from .figures import write_csv, save, style, letter
    plt = style()
    n = len(record["tail"])
    fig, axes = plt.subplots(1, n, figsize=(7.2, 2.7), sharey=True)
    rows = []
    for ax, row, L in zip(np.atleast_1d(axes), record["tail"], "ABCDE"):
        ex = np.asarray(row["exact"])
        keep = ex > 1e-7
        order = np.argsort(ex[keep])
        x = ex[keep][order]
        for key, label in METHODS:
            est = np.array([r["post"] for r in row["runs"][key]])[:, keep][:, order] / x
            med, lo, hi = np.median(est, 0), np.quantile(est, 0.25, 0), np.quantile(est, 0.75, 0)
            ax.errorbar(x, med, yerr=[med - lo, hi - med], color="black", markersize=3.5, linewidth=0.8, label=label,
                        **TAIL_STYLE[key])
            rows += [{"panel": L, "series": key, "exact": float(a), "median": float(b), "q25": float(c), "q75": float(d)}
                     for a, b, c, d in zip(x, med, lo, hi)]
        ax.axhline(1.0, color="black", linestyle=":", linewidth=0.8)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Exact posterior")
        letter(ax, L, row["field"])
    a0 = np.atleast_1d(axes)[0]
    a0.set_ylabel("Estimate / exact")
    a0.legend(loc="lower right")
    fig.tight_layout()
    caption = ("The naming model's estimate of each place over its exact posterior, on synthetic three-body fields with "
               "the seven measures: the median over runs and the interquartile range, on NUTS's draws, on independent "
               "draws from the exact posterior of the size, and on NUTS ten times as long.")
    return save(fig, outdir, "fixed_k_tail", caption) + [write_csv(outdir, "fixed_k_tail", rows)]


def write_figures_md(outdir: str, written: List[str], path: str = RECORD) -> str:
    import matplotlib
    import platform
    from .figures import SERIF, sha256
    here = os.path.dirname(os.path.abspath(__file__))
    lines = ["# The fixed-k NUTS review's figures", "",
             "Built with `python -m schwingcheck.fixed_k figures`.", ""]
    for p in (path, draws_path("seven", path)):
        lines.append("- Record: `%s`, sha256 %s." % (os.path.relpath(p, ROOT), sha256(p)))
    for name in ("figures.py", "fixed_k.py"):
        lines.append("- Code: `schwingcheck/%s`, sha256 %s." % (name, sha256(os.path.join(here, name))))
    lines += ["- Python %s, numpy %s, matplotlib %s; serif type %s, embedded in the PDF."
              % (platform.python_version(), np.__version__, matplotlib.__version__, SERIF[0]),
              "- The PDFs carry no creation date, so a rebuild with the same versions gives the same files; the CSVs "
              "beside them hold every number drawn.", "",
              "| Figure | Files | Caption |", "|---|---|---|"]
    for name in dict.fromkeys(os.path.basename(p).split(".")[0] for p in written):
        files = sorted(f for f in os.listdir(outdir) if f.split(".")[0] == name)
        with open(os.path.join(outdir, name + ".caption.txt"), encoding="ascii") as fh:
            caption = fh.read().strip().replace("|", "/")
        lines.append("| %s | %s | %s |" % (name, ", ".join("`%s`" % f for f in files), caption))
    out = os.path.join(outdir, "FIGURES.md")
    with open(out, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return out


def draw_figures(outdir: str = FIGURE_DIR, path: str = RECORD, figures_md: bool = True) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    record = load(path)
    written = (fig_trace(record, load_draws("seven", path), outdir) + fig_forest(record, outdir)
               + fig_mixing(record, outdir) + fig_tail(record, outdir))
    if figures_md:
        written.append(write_figures_md(outdir, written, path))
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.fixed_k")
    ap.add_argument("what", choices=("run", "table", "figures", "check"))
    ap.add_argument("--table", choices=("known", "free", "sharp", "tail", "spread", "categorical"), default="known")
    ap.add_argument("--out", default=RECORD, help="the record run writes, and the one table, figures and check read")
    ap.add_argument("--quick", action="store_true", help="every count shrunk, for the tests")
    a = ap.parse_args(argv)
    if a.what == "run":
        record, draws = run(quick=a.quick)
        print("wrote %s" % write(record, draws, a.out))
    elif a.what == "table":
        print(tables(a.out)["fixed_k:" + a.table], end="")
    elif a.what == "figures":
        for p in draw_figures(os.path.join(os.path.dirname(a.out), "figures"), a.out):
            print(os.path.relpath(p, ROOT))
    else:
        problems = check(path=a.out)
        for p in problems:
            print(p)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
