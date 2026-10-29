"""Which fields the rule names wrong at a posterior of 0.99 on the anomalous spines, with all 32 measures.

    PYTHONPATH=. python schwingcheck/examples/anomalous_check.py

On the build-up study's own anomalous columns (curve.py: seeds 99 and 314, 150 columns of each
spine), with every measure of the pool, at 1, 3, 5 and 9 bodies, this prints for each spine that
holds a body out of the typical run the fields named at 0.99, how many of them are wrong, how many
of the wrong ones hold that body, and the window of each wrong one that does not. The body is the
L6 of a six-lumbar spine and the T13 of a spine with a thirteenth rib-bearing body, names the rule
does not have, and the rib-bearing L1 of a rib on L1 and the ribless T12 of no rib on T12, which
the generator draws half-way between T12 and L1 (columns.SYNTH's blend), as it draws the T13. A
four-lumbar spine has no such body. At nine bodies it prints the wrong ones by the body in their
middle too. The counts named and wrong are held to the study's record, the nominal arm's all 32,
where records/curve-2026-10-28/curve.nc is there; schwingcheck/README.md quotes what this printed
on 28 October 2026.
"""
from __future__ import annotations

import os
from collections import Counter

import numpy as np

from schwingcheck import columns as C
from schwingcheck import curve as CV
from schwingcheck import measures as MS
from schwingcheck import rule as R
from schwingcheck import score as S

SPINES = {"six_lumbar": "the L6", "t13": "the T13", "lumbar_rib": "the rib-bearing L1", "no_rib_t12": "the ribless T12"}
WIDTHS = (1, 3, 5, 9)
RECORD = os.path.join("records", "curve-2026-10-28", "curve.nc")
CHUNK = 10                                       # columns at a time: nine bodies of 32 measures are 150 MB a chunk


def odd_body(c: C.Columns, k: int) -> int:
    """Where column k's body out of the typical run sits: its transitional body, else its L6."""
    at = c.transitional_at[k]
    return c.levels[k].index("L6") if at is None else at


def wrong_fields(c: C.Columns, n: int, mu, sd, noise, power, nodes):
    """Every field of n bodies: whether it is named at 0.99, whether wrongly, whether it holds the
    odd body, and its column and start."""
    offsets = np.arange(n)
    out = {"named": [], "wrong": [], "holds": [], "start": [], "col": []}
    for c0 in range(0, len(c.levels), CHUNK):
        levels = c.levels[c0:c0 + CHUNK]
        X, start, col = C.fields(c.values[c0:c0 + CHUNK], offsets)
        LL = R.loglik(X, offsets, mu, sd, R.SYNTH, sizes=nodes[0], noise=noise, power=power)
        post = R.posterior(R.logsumexp(LL.sum(2) + nodes[1], 2))
        st = CV.field_stats(post, start, CV.true_positions(start, col, levels, n), n, False)
        named = st["top"] >= CV.CLAIM
        out["named"].append(named)
        out["wrong"].append(named & ~st["hit"])
        out["holds"].append(np.array([s <= odd_body(c, c0 + k) < s + n for s, k in zip(start, col)]))
        out["start"].append(start)
        out["col"].append(col + c0)
    return {key: np.concatenate(v) for key, v in out.items()}


def recorded(spine: str, n: int):
    """The record's count named at 0.99 and count wrong for the spine with all 32 measures, or None."""
    if not os.path.exists(RECORD):
        return None
    import xarray as xr
    from schwingcheck import curve_report as CR
    ds = CR.rates_of(xr.open_datatree(RECORD, engine="h5netcdf"))
    return tuple(int(CR.value(ds, stat, "nominal", spine, "prefix-32", n)) for stat in ("n_answered", "errors"))


def report(spine: str, pool, mu, sd, noise, power, nodes) -> None:
    c = CV.draw_pool(pool, spine, CV.ANOMALOUS_SEED, CV.ANOMALOUS_EXTRA_SEED, CV.N_ANOMALOUS)
    for n in WIDTHS:
        f = wrong_fields(c, n, mu, sd, noise, power, nodes)
        named, wrong = int(f["named"].sum()), int(f["wrong"].sum())
        held = recorded(spine, n)
        if held is not None and held != (named, wrong):
            raise AssertionError("%s at %d bodies: %r named and wrong here, %r in the record"
                                 % (spine, n, (named, wrong), held))
        print("%s, %d %s: %d of %d fields named at 0.99, %d of them wrong (%.2f%%), %d of those holding %s%s"
              % (spine, n, "body" if n == 1 else "bodies", named, len(f["named"]), wrong, 100.0 * wrong / max(named, 1),
                 int((f["wrong"] & f["holds"]).sum()), SPINES[spine], ", as the record" if held is not None else ""))
        others = Counter()
        for i in np.flatnonzero(f["wrong"] & ~f["holds"]):
            lv, s = c.levels[f["col"][i]], f["start"][i]
            others[lv[s] if n == 1 else "%s to %s" % (lv[s], lv[s + n - 1])] += 1
        if others:
            print("    wrong and not holding it: " + ", ".join("%s %d" % kv for kv in sorted(others.items())))
        if n == WIDTHS[-1] and wrong:
            middle = Counter(c.levels[f["col"][i]][f["start"][i] + S.target_offset(n)]
                             for i in np.flatnonzero(f["wrong"]))
            print("    wrong by middle body: " + ", ".join("%s %d" % kv for kv in sorted(middle.items())))


def main() -> int:
    pool = MS.pool()
    mu, sd = MS.arrays(pool)
    nodes = R.trapezoid(R.SYNTH["scale_sd"])
    for spine in SPINES:
        report(spine, pool, mu, sd, MS.errors(pool), MS.powers(pool), nodes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
