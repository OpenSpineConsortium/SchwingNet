"""How well the two quadratures integrate the size out once every measure of the pool is read.

    PYTHONPATH=. python schwingcheck/examples/quadrature_check.py

rule.py's docstring quotes what this prints, from its runs of 27 and 28 October 2026: 40 typical
columns of seed 1234 with all 32 measures of the pool, each with its own error and power of the
size, at 1, 3 and 9 bodies. For each width it gives the error of the log evidence at the true
place of the Gauss-Hermite rule (161 nodes) and of the trapezoid rule (step 0.004) against a
trapezoid rule four times as fine, the largest error of the posterior over places, and the
posterior SD of log s at the true place, which is what the nodes must resolve. Far from the
truth a place asks for a size past the trapezoid's reach of 8 prior SDs, where every trapezoid
grid of that reach falls short alike, so the fine grid is no reference there: at the three places
of each width where Gauss-Hermite and the fine grid part most, the three rules are set against
the closed form summed on a grid of step 0.0005 out to 40 prior SDs.
"""
from __future__ import annotations

import numpy as np

from schwingcheck import columns as C
from schwingcheck import measures as MS
from schwingcheck import rule as R

SEED = 1234
N_COLUMNS = 40
WIDE_STEP = 0.0005
WIDE_REACH = 40.0


def size_sd_at_truth(LL: np.ndarray, logw: np.ndarray, sizes: np.ndarray, truth: np.ndarray) -> np.ndarray:
    """The posterior SD of log s given the true place, one per field."""
    total = LL.sum(2) + logw
    a = total[np.arange(len(truth)), truth]
    w = np.exp(a - a.max(1, keepdims=True))
    w /= w.sum(1, keepdims=True)
    t = np.log(sizes)
    mean = (w * t).sum(1)
    return np.sqrt((w * (t - mean[:, None]) ** 2).sum(1))


def wide_evidence(x, place, offsets, mu, sd, noise, power) -> float:
    """One field's log evidence at one place, the closed form summed on a grid of step 0.0005 out
    to 40 prior SDs, wider than any place of these fields asks for."""
    sizes, logw = R.trapezoid(R.SYNTH["scale_sd"], step=WIDE_STEP, reach=WIDE_REACH)
    span = int(offsets[-1]) + 1
    LL = R.loglik(x[None], offsets, mu[:, place:place + span], sd[:, place:place + span], R.SYNTH,
                  sizes=sizes, noise=noise, power=power)
    return float(R.log_evidence(LL, logw)[0, 0])


def main() -> int:
    pool = MS.pool()
    mu, sd = MS.arrays(pool)
    noise, power = MS.errors(pool), MS.powers(pool)
    cols = C.draw_columns(MS.reference(pool), ["typical"], SEED, N_COLUMNS, [MS.archive_key(m) for m in pool],
                          noise_mm=noise, power=power)
    rules = {"gauss-hermite": R.quadrature(R.SYNTH["scale_sd"]), "trapezoid": R.trapezoid(R.SYNTH["scale_sd"]),
             "fine": R.trapezoid(R.SYNTH["scale_sd"], step=0.001)}
    print("%d measures, %d columns of seed %d; nodes: %s" % (len(pool), N_COLUMNS, SEED,
                                                             ", ".join("%s %d" % (k, len(v[0])) for k, v in rules.items())))
    for n in (1, 3, 9):
        offsets = np.arange(n)
        X, truth, _ = C.fields(cols.values, offsets)
        out = {}
        for name, (sizes, logw) in rules.items():
            LL = R.loglik(X, offsets, mu, sd, R.SYNTH, sizes=sizes, noise=noise, power=power)
            ev = R.log_evidence(LL, logw)
            out[name] = (ev, R.posterior(ev), LL, logw, sizes)
        fine_ev, fine_post = out["fine"][0], out["fine"][1]
        for name in ("gauss-hermite", "trapezoid"):
            d = np.abs(out[name][0] - fine_ev)
            print("%d bodies, %s: log evidence at the true place off by at most %.1e; posterior over places by %.1e"
                  % (n, name, d[np.arange(len(truth)), truth].max(), np.abs(out[name][1] - fine_post).max()))
        gap = np.abs(out["gauss-hermite"][0] - fine_ev)
        gh_off, trap_off, fine_off = [], [], []
        for flat in np.argsort(-gap.ravel())[:3]:
            f, k = np.unravel_index(flat, gap.shape)
            wide = wide_evidence(X[f], k, offsets, mu, sd, noise, power)
            gh_off.append(abs(out["gauss-hermite"][0][f, k] - wide))
            trap_off.append(abs(out["trapezoid"][0][f, k] - wide))
            fine_off.append(abs(fine_ev[f, k] - wide))
        print("%d bodies, the three places where the two rules part most (by %s): against a grid of step %g out to %g "
              "prior SDs, Gauss-Hermite off by %s, the trapezoid by %s and the fine trapezoid by %s"
              % (n, ", ".join("%.3g" % g for g in np.sort(gap.ravel())[::-1][:3]), WIDE_STEP, WIDE_REACH,
                 ", ".join("%.1e" % v for v in gh_off), ", ".join("%.3g" % v for v in trap_off),
                 ", ".join("%.3g" % v for v in fine_off)))
        s = size_sd_at_truth(out["fine"][2], out["fine"][3], out["fine"][4], truth)
        print("%d bodies: posterior SD of log s at the true place %.3f to %.3f" % (n, s.min(), s.max()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
