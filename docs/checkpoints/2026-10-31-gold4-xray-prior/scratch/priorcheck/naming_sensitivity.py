"""How much run_naming's answer leans on the fitted within-vertebra correlation: a reduced copy of
bordercall schwingcheck/run_naming.py (typical column only, no anchor, the true scorer), run with the
fitted ENHANCE.PET C3..L5 prior and with the same prior whose upper and lower end-plate widths (and,
in a second variant, depths) correlate at 0.8. Imports nothing from the repositories.

Copied math: fields from draw_columns(correlation=prior) with a 1 mm error; each hypothesis (a place
of the k-body run) scored by the exact multivariate normal, levels-major, cov = (g d)(g d)' * kron(R_level
block, R_measure) + noise^2 I, the size integrated on 81 even nodes of log s over 6 SDs either side.
The study's other column types (six_lumbar, t13, four_lumbar at 0.05 each) are left out, so these
accuracies are not the PREREG's outcome, only a measure of how far R_measure moves it.
"""
import json
import math
import sys

import numpy as np

SCALE_SD, NOISE_MM, NODES, REACH = 0.07, 1.0, 81, 6.0
W_TOP, D_TOP, W_BOT, D_BOT, H = range(5)


def nearest_pd(r, floor=1e-6):
    w, v = np.linalg.eigh(r)
    if w.min() >= floor:
        return r
    fixed = (v * np.maximum(w, floor)) @ v.T
    d = np.sqrt(np.diag(fixed))
    out = fixed / np.outer(d, d)
    np.fill_diagonal(out, 1.0)
    return (out + out.T) / 2


def draw_fields(rng, mu, sd, r_level, r_measure, k, n):
    """n runs of k bodies at uniform places, levels-major values (n, k*M), and the true places."""
    M, L = mu.shape
    al = np.linalg.cholesky(nearest_pd(r_level))
    am = np.linalg.cholesky(r_measure)
    e = rng.normal(size=(n, M, L))
    field = np.einsum("ij,njk,lk->nil", am, e, al)
    s = np.exp(rng.normal(0.0, SCALE_SD, size=(n, 1, 1)))
    v = s * (mu[None] + sd[None] * field) + NOISE_MM * rng.normal(size=(n, M, L))
    v = np.maximum(v, 0.5)
    places = rng.integers(0, L - k + 1, size=n)
    X = np.stack([v[i, :, p:p + k].T.ravel() for i, p in enumerate(places)])
    return X, places


def loglik(X, mu, sd, r_level, r_measure, p, k, sizes, logw):
    M = mu.shape[0]
    m = mu[:, p:p + k].T.ravel()
    d = sd[:, p:p + k].T.ravel()
    R = np.kron(nearest_pd(r_level[p:p + k, p:p + k]), r_measure)
    per = np.empty((len(X), len(sizes)))
    for j, g in enumerate(sizes):
        cov = np.outer(g * d, g * d) * R + NOISE_MM ** 2 * np.eye(k * M)
        c = np.linalg.cholesky(cov)
        z = np.linalg.solve(c, (X - g * m).T)
        per[:, j] = -0.5 * (k * M * math.log(2 * math.pi) + 2 * np.log(np.diag(c)).sum() + (z * z).sum(0))
    return np.logaddexp.reduce(per + logw[None], axis=1)


def accuracy(rng, mu, sd, r_level, r_measure, k, n):
    t = np.linspace(-REACH * SCALE_SD, REACH * SCALE_SD, NODES)
    logw = -0.5 * (t / SCALE_SD) ** 2
    logw -= np.logaddexp.reduce(logw)
    sizes = np.exp(t)
    X, truth = draw_fields(rng, mu, sd, r_level, r_measure, k, n)
    L = mu.shape[1]
    ll = np.stack([loglik(X, mu, sd, r_level, r_measure, p, k, sizes, logw) for p in range(L - k + 1)], axis=1)
    post = np.exp(ll - np.logaddexp.reduce(ll, axis=1, keepdims=True))
    hit = post.argmax(1) == truth
    acc = hit.mean()
    z = 1.959964
    den = 1 + z * z / n
    mid = (acc + z * z / (2 * n)) / den
    half = z * math.sqrt(acc * (1 - acc) / n + z * z / (4 * n * n)) / den
    return dict(accuracy=float(acc), lo=float(mid - half), hi=float(mid + half),
                p_true=float(post[np.arange(n), truth].mean()))


def main(table_path, prior_path, out_path, n=2000):
    tab, prior = json.load(open(table_path)), json.load(open(prior_path))
    levels = prior["levels"]
    mu = np.array([[tab["ref"][m][l][0] for l in levels] for m in prior["measures"]])
    sd = np.array([[tab["ref"][m][l][1] for l in levels] for m in prior["measures"]])
    rl, rm = np.array(prior["r_level"]), np.array(prior["r_measure"])
    widths = rm.copy()
    widths[W_TOP, W_BOT] = widths[W_BOT, W_TOP] = 0.8
    both = widths.copy()
    both[D_TOP, D_BOT] = both[D_BOT, D_TOP] = 0.8
    variants = {"fitted": rm, "widths_0.8": widths, "widths_and_depths_0.8": both}
    out = {}
    for name, r in variants.items():
        assert np.linalg.eigvalsh(r).min() > 0, name
        for k in (1, 2, 3, 4):
            rng = np.random.default_rng(1000 * k + 7)
            res = accuracy(rng, mu, sd, rl, r, k, int(n))
            out["%s|k%d" % (name, k)] = res
            print("%-24s k=%d acc %.3f [%.3f, %.3f] p_true %.3f" % (name, k, res["accuracy"], res["lo"], res["hi"], res["p_true"]))
            sys.stdout.flush()
    json.dump(out, open(out_path, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:])
