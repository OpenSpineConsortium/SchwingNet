"""How a person's measures move together across levels and across measures, fitted from real spines.

The published tables give each level's mean and SD of each measure and nothing about how they
covary, so the generator (columns.draw_columns) assumes a structure: one offset z per measure
shared by every level with weight rho, and an independent draw per level, so two levels of one
measure correlate at rho squared (0.25 at the default rho 0.5), and two measures correlate only
through r_between, which is 0 by default. A set of whole real spines, such as the gold tier 3
CTs' morphometry rows, can estimate that structure instead.

The model is a matrix normal on the standardised values of one spine, X (levels x measures):
vec(X) ~ N(0, R_level kron R_measure), a correlation between levels shared by every measure and
a correlation between measures shared by every level. It is fitted by the flip-flop maximum
likelihood of Dutilleul (1999) on complete spines, shrunk toward the identity by a fixed share,
and stored as two correlation matrices. The margins (each cell's mean and SD) stay the table's:
this block replaces only the correlation the table cannot give, so a draw keeps every cell's
mean and SD as before.

Persons who share a population are fitted together and nothing else is: one prior per stratum
(ENHANCE.PET, VerSe, TotalSegmentator), as the populations rule of 2026-10-29 says. A level a
prior was not fitted on (L6, T13) borrows its neighbour's row, L5's for L6 and T12's for T13,
and correlates with that neighbour as the neighbour does with its own (L4 with L5, T11 with T12).

Usage, on rows the morphometry engine wrote (study, level, key, value, note):

    python -m schwingcheck.correlation fit --rows rows.csv --levels T1..L5 --keys k1,k2 \
        [--studies train.txt] [--keymap map.csv] [--shrink 0.05] --out prior.json
    python -m schwingcheck.correlation compare --rows rows.csv --prior prior.json \
        --train train.txt --test test.txt [--rho 0.5] [--r-between 0]

compare scores held-out spines by mean log likelihood per spine under the fitted structure and
under the generator's assumed one, both on the training spines' cell means and SDs, so the two
differ only in their correlation.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS_C2

ALL_LEVELS = LEVELS_C2 + ["L6", "T13"]
BORROW = {"L6": ("L5", "L4"), "T13": ("T12", "T11")}   # level -> (whose row, whose neighbour)
FLIP_FLOP_STEPS = 100
FLIP_FLOP_TOL = 1e-9


@dataclass
class Prior:
    levels: List[str]
    measures: List[str]
    r_level: np.ndarray
    r_measure: np.ndarray
    n: int = 0
    shrink: float = 0.0
    note: str = ""

    def to_json(self) -> dict:
        return dict(levels=self.levels, measures=self.measures, r_level=self.r_level.tolist(),
                    r_measure=self.r_measure.tolist(), n=self.n, shrink=self.shrink, note=self.note)

    @classmethod
    def from_json(cls, d: dict) -> "Prior":
        return cls(levels=list(d["levels"]), measures=list(d["measures"]), r_level=np.array(d["r_level"], float),
                   r_measure=np.array(d["r_measure"], float), n=int(d.get("n", 0)),
                   shrink=float(d.get("shrink", 0.0)), note=str(d.get("note", "")))


def to_correlation(cov: np.ndarray) -> np.ndarray:
    d = np.sqrt(np.diag(cov))
    r = cov / np.outer(d, d)
    np.fill_diagonal(r, 1.0)
    return (r + r.T) / 2


def standardise(values: np.ndarray, mean: Optional[np.ndarray] = None,
                sd: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """values (spines, levels, measures) to z scores by each cell's mean and SD, the training
    spines' own where none are given."""
    if mean is None:
        mean = np.nanmean(values, axis=0)
    if sd is None:
        sd = np.nanstd(values, axis=0, ddof=1)
    if np.any(~np.isfinite(sd)) or np.any(sd <= 0):
        raise ValueError("every cell needs a positive SD; a cell with one value or none has none")
    return (values - mean) / sd, mean, sd


def complete(values: np.ndarray) -> np.ndarray:
    keep = np.isfinite(values).all(axis=(1, 2))
    return values[keep]


def flip_flop(z: np.ndarray, steps: int = FLIP_FLOP_STEPS, tol: float = FLIP_FLOP_TOL) -> Tuple[np.ndarray, np.ndarray]:
    """The maximum likelihood row and column covariances of a zero-mean matrix normal sample
    z (n, L, M), Dutilleul's alternation; returned as correlations, which is all the product
    identifies once the margins are fixed."""
    n, L, M = z.shape
    if n * M <= L or n * L <= M:
        raise ValueError("%d complete spines are too few for %d levels and %d measures" % (n, L, M))
    sl, sm = np.eye(L), np.eye(M)
    for _ in range(steps):
        im = np.linalg.inv(sm)
        sl_new = np.einsum("nlm,mk,njk->lj", z, im, z) / (n * M)
        il = np.linalg.inv(sl_new)
        sm_new = np.einsum("nlm,lk,nkj->mj", z, il, z) / (n * L)
        done = np.abs(sl_new - sl).max() < tol and np.abs(sm_new - sm).max() < tol
        sl, sm = sl_new, sm_new
        if done:
            break
    return to_correlation(sl), to_correlation(sm)


def shrunk(r: np.ndarray, share: float) -> np.ndarray:
    return (1 - share) * r + share * np.eye(len(r))


def fit(values: np.ndarray, levels: Sequence[str], measures: Sequence[str], shrink: float = 0.05,
        note: str = "") -> Prior:
    """The prior from whole spines, values (spines, levels, measures) with NaN where missing;
    only spines with every cell are used."""
    whole = complete(values)
    z, _, _ = standardise(whole)
    rl, rm = flip_flop(z)
    return Prior(list(levels), list(measures), shrunk(rl, shrink), shrunk(rm, shrink), n=len(whole),
                 shrink=shrink, note=note)


def assumed_cov(L: int, M: int, rho: float = 0.5, r_between: float = 0.0) -> np.ndarray:
    """The generator's own correlation of one spine's standardised values, levels-major as
    vec(X): rho * z[m] + sqrt(1 - rho^2) * e[m, l] gives rho^2 * C_z[m, m'] between any two
    cells and 1 on the diagonal, C_z the exchangeable correlation at r_between."""
    cz = np.full((M, M), r_between)
    np.fill_diagonal(cz, 1.0)
    cov = rho * rho * np.kron(np.ones((L, L)), cz)
    cov += (1 - rho * rho) * np.eye(L * M)
    return cov


def prior_cov(p: Prior) -> np.ndarray:
    return np.kron(p.r_level, p.r_measure)


def mvn_loglik(z: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Log density of each spine's vec(z) under N(0, cov); z (n, L, M)."""
    n = len(z)
    x = z.reshape(n, -1)
    chol = np.linalg.cholesky(cov)
    sol = np.linalg.solve(chol, x.T)
    logdet = 2 * np.log(np.diag(chol)).sum()
    return -0.5 * (x.shape[1] * math.log(2 * math.pi) + logdet + (sol * sol).sum(axis=0))


def compare(train: np.ndarray, test: np.ndarray, p: Prior, rho: float = 0.5, r_between: float = 0.0) -> dict:
    """Mean held-out log likelihood per whole spine, in nats, fitted against assumed, both on
    the training spines' cell means and SDs, so only the correlation differs."""
    whole_train, whole_test = complete(train), complete(test)
    _, mean, sd = standardise(whole_train)
    zt, _, _ = standardise(whole_test, mean, sd)
    L, M = zt.shape[1:]
    fitted = mvn_loglik(zt, prior_cov(p))
    assumed = mvn_loglik(zt, assumed_cov(L, M, rho, r_between))
    diff = fitted - assumed
    se = float(diff.std(ddof=1) / math.sqrt(len(diff))) if len(diff) > 1 else float("nan")
    return dict(n_test=int(len(zt)), cells=int(L * M), fitted=float(fitted.mean()), assumed=float(assumed.mean()),
                gain_per_spine=float(diff.mean()), gain_se=se, gain_per_cell=float(diff.mean() / (L * M)),
                share_better=float((diff > 0).mean()))


def nearest_pd(r: np.ndarray, floor: float = 1e-6) -> np.ndarray:
    w, v = np.linalg.eigh(r)
    if w.min() >= floor:
        return r
    fixed = (v * np.maximum(w, floor)) @ v.T
    return to_correlation(fixed)


def level_block(p: Prior, names: Sequence[str]) -> np.ndarray:
    """The correlation between the named levels of one column, borrowing for L6 and T13."""
    index = {l: i for i, l in enumerate(p.levels)}

    def source(l: str) -> str:
        if l in index:
            return l
        if l in BORROW and BORROW[l][0] in index:
            return BORROW[l][0]
        raise ValueError("the prior has no level %s and nothing to borrow it from" % l)

    def adjacent(l: str) -> float:
        own, neighbour = BORROW[l]
        if own in index and neighbour in index:
            return float(p.r_level[index[own], index[neighbour]])
        return 0.0

    src = [index[source(l)] for l in names]
    r = p.r_level[np.ix_(src, src)].copy()
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if i != j and src[i] == src[j]:
                r[i, j] = adjacent(a if a not in index else b)
    np.fill_diagonal(r, 1.0)
    return nearest_pd(r)


def measure_block(p: Prior, measures: Sequence[str]) -> np.ndarray:
    missing = [m for m in measures if m not in p.measures]
    if missing:
        raise ValueError("the prior was not fitted on %s" % ", ".join(missing))
    at = [p.measures.index(m) for m in measures]
    return p.r_measure[np.ix_(at, at)]


def draw_field(rng: np.random.Generator, p: Prior, levels: Sequence[str], measures: Sequence[str]) -> np.ndarray:
    """One column's standardised deviations, (measures, levels), from the matrix normal."""
    al = np.linalg.cholesky(level_block(p, levels))
    am = np.linalg.cholesky(measure_block(p, measures))
    e = rng.normal(size=(len(measures), len(levels)))
    return am @ e @ al.T


# reading the morphometry engine's rows

def expand_levels(spec: str) -> List[str]:
    """'T1..L5' or 'C3,C4,L1' to level names in ALL_LEVELS' order."""
    if ".." in spec:
        a, b = spec.split("..")
        i, j = LEVELS_C2.index(a), LEVELS_C2.index(b)
        return LEVELS_C2[i:j + 1]
    return [s for s in spec.split(",") if s]


def read_rows(path: str, levels: Sequence[str], keys: Sequence[str], studies: Optional[Iterable[str]] = None,
              keymap: Optional[Dict[str, str]] = None) -> Tuple[np.ndarray, List[str]]:
    """The engine's long rows to (studies, levels, keys), NaN where a value is missing or not
    finite; keymap renames the engine's keys first."""
    wanted = None if studies is None else set(studies)
    li = {l: i for i, l in enumerate(levels)}
    ki = {k: i for i, k in enumerate(keys)}
    cells: Dict[str, np.ndarray] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            study = row["study"]
            if wanted is not None and study not in wanted:
                continue
            key = (keymap or {}).get(row["key"], row["key"])
            if row["level"] not in li or key not in ki:
                continue
            try:
                v = float(row["value"])
            except ValueError:
                continue
            if not math.isfinite(v):
                continue
            if study not in cells:
                cells[study] = np.full((len(levels), len(keys)), np.nan)
            cells[study][li[row["level"]], ki[key]] = v
    order = sorted(cells)
    if not order:
        return np.empty((0, len(levels), len(keys))), []
    return np.stack([cells[s] for s in order]), order


def read_list(path: Optional[str]) -> Optional[List[str]]:
    if path is None:
        return None
    with open(path) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def read_keymap(path: Optional[str]) -> Optional[Dict[str, str]]:
    if path is None:
        return None
    with open(path, newline="") as f:
        return {r["engine"]: r["table"] for r in csv.DictReader(f)}


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.correlation")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fit")
    f.add_argument("--rows", required=True)
    f.add_argument("--levels", required=True)
    f.add_argument("--keys", required=True)
    f.add_argument("--studies")
    f.add_argument("--keymap")
    f.add_argument("--shrink", type=float, default=0.05)
    f.add_argument("--note", default="")
    f.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("--rows", required=True)
    c.add_argument("--prior", required=True)
    c.add_argument("--train", required=True)
    c.add_argument("--test", required=True)
    c.add_argument("--keymap")
    c.add_argument("--rho", type=float, default=0.5)
    c.add_argument("--r-between", type=float, default=0.0)
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        levels, keys = expand_levels(a.levels), [k for k in a.keys.split(",") if k]
        values, _ = read_rows(a.rows, levels, keys, read_list(a.studies), read_keymap(a.keymap))
        p = fit(values, levels, keys, a.shrink, a.note)
        with open(a.out, "w") as out:
            json.dump(p.to_json(), out, indent=1)
            out.write("\n")
        print("fitted on %d whole spines of %d read" % (p.n, len(values)))
        return 0
    with open(a.prior) as fp:
        p = Prior.from_json(json.load(fp))
    km = read_keymap(a.keymap)
    train, _ = read_rows(a.rows, p.levels, p.measures, read_list(a.train), km)
    test, _ = read_rows(a.rows, p.levels, p.measures, read_list(a.test), km)
    json.dump(compare(train, test, p, a.rho, a.r_between), sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
