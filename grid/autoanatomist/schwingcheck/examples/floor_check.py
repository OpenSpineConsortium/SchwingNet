"""How often the generator's floor binds, and how far it moves the posterior where it does.

    PYTHONPATH=. python schwingcheck/examples/floor_check.py

The generator floors a value at 0.5 where its measure scales with the size (columns.py), and
the likelihood has no floor, so the rule is the generator's own posterior except where a value
sits at the floor. On the archive's seven the floor touched 4 of 308,000 values (README.md);
the pool adds areas and short lengths whose spread reaches it. For the seven and for the pool,
with the errors halved, as given and doubled, as the build-up study of step e runs them, this
prints how many values sat at the floor in 2,000 typical columns of seed 1234
(columns.floor_hits), in how many columns, and the measure-levels it touched most, how many of
them were areas and how many lengths, and the count at every measure it touched; then, over
the one-body fields holding such a value, how far the posterior over places moves, and on how
many fields the top place changes, when the value is scored by the generator's own mass at the
floor, P(raw <= 0.5 | place, size), in place of the likelihood's density at 0.5. One body's
value of one measure given the place and the size is normal with mean s^p mu and variance
(s^p sd)^2 + error^2, so that mass is one normal distribution function; a field of several
bodies would need the floored values' distribution given the rest, which this does not compute.
schwingcheck/README.md and measures.py quote what this printed on 28 October 2026.
"""
from __future__ import annotations

import numpy as np
from scipy.special import log_ndtr

from schwingcheck import columns as C
from schwingcheck import measures as MS
from schwingcheck import rule as R

SEED = 1234
N_COLUMNS = 2000
SCALES = (0.5, 1.0, 2.0)
CHUNK = 200


def floor_mass(mu, sd, noise, power, sizes):
    """log P(raw <= floor) for one body at every place, measure and node: (places, measures, nodes)."""
    g = R.size_factors(sizes, power, mu.shape[0])                       # (M, J)
    loc = mu.T[:, :, None] * g[None]
    spread = np.sqrt((sd.T[:, :, None] * g[None]) ** 2 + noise[None, :, None] ** 2)
    return log_ndtr((C.FLOOR - loc) / spread)


def one_body_shift(X, mu, sd, noise, power):
    """The posterior over places as the rule gives it and with each floored value scored by its
    mass at the floor, on the same Gauss-Hermite nodes."""
    sizes, logw = R.quadrature(R.SYNTH["scale_sd"])
    mass = floor_mass(mu, sd, noise, power, sizes)
    at = (X[:, :, 0] == C.FLOOR) & (power[None, :] > 0)                 # (fields, measures)
    rule, exact = [], []
    for f0 in range(0, len(X), CHUNK):
        LL = R.loglik(X[f0:f0 + CHUNK], [0], mu, sd, R.SYNTH, sizes=sizes, noise=noise, power=power)
        rule.append(R.posterior(R.log_evidence(LL, logw)))
        for f, m in np.argwhere(at[f0:f0 + CHUNK]):
            LL[f, :, m, :] = mass[:, m, :]
        exact.append(R.posterior(R.log_evidence(LL, logw)))
    return np.concatenate(rule), np.concatenate(exact)


def report(label, measures, scale):
    mu, sd = MS.arrays(measures)
    noise, power = MS.errors(measures) * scale, MS.powers(measures)
    cols = C.draw_columns(MS.reference(measures), ["typical"], SEED, N_COLUMNS,
                          [MS.archive_key(m) for m in measures], noise_mm=noise, power=power)
    hits = C.floor_hits(cols)
    most = ", ".join("%s %d" % kv for kv in list(hits["where"].items())[:4]) or "none"
    print("%s, errors x%g: %d of %d values at the floor (%.3f%%), in %d of %d columns; most at %s"
          % (label, scale, hits["values"], hits["of"], 100.0 * hits["values"] / hits["of"], hits["columns"],
             N_COLUMNS, most))
    power_of = dict(zip([MS.archive_key(m) for m in measures], power))
    by_measure = {}
    for key, count in hits["where"].items():
        name = key.rsplit(" ", 1)[0]
        by_measure[name] = by_measure.get(name, 0) + count
    areas = sum(count for name, count in by_measure.items() if power_of[name] == 2)
    print("    %d of them areas and %d lengths; by measure %s"
          % (areas, hits["values"] - areas,
             ", ".join("%s %d" % kv for kv in sorted(by_measure.items(), key=lambda kv: (-kv[1], kv[0]))) or "none"))
    X, _, _ = C.fields(cols.values, [0])
    keep = ((X[:, :, 0] == C.FLOOR) & (power[None, :] > 0)).any(1)
    if not keep.any():
        return
    rule, exact = one_body_shift(X[keep], mu, sd, noise, power)
    moved = np.abs(rule - exact).max(1)
    changed = int((rule.argmax(1) != exact.argmax(1)).sum())
    print("    one body: %d of %d fields hold a value at the floor; the posterior over places moves by at most %.3f "
          "(median %.4f) and the top place changes in %d" % (int(keep.sum()), len(X), moved.max(), np.median(moved), changed))


def main() -> int:
    for label, measures in (("the seven", MS.select(MS.SPINEPS_7)), ("the pool", MS.pool())):
        for scale in SCALES:
            report(label, measures, scale)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
