"""How sharply a visible run of k consecutive vertebrae names its levels (bordercall #56, step 5 of
#51): greg's question of 2026-10-30 23:30 UTC, whether landmarks found in a fluoroscopic shot of
any field of view can name each vertebra.

    python -m schwingcheck.run_naming run --prior <prior.json> --out records/run-naming-<date>
    python -m schwingcheck.run_naming run --stand-in --quick --out <scratch>     # the smoke

The model is the generator's, with one change: a column's standardised values are drawn from a
correlation prior (correlation.py), the levels and measures together, and a field is the k
consecutive bodies a shot shows, each with its measures, the patient's size and a measurement
error on top (columns.draw_columns with correlation=). Each hypothesis is a column type and a
place, the level of the run's first body; given it and the size, the field's kM values are one
multivariate normal, so its likelihood is exact, the size integrated on an even grid of log s.
The posterior over hypotheses comes from the types' prior weights (chain.WEIGHTS, with
autoanatomist/naming.py's four_lumbar at 0.05, all stated choices) and a uniform prior over places
within a type. An answer is right when the level names it gives the run are
the run's true names, whichever type gave them.

Two scorers read the same fields: the true structure (the prior the fields were drawn from) and
the generator's assumed structure (two levels of a measure at rho^2, measures uncorrelated),
which is what the rule uses today. Three views of where the run sits: no anchor (any place), the
bottom anchored (the run ends at the column's last body, the sacrum in view below it) and the top
anchored (the run starts at the first, C2 in view above it). An anchor is a reference bone, not a
read body: it fixes the place within a type and leaves the type to the values.

This measures the information the measures carry, in 3-D, with the error given. A 2-D shot shows
a projection of each measure, and a lateral view hides the widths that an anteroposterior one
shows, so a network's landmarks can do no better than this and may do worse. Nothing here is a
real image or a real spine.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from schwingcheck import columns as C
from schwingcheck import correlation as CORR
from schwingcheck import measures as SM

MEASURES = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post"]
TYPES = {"typical": 0.9, "six_lumbar": 0.05, "t13": 0.05, "four_lumbar": 0.05}   # chain.WEIGHTS and naming.py's
                                                                                  # four_lumbar, stated choices
K_RUN = (1, 2, 3, 4, 5, 6)
ANCHORS = ("none", "bottom", "top")
NOISE_MM = 1.0              # the generator's measurement error, every measure
SIZE_NODES = 81             # an even grid of log s over 6 prior SDs either side
SIZE_REACH = 6.0
FIELDS = 2000               # fields per type and run length
QUICK_FIELDS = 200
TARGET = 0.90               # the accuracy greg's question turns on: how many bodies reach it with no anchor
ECE_BINS = 10
PREREG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "records", "run-naming", "PREREG.md")
RHO = C.SYNTH["rho"]
SCALE_SD = C.SYNTH["scale_sd"]
BLEND = C.SYNTH["blend"]


def stand_in_prior() -> CORR.Prior:
    """A stand-in for the smoke only, never for a reported number: levels at 0.8 to the power of
    their distance, the widths and depths of one plate at 0.6, a width and its depth at 0.5."""
    levels = CORR.expand_levels("C3..L5")
    lag = np.abs(np.subtract.outer(np.arange(len(levels)), np.arange(len(levels))))
    rm = np.array([[1.0, 0.5, 0.6, 0.4, 0.3], [0.5, 1.0, 0.4, 0.6, 0.2], [0.6, 0.4, 1.0, 0.5, 0.3],
                   [0.4, 0.6, 0.5, 1.0, 0.2], [0.3, 0.2, 0.3, 0.2, 1.0]])
    return CORR.Prior(levels=levels, measures=list(MEASURES), r_level=0.8 ** lag, r_measure=rm, n=0,
                      note="stand-in for the smoke, not fitted")


class Setting:
    """The table's means and spreads per type, the measures' powers of the size and the size grid."""

    def __init__(self, measures: Sequence[str] = MEASURES):
        self.measures = list(measures)
        ms = SM.select(self.measures)
        self.ref = SM.reference(ms)
        self.powers = SM.powers(ms)
        self.profiles = {t: C.profiles(self.ref, self.measures, t, BLEND) for t in TYPES}
        t = np.linspace(-SIZE_REACH * SCALE_SD, SIZE_REACH * SCALE_SD, SIZE_NODES)
        logw = -0.5 * (t / SCALE_SD) ** 2
        self.sizes = np.exp(t)
        self.logw = logw - np.logaddexp.reduce(logw)

    def levels(self, t: str) -> List[str]:
        return list(self.profiles[t][0])


def correlation(structure: str, prior: CORR.Prior, levels: Sequence[str], M: int) -> np.ndarray:
    """The standardised values' correlation of a run of these levels, levels-major as vec(X)."""
    if structure == "true":
        return np.kron(CORR.level_block(prior, levels), CORR.measure_block(prior, MEASURES[:M]))
    return CORR.assumed_cov(len(levels), M, RHO, 0.0)


def hypotheses(s: Setting, k: int, anchor: str) -> List[Tuple[str, int]]:
    """Every (type, place) a run of k bodies can be under the anchor."""
    out = []
    for t in TYPES:
        n = len(s.levels(t))
        places = range(n - k + 1)
        if anchor == "bottom":
            places = [n - k]
        elif anchor == "top":
            places = [0]
        out.extend((t, p) for p in places if p >= 0)
    return out


def hypothesis_loglik(X: np.ndarray, s: Setting, prior: CORR.Prior, structure: str, t: str, p: int, k: int) -> np.ndarray:
    """log p(field | type, place) for every field of X (fields, k*M levels-major), the size integrated."""
    lv, _, mu, sd = s.profiles[t]
    M = len(s.measures)
    names = lv[p:p + k]
    m = mu[:, p:p + k].T.ravel()
    d = sd[:, p:p + k].T.ravel()
    pw = np.tile(s.powers, k)
    R = correlation(structure, prior, names, M)
    per_node = np.empty((len(X), len(s.sizes)))
    for j, size in enumerate(s.sizes):
        g = size ** pw
        cov = np.outer(g * d, g * d) * R + NOISE_MM ** 2 * np.eye(k * M)
        per_node[:, j] = CORR.mvn_loglik((X - g * m)[:, :, None], cov)
    return np.logaddexp.reduce(per_node + s.logw[None, :], axis=1)


def posterior(X: np.ndarray, s: Setting, prior: CORR.Prior, structure: str, k: int, anchor: str):
    """(hypotheses, posterior (fields, hypotheses))."""
    hyps = hypotheses(s, k, anchor)
    per_type = {t: sum(1 for h in hyps if h[0] == t) for t in TYPES}
    log_prior = np.array([math.log(TYPES[t] / per_type[t]) for t, _ in hyps])
    ll = np.stack([hypothesis_loglik(X, s, prior, structure, t, p, k) for t, p in hyps], axis=1) + log_prior
    ll -= np.logaddexp.reduce(ll, axis=1, keepdims=True)
    return hyps, np.exp(ll)


def draw_fields(s: Setting, prior: CORR.Prior, t: str, k: int, anchor: str, n: int, seed: int):
    """n fields of k bodies from columns of type t drawn from the prior: values (n, k*M) and each
    field's true level names."""
    cols = C.draw_columns(s.ref, [t], seed, n, s.measures, noise_mm=NOISE_MM, power=s.powers,
                          correlation=prior)
    rng = np.random.default_rng(seed + 1)
    L = len(s.levels(t))
    X, names = [], []
    for c in range(n):
        p = {"bottom": L - k, "top": 0}.get(anchor, int(rng.integers(0, L - k + 1)))
        X.append(cols.values[c, p:p + k, :].ravel())
        names.append(tuple(cols.levels[c][p:p + k]))
    return np.array(X), names


def names_of(s: Setting, hyp: Tuple[str, int], k: int) -> tuple:
    t, p = hyp
    return tuple(s.levels(t)[p:p + k])


def wilson(hits: int, n: int, z: float = 1.959964) -> Tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    ph = hits / n
    den = 1 + z * z / n
    mid = (ph + z * z / (2 * n)) / den
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return mid - half, mid + half


def scores(s: Setting, hyps, post: np.ndarray, truth: Sequence[tuple], k: int) -> dict:
    """Top-1 accuracy with its interval, the mean probability of the true names, and the expected
    calibration error of the top answer."""
    labels = [names_of(s, h, k) for h in hyps]
    unique = sorted(set(labels))
    col = {u: i for i, u in enumerate(unique)}
    P = np.zeros((len(post), len(unique)))
    for j, u in enumerate(labels):
        P[:, col[u]] += post[:, j]
    top = P.argmax(axis=1)
    conf = P.max(axis=1)
    right = np.array([unique[top[i]] == truth[i] for i in range(len(truth))])
    p_true = np.array([P[i, col[truth[i]]] if truth[i] in col else 0.0 for i in range(len(truth))])
    ece = 0.0
    edges = np.linspace(0, 1, ECE_BINS + 1)
    for a, b in zip(edges[:-1], edges[1:]):
        inside = (conf > a) & (conf <= b)
        if inside.any():
            ece += inside.mean() * abs(right[inside].mean() - conf[inside].mean())
    lo, hi = wilson(int(right.sum()), len(right))
    return dict(n=int(len(right)), accuracy=float(right.mean()), lo=lo, hi=hi,
                p_true=float(p_true.mean()), ece=float(ece))


def run(prior: CORR.Prior, n: int = FIELDS, ks: Sequence[int] = K_RUN, log=print) -> List[dict]:
    s = Setting()
    rows = []
    for anchor in ANCHORS:
        for k in ks:
            for t in TYPES:
                seed = 1000 * k + 10 * ANCHORS.index(anchor) + list(TYPES).index(t)
                X, truth = draw_fields(s, prior, t, k, anchor, n, seed)
                for structure in ("true", "assumed"):
                    hyps, post = posterior(X, s, prior, structure, k, anchor)
                    row = dict(anchor=anchor, k=k, type=t, structure=structure, **scores(s, hyps, post, truth, k))
                    rows.append(row)
                    log("%-6s k=%d %-10s %-7s acc %.3f [%.3f, %.3f] p_true %.3f ece %.3f"
                        % (anchor, k, t, structure, row["accuracy"], row["lo"], row["hi"], row["p_true"], row["ece"]))
    return rows


def answer(rows: List[dict]) -> dict:
    """The fewest bodies whose typical-column accuracy with no anchor, under the true structure,
    reaches TARGET at its interval's lower bound, or None."""
    for k in sorted({r["k"] for r in rows}):
        r = [x for x in rows if x["k"] == k and x["anchor"] == "none" and x["type"] == "typical" and x["structure"] == "true"]
        if r and r[0]["lo"] >= TARGET:
            return dict(k=k, accuracy=r[0]["accuracy"], lo=r[0]["lo"])
    return dict(k=None)


def figure(rows: List[dict], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    styles = {"true": ("#1f6feb", "-"), "assumed": ("#9a6700", "--")}
    for ax, anchor in zip(axes, ANCHORS):
        for t, marker in zip(TYPES, ("o", "s", "^", "D")):
            for structure, (colour, line) in styles.items():
                r = sorted([x for x in rows if x["anchor"] == anchor and x["type"] == t and x["structure"] == structure],
                           key=lambda x: x["k"])
                if not r:
                    continue
                k = [x["k"] for x in r]
                acc = [x["accuracy"] for x in r]
                err = [[max(0.0, x["accuracy"] - x["lo"]) for x in r], [max(0.0, x["hi"] - x["accuracy"]) for x in r]]
                ax.errorbar(k, acc, yerr=err, color=colour, linestyle=line, marker=marker, markersize=4, capsize=2,
                            label="%s, %s" % (t, structure))
        ax.axhline(TARGET, color="#6e7781", linewidth=0.8)
        ax.set_title("anchor: %s" % anchor)
        ax.set_xlabel("visible vertebrae")
    axes[0].set_ylabel("top-1 level accuracy")
    axes[0].set_ylim(0, 1.02)
    axes[-1].legend(fontsize=7, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def prereg_digest() -> Optional[str]:
    """The frozen PREREG's sha256 when the file matches the digest frozen beside it, else None."""
    try:
        with open(PREREG, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        with open(PREREG + ".sha256") as f:
            frozen = f.read().split()[0]
    except (OSError, IndexError):
        return None
    return digest if digest == frozen else None


def write(rows: List[dict], prior: CORR.Prior, prior_path: Optional[str], out: str, n: int) -> str:
    os.makedirs(out, exist_ok=True)
    digest = None
    if prior_path:
        with open(prior_path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    record = dict(settings=dict(measures=MEASURES, types=TYPES, k=list(K_RUN), anchors=list(ANCHORS), noise_mm=NOISE_MM,
                                size_nodes=SIZE_NODES, size_reach=SIZE_REACH, rho=RHO, scale_sd=SCALE_SD, fields=n,
                                target=TARGET),
                  prior=dict(note=prior.note, n=prior.n, levels=prior.levels, sha256=digest),
                  prereg_sha256=prereg_digest(),
                  answer=answer(rows), rows=rows)
    path = os.path.join(out, "run_naming.json")
    with open(path, "w") as f:
        json.dump(record, f, indent=1)
        f.write("\n")
    figure(rows, os.path.join(out, "accuracy.png"))
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.run_naming")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--prior", help="a fitted prior's JSON (correlation.Prior.to_json)")
    r.add_argument("--stand-in", action="store_true", help="the smoke's stand-in prior, never for a reported number")
    r.add_argument("--quick", action="store_true")
    r.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if bool(a.prior) == bool(a.stand_in):
        ap.error("give --prior or --stand-in")
    if a.prior and prereg_digest() is None:
        print("refusing: records/run-naming/PREREG.md is missing or differs from its frozen digest", file=sys.stderr)
        return 90
    if a.prior:
        with open(a.prior) as f:
            prior = CORR.Prior.from_json(json.load(f))
    else:
        prior = stand_in_prior()
    n = QUICK_FIELDS if a.quick else FIELDS
    rows = run(prior, n)
    print(write(rows, prior, a.prior, a.out, n))
    print(json.dumps(answer(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
