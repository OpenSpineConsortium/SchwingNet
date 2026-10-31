"""How often a phantom vertebra's upper and lower end-plate widths disagree, under the fitted
ENHANCE.PET C3..L5 correlation prior and under alternatives.

Imports nothing from bordercall or SchwingNet. It copies the math of
bordercall schwingcheck/columns.py draw_columns (correlation= branch and the default branch) and
schwingcheck/correlation.py (nearest_pd, level_block for a typical C3..L5 column, draw_field):

    value[m, l] = s * (mu[m][l] + sd[m][l] * field[m, l]) + noise * n[m, l],   s = exp(N(0, 0.07^2))
    field = chol(R_measure) @ E @ chol(R_level).T,   E iid N(0, 1)            (with a prior)
    field = rho * z[m] + sqrt(1 - rho^2) * e[m, l], z iid across measures      (no prior: rho 0.5, r_between 0)

Inputs (paths as arguments): the Panjabi table extracted by read_table.py (means and population SD,
sem * sqrt(n)), the prior JSON, and optionally a margins JSON from the gold tier aggregate table.
"""
import json
import math
import sys

import numpy as np

MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
W_TOP, D_TOP, W_BOT, D_BOT, H = range(5)
SCALE_SD = 0.07
RHO = 0.5
N = 200_000
THRESHOLDS = (0.10, 0.20)


def nearest_pd(r, floor=1e-6):
    w, v = np.linalg.eigh(r)
    if w.min() >= floor:
        return r
    fixed = (v * np.maximum(w, floor)) @ v.T
    d = np.sqrt(np.diag(fixed))
    out = fixed / np.outer(d, d)
    np.fill_diagonal(out, 1.0)
    return (out + out.T) / 2


def draw_prior_fields(rng, r_level, r_measure, n):
    """n fields (n, measures, levels) from the matrix normal, as correlation.draw_field."""
    al = np.linalg.cholesky(nearest_pd(r_level))
    am = np.linalg.cholesky(r_measure)
    e = rng.normal(size=(n, r_measure.shape[0], r_level.shape[0]))
    return np.einsum("ij,njk,lk->nil", am, e, al)


def draw_assumed_fields(rng, M, L, n, rho=RHO):
    """The default generator's field: one offset per measure shared by every level, r_between 0."""
    z = rng.normal(size=(n, M, 1))
    e = rng.normal(size=(n, M, L))
    return rho * z + math.sqrt(1 - rho * rho) * e


def values(rng, mu, sd, field, noise_mm):
    """mu, sd (measures, levels); field (n, measures, levels); lengths, power 1, floor 0.5."""
    n = field.shape[0]
    s = np.exp(rng.normal(0.0, SCALE_SD, size=(n, 1, 1)))
    v = s * (mu[None] + sd[None] * field)
    if noise_mm:
        v = v + noise_mm * rng.normal(size=v.shape)
    return np.maximum(v, 0.5)


def mismatch(a, b, mu_a, mu_b):
    """Two readings of one vertebra: |a - b| over their mean, and the excess over the population's
    mean ratio, |(a / b) / (mu_a / mu_b) - 1|."""
    raw = np.abs(a - b) / (0.5 * (a + b))
    excess = np.abs((a / b) / (mu_a / mu_b) - 1.0)
    return raw, excess


def margins(table, levels):
    mu = np.array([[table[m][l][0] for l in levels] for m in MEASURES])
    sd = np.array([[table[m][l][1] for l in levels] for m in MEASURES])
    return mu, sd


def scenario_rows(name, v, mu, levels):
    """Per level and pooled: shares of vertebrae past each threshold, raw and excess, and the
    Pearson r of the two widths as drawn (size included)."""
    raw, excess = mismatch(v[:, W_TOP], v[:, W_BOT], mu[W_TOP][None], mu[W_BOT][None])
    out = dict(name=name, per_level={}, pooled={})
    for j, l in enumerate(levels):
        r = float(np.corrcoef(v[:, W_TOP, j], v[:, W_BOT, j])[0, 1])
        out["per_level"][l] = dict(
            raw={str(t): float((raw[:, j] > t).mean()) for t in THRESHOLDS},
            excess={str(t): float((excess[:, j] > t).mean()) for t in THRESHOLDS},
            r_widths_as_drawn=r)
    out["pooled"] = dict(raw={str(t): float((raw > t).mean()) for t in THRESHOLDS},
                         excess={str(t): float((excess > t).mean()) for t in THRESHOLDS},
                         median_raw=float(np.median(raw)), median_excess=float(np.median(excess)),
                         p95_excess=float(np.quantile(excess, 0.95)))
    return out


def across_disc(v, mu, levels):
    """The lower plate of one level against the upper plate of the next, across the disc."""
    a, b = v[:, W_BOT, :-1], v[:, W_TOP, 1:]
    raw, excess = mismatch(a, b, mu[W_BOT][None, :-1], mu[W_TOP][None, 1:])
    return dict(raw={str(t): float((raw > t).mean()) for t in THRESHOLDS},
                excess={str(t): float((excess > t).mean()) for t in THRESHOLDS},
                r_as_drawn_mean=float(np.mean([np.corrcoef(a[:, j], b[:, j])[0, 1] for j in range(a.shape[1])])))


def analytic_share(mu_a, sd_a, mu_b, sd_b, r, t):
    """P(|a - b| > t * (mu_a + mu_b) / 2) for a bivariate normal, the denominator held at the means
    and the size left out (it cancels in a ratio): a check on the simulation."""
    from math import erf, sqrt
    m = mu_a - mu_b
    s = sqrt(sd_a ** 2 + sd_b ** 2 - 2 * r * sd_a * sd_b)
    c = t * 0.5 * (mu_a + mu_b)
    cdf = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
    return 1 - (cdf((c - m) / s) - cdf((-c - m) / s))


def main(table_path, prior_path, out_path, gold_path=None):
    rng = np.random.default_rng(20261031)
    tab = json.load(open(table_path))
    prior = json.load(open(prior_path))
    levels = prior["levels"]
    assert levels == tab["levels"], "the prior and the table name different levels"
    r_level = np.array(prior["r_level"], float)
    r_measure = np.array(prior["r_measure"], float)
    width_08 = r_measure.copy()
    width_08[W_TOP, W_BOT] = width_08[W_BOT, W_TOP] = 0.8
    raw_unshrunk = r_measure.copy()
    raw_unshrunk[W_TOP, W_BOT] = raw_unshrunk[W_BOT, W_TOP] = r_measure[W_TOP, W_BOT] / 0.95
    sources = [("panjabi", margins(tab["ref"], levels))]
    if gold_path:
        sources.append(("gold_enhance_229", margins(json.load(open(gold_path))["ref"], levels)))
    report = dict(n_per_scenario=N, scale_sd=SCALE_SD, thresholds=THRESHOLDS,
                  r_width_pair=dict(fitted=float(r_measure[W_TOP, W_BOT]), unshrunk=float(raw_unshrunk[W_TOP, W_BOT])),
                  results={})
    for source, (mu, sd) in sources:
        for noise in (0.0, 1.0):
            fields = {
                "fitted_prior": draw_prior_fields(rng, r_level, r_measure, N),
                "fitted_prior_width_pair_0.8": draw_prior_fields(rng, r_level, width_08, N),
                "no_prior_assumed_rho0.5": draw_assumed_fields(rng, len(MEASURES), len(levels), N),
            }
            for name, f in fields.items():
                v = values(rng, mu, sd, f, noise)
                key = "%s|noise%.0f|%s" % (source, noise, name)
                res = scenario_rows(name, v, mu, levels)
                res["across_disc"] = across_disc(v, mu, levels)
                report["results"][key] = res
        checks = {}
        for name, r in (("fitted_prior", r_measure[W_TOP, W_BOT]), ("width_pair_0.8", 0.8), ("no_prior", 0.0)):
            checks[name] = {str(t): float(np.mean([analytic_share(mu[W_TOP][j], sd[W_TOP][j], mu[W_BOT][j], sd[W_BOT][j], r, t)
                                                   for j in range(len(levels))])) for t in THRESHOLDS}
        report["analytic_pooled_raw_noise0_" + source] = checks
    json.dump(report, open(out_path, "w"), indent=1)
    return report


if __name__ == "__main__":
    rep = main(*sys.argv[1:])
    for key, res in rep["results"].items():
        p = res["pooled"]
        d = res["across_disc"]
        print("%-62s raw>10%% %.3f raw>20%% %.3f | excess>10%% %.3f excess>20%% %.3f | med excess %.3f p95 %.3f | disc raw>10%% %.3f excess>10%% %.3f r %.2f"
              % (key, p["raw"]["0.1"], p["raw"]["0.2"], p["excess"]["0.1"], p["excess"]["0.2"], p["median_excess"],
                 p["p95_excess"], d["raw"]["0.1"], d["excess"]["0.1"], d["r_as_drawn_mean"]))
    for k, v in rep.items():
        if k.startswith("analytic"):
            print(k, json.dumps(v))
