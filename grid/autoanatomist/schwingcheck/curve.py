"""Step e's build-up study: how often the rule names a field right, and how long it takes, as the
measures are added one at a time, from one measure to all 32 of the pool (TODO.md, item P, step e).

    python -m schwingcheck curve run --outdir records/curve-2026-10-28     # the record, curve.nc
    python -m schwingcheck curve table --record records/curve-2026-10-28/curve.nc
    python -m schwingcheck curve figures --record records/curve-2026-10-28/curve.nc --outdir records/curve-2026-10-28/figures
    python -m schwingcheck curve check --record records/curve-2026-10-28/curve.nc

The owner's words of 27 October 2026, 21:27 UTC: "ok now contineu the work but do measure the speed
and accuracy as the number of features per sample increase all the way to all the possible
measurements". The measures are the 32 of measures.pool(), each with its own error and power of
the size, and the rule integrates the size on the trapezoid (rule.trapezoid) throughout.

The columns. The scoring columns are the archive's: 2,000 typical columns from seed 97, the seven
drawn exactly as the record of 2026-10-26 drew them, and the other 25 measures of the pool drawn
for the same patients from seed 197, given their sizes (columns.draw_columns, `scale`), so that the
seven's values stay the record's and rung 0 can be held to it. The selection columns, which choose
the order and are never scored, are 100 typical columns drawn the same way from seeds 311 and 312.
Each of the five anomalous phenotypes has 150 columns from seed 99, the seed of the archive's
supplement, which drew six_lumbar, four_lumbar and t13 (archive/bordercall/exact_supplement.py,
ANOMALOUS); lumbar_rib and no_rib_t12 are new here, and every phenotype takes the other measures
from seed 314. A field there is judged by its column's own names, as the supplement judged its
three, so a T13 or an L6 is never named right. Those names are not one convention: on a t13
column they are the rib reading, which calls the thirteenth rib-bearing body T13 where the
count from C2 calls it L1, and on a lumbar_rib or no_rib_t12 column the count from C2, under
which the rib-bearing L1 stays L1 and the ribless T12 stays T12 where the rib reading calls
them T13 and L1 (archive/bordercall/neighbour.py, rib_ordinals); on six_lumbar and four_lumbar
columns the two agree.

The order. Forward selection from no measure on the selection columns: at each step the measure
whose addition gives the smallest log loss of the true place, the mean over fields summed over 1,
3 and 9 bodies, joins the ones before it, an earlier measure of the pool's order winning a tie.
Every prefix of the order is then scored on the scoring columns, so the curve reports no number
from the columns that chose it.

What is scored besides the prefixes: the seven, rung 0; the seven with each family of measures
added alone, and the families added one after another (the pedicles, the processes, the facets,
the interfacet distances, then the rest of the body and the canal, which takes the ladder to all
32); the lengths, the seven with the areas and the seven with the angles; and what an AP view
reads, what a lateral view reads, both, and everything (measures.py's planes).

The arms, each scored on its own columns:

- nominal: the scoring columns and the five anomalous phenotypes, the rule built on the table as
  printed, at 1, 3, 5 and 9 bodies, the typical columns at 5 too, so that every anomalous rate at
  5 bodies has a typical one beside it;
- errors-0.5 and errors-2: every measure's error halved or doubled in the columns and in the rule
  alike, since the errors are a stated assumption and the gain from a measure depends on them;
- correlated: a patient's offsets correlated at 0.4 between measures, every other setting as
  assumed (the archive's misspecified world r_between = 0.4, exact.MISSPEC; its combined world,
  exact.COMBINED, also draws 1.5 mm of error and builds the rule on twelve-specimen tables), all
  32 drawn in one stream from seed 331; the rule, which multiplies its measures as independent,
  does not know it, so this arm shows how the independence rule fares on correlated columns and
  whether its answers at 0.99 stay right. It does not measure what treating the measures as
  independent costs, which needs a rule that knows r, scored against this rule on the same
  columns, and that rule is not built here (exact.py's r_known worlds built one for the seven,
  on columns of their own);
- people-P-nominal and people-P-predictive, the data axis: the table re-estimated from P people
  drawn from the generator with no size spread, no measurement error and no floor (P = 12, 50,
  200 and 2,000; 8, 4, 2 and 2 tables from seed 317, at least two at every P, so that every row
  of the axis carries the variation between tables), as exact.py's specimen worlds draw twelve,
  though those keep the floor: a specimen carries no error, and one held at the floor would only
  bend the estimate away from the printed table, to which without it the estimate tends as P
  grows. The rule is built on the estimate as if it were exact (nominal) or with each SD widened
  to the spread of a new person about a P-person mean and SD, a Student t on P - 1 degrees of
  freedom whose variance is (1 + 1/P)(P - 1)/(P - 3) times the SD squared (predictive, exact.py's
  rule for twelve); each is scored on the first 200 scoring columns, the tables' fields pooled,
  beside the table as printed scored on the same 200 columns (people-printed), against which
  every table of the axis is read.

The rates of every arm, phenotype, subset and width are the share named exactly, the share within
one level, the share named at a posterior of 0.99 and the precision there, the log loss of the
true place and the error the posterior itself predicts (typical columns only, since an anomalous
body may have no place), and the mean size of the 99 per cent set, each share and the precision
with its standard error clustered by column. Within one level is read on a half-step scale on
which a T13 sits half-way between T12 and L1 and an L6 one below L5, so on a T13 column a T12
called L1, or an L1 called T12, counts as within one level though the two are two bodies apart.
Beside the precision are the count answered, and, where no answered field is wrong, which gives a
clustered standard error of 0 however few were answered, the precision's exact two-sided 95 per
cent lower bound (Clopper-Pearson, 0.025 to the power 1 over the count; on the data axis, whose
count answered counts a field once for every table that answered it, over the count of the table
that answered fewest). On the data axis, whose tables share the columns, the clustered SEs hold
the tables drawn fixed, and *_se_tables, beside every share and the precision, counts the
variation between tables too (pooled_rates), on one degree of freedom fewer than the tables: 7,
3, 1 and 1 at P = 12, 50, 200 and 2,000.

The time to name one field, single-threaded, is measured at every prefix of the order and at 1, 3
and 9 bodies on the first 20 scoring columns, with the rule built beforehand as a service would
build it once, rule.py's table blocks and the compiled rule's alike (compiled.ExactRule.prepare):
the median and the largest over 30 single fields, and per field in a batch of 128, the median and
the largest of five such calls after one that warms them, for rule.py on the trapezoid's nodes and
on the Gauss-Hermite ones and for the compiled rule (compiled.py) on the trapezoid's. The compiled
rule's functions are compiled before the thread limit is set, since compiling loads scipy's own
BLAS, which Numba's BLAS calls use, and threadpool_limits holds only the libraries loaded when it
is entered; every pool's threads are recorded inside the limit. NUTS on the naming model (model.py)
runs at 7, 16 and 32 measures of the order, on one field at each place, sampled together in one
model and the middle one of them alone, with the seconds a call to build the model and to set the
sampler up (compiling its log density and gradient, which every new set of fields pays again, since
the observed values are constants of the compiled graph, and which a compiled graph already on disk
shortens), the seconds a field of NUTS's own loop and of averaging the posterior (a second call,
the first having compiled it), and each field's distance from the exact posterior, its Monte Carlo
error and R-hat, and the divergences. Beside each run are the files it added to PyTensor's Numba
cache, base_compiledir/numba, which PyTensor's compiledir flag does not move: a run that compiled
some of its graph adds files there, and one whose graph was compiled already, by an earlier run or
an earlier process, adds none and sets up far faster, so the record says which setups hold a
compile; a cold setup is timed with base_compiledir, not compiledir, pointed at an empty folder.

The record is written once the scoring is done, before any time is taken, so that a failure in
the timing loses no scoring, and again with the times, each time through records.write, which
gives the file its name only once it is whole. The digests of the package and of the table and
the git state are taken when the run begins (code_state), so that the record names the code that
ran, and what changed by the time the record is built is recorded beside them
(changed_during_run), since compiled.py and model.py are imported only when the times reach them.
How the times were taken, the counts, the fields' places, the pools' threads, the machine, the
versions and the files in PyTensor's Numba cache when NUTS began, is in the attributes speed and
nuts; `curve speed` takes them again into a record, with its own digests.
"""
from __future__ import annotations

import json
import math
import multiprocessing
import os
import platform
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS
from . import columns as C
from . import measures as MS
from . import rule as R
from . import score as S
from . import table as T

WIDTHS = (1, 3, 9)
NOMINAL_WIDTHS = (1, 3, 5, 9)                        # the nominal arm's, typical and anomalous alike
ANOMALOUS = ("four_lumbar", "six_lumbar", "t13", "lumbar_rib", "no_rib_t12")
SCORE_SEED, EXTRA_SEED, N_SCORE = 97, 197, 2000
SELECT_SEED, SELECT_EXTRA_SEED, N_SELECT = 311, 312, 100
ANOMALOUS_SEED, ANOMALOUS_EXTRA_SEED, N_ANOMALOUS = 99, 314, 150
ERROR_SCALES = (0.5, 2.0)
CORRELATED_SEED, R_BETWEEN = 331, 0.4
WORLD_SEED, N_WORLD_COLUMNS = 317, 200
WORLDS = {12: 8, 50: 4, 200: 2, 2000: 2}            # tables drawn per number of people, two at least
NUTS_MEASURES = (7, 16, 32)
NUTS_WIDTH, NUTS_DRAWS, NUTS_TUNE, NUTS_CHAINS, NUTS_SEED = 3, 500, 500, 2, 7
SPEED_CALLS, SPEED_BATCH, SPEED_BATCHES = 30, 128, 5
SPEED_COLUMNS = 20                                   # the scoring columns the times are taken on
CLAIM = 0.99
PROCESSES = 4
JOB_COLUMNS = 25                                     # columns per job of the pool of processes
FIELD_BLOCK = 128                                    # fields per log likelihood array, to bound memory
FAMILIES = ("pedicles", "processes", "facets", "interfacet", "body")
FAMILY_NAMES = {"pedicles": "the pedicles", "processes": "the processes", "facets": "the facets",
                "interfacet": "the interfacet distances", "body": "the rest of the body and the canal"}
STATS = ("n_fields", "n_columns", "exact", "exact_se", "within_one", "within_one_se", "answered", "answered_se",
         "precision", "precision_se", "n_answered", "errors", "precision_lower", "log_loss", "predicted_error",
         "set_size", "floored", "exact_table_sd", "answered_table_sd", "precision_table_sd",
         "exact_se_tables", "within_one_se_tables", "answered_se_tables", "precision_se_tables")
TABLE_TERMS = ("exact", "within_one", "answered", "precision")    # the rates the data axis gives an SE with the tables
# every count the study takes, at full size and, under --quick, at the tests' size
FULL_COUNTS = {"score": N_SCORE, "select": N_SELECT, "anomalous": N_ANOMALOUS, "world_columns": N_WORLD_COLUMNS,
               "worlds": WORLDS, "speed_calls": SPEED_CALLS, "speed_batch": SPEED_BATCH,
               "speed_batches": SPEED_BATCHES, "speed_measures": None, "nuts_measures": NUTS_MEASURES}
QUICK_COUNTS = {"score": 20, "select": 8, "anomalous": 6, "world_columns": 10, "worlds": {12: 2, 2000: 2},
                "speed_calls": 3, "speed_batch": 8, "speed_batches": 2, "speed_measures": (1, 7, 32),
                "nuts_measures": (7,)}
VERSIONED = ("numpy", "scipy", "pytensor", "pymc", "numba", "arviz", "xarray", "threadpoolctl", "h5netcdf")
# the half-step scale on which "within one level" is read: C3 0 ... T12 16, T13 16.5, L1 17 ... L5 21,
# L6 22; so on a T13 column a T12 called L1, or an L1 called T12, counts as within one level, though
# the two are two bodies apart there
POSITION = dict({lv: float(i) for i, lv in enumerate(LEVELS)}, T13=LEVELS.index("T12") + 0.5, L6=float(len(LEVELS)))
PLACE_POSITION = np.array([POSITION[lv] for lv in LEVELS])


def study_counts(quick: bool) -> dict:
    """Every count of the study: the full study's, or with quick each one shrunk for the tests."""
    return dict(QUICK_COUNTS if quick else FULL_COUNTS)


# ---- the measures and their subsets ---------------------------------------------------------

def family_of(m: MS.Measure) -> str:
    """The part of the vertebra a measure of the pool describes."""
    if m.name.startswith("pedicle"):
        return "pedicles"
    if m.name.startswith(("spinous", "transverse")):
        return "processes"
    if m.name.startswith("interfacet"):
        return "interfacet"
    if m.name.startswith("facet"):
        return "facets"
    return "body"


def subsets(pool: Sequence[MS.Measure], order: Sequence[int]) -> Dict[str, List[int]]:
    """Every subset the study scores, by name, as indices into the pool: the prefixes of the order
    (prefix-01 to prefix-32), then the named ones."""
    keys = [m.key for m in pool]
    seven = [keys.index(k) for k in MS.SPINEPS_7]
    fam = {f: [i for i, m in enumerate(pool) if family_of(m) == f and i not in seven] for f in FAMILIES}
    kind = {k: [i for i, m in enumerate(pool) if m.kind == k] for k in ("length", "area", "angle")}
    plane = {p: [i for i, m in enumerate(pool) if p in m.planes] for p in ("ap", "lateral")}
    out = {"prefix-%02d" % k: list(order[:k]) for k in range(1, len(order) + 1)}
    out["seven"] = seven
    for f in FAMILIES:
        out["seven+" + f] = sorted(seven + fam[f])
    ladder = list(seven)
    for f in FAMILIES:
        ladder = sorted(ladder + fam[f])
        out["ladder-" + f] = list(ladder)
    out["lengths"] = kind["length"]
    out["seven+areas"] = sorted(set(seven) | set(kind["area"]))
    out["seven+angles"] = sorted(set(seven) | set(kind["angle"]))
    out["ap"] = plane["ap"]
    out["lateral"] = plane["lateral"]
    out["ap+lateral"] = sorted(set(plane["ap"]) | set(plane["lateral"]))
    out["all"] = list(range(len(pool)))
    return out


def prefixes_and_seven(names: Sequence[str]) -> List[str]:
    """The subsets the robustness arms score: the prefixes of the order and the seven."""
    return [n for n in names if n.startswith("prefix-") or n == "seven"]


# ---- the columns ----------------------------------------------------------------------------

def _keys(measures: Sequence[MS.Measure]) -> List[str]:
    return [MS.archive_key(m) for m in measures]


def draw_pool(pool: Sequence[MS.Measure], phenotype: str, seed: int, extra_seed: int, n: int,
              error_scale: float = 1.0, scale: Optional[np.ndarray] = None) -> C.Columns:
    """n columns of one phenotype with every measure of the pool, in the pool's order: the seven
    from `seed` exactly as the archive draws them, the rest from `extra_seed` for the same patients;
    the meta's powers and errors are the pool's, in its order, so that columns.floor_hits reads them.
    `scale`, one size a column, gives the patients' sizes in place of drawing them
    (columns.draw_columns); the stream then draws no sizes, so the seven come from the same law but
    are no longer the archive's draws from `seed`."""
    seven = MS.select(MS.SPINEPS_7)
    rest = [m for m in pool if m.key not in MS.SPINEPS_7]
    first = C.draw_columns(MS.reference(seven), [phenotype], seed, n, _keys(seven),
                           noise_mm=MS.errors(seven) * error_scale, power=MS.powers(seven), scale=scale)
    more = C.draw_columns(MS.reference(rest), [phenotype], extra_seed, n, _keys(rest),
                          noise_mm=MS.errors(rest) * error_scale, power=MS.powers(rest), scale=first.scale)
    if first.levels != more.levels:
        raise AssertionError("the two draws laid the columns out differently")
    drawn = [m.key for m in seven] + [m.key for m in rest]
    where = [drawn.index(m.key) for m in pool]
    values = np.concatenate([first.values, more.values], axis=2)[:, :, where]
    meta = dict(first.meta, extra_seed=extra_seed, error_scale=error_scale, power=MS.powers(pool).tolist(),
                noise_mm=(MS.errors(pool) * error_scale).tolist())
    return C.Columns(values=values, levels=first.levels, measures=[m.key for m in pool], phenotype=first.phenotype,
                     scale=first.scale, transitional_at=first.transitional_at, blend=first.blend, seed=seed, meta=meta)


def draw_correlated(pool: Sequence[MS.Measure], seed: int, n: int, r_between: float) -> C.Columns:
    """n typical columns with every measure of the pool drawn in one stream, a patient's offsets
    correlated at r_between between measures."""
    return C.draw_columns(MS.reference(pool), ["typical"], seed, n, _keys(pool), r_between=r_between,
                          noise_mm=MS.errors(pool), power=MS.powers(pool))


def estimated_table(pool: Sequence[MS.Measure], people: int, rng) -> Tuple[np.ndarray, np.ndarray]:
    """The table (measures, levels) re-estimated from `people` typical columns drawn from the
    generator with no size spread, no measurement error and no floor, as exact.redrawn_table's
    specimens but for the floor, which they keep: each level's mean and SD over the people. The
    specimens carry no error, so a value held at the floor would only bend the estimate away from
    the printed table; without it the estimate tends to the printed table as the people grow."""
    spec = C.draw_columns(MS.reference(pool), ["typical"], int(rng.integers(1 << 30)), people, _keys(pool),
                          noise_mm=0.0, scale_sd=0.0, power=MS.powers(pool), floor=False)
    vals = spec.values[:, :len(LEVELS), :]
    return vals.mean(0).T.copy(), vals.std(0, ddof=1).T.copy()


def predictive_factor(people: int) -> float:
    """The SD of a new person about a table of `people`: sqrt((1 + 1/P)(P - 1)/(P - 3))."""
    return math.sqrt((1.0 + 1.0 / people) * (people - 1.0) / (people - 3.0))


# ---- one arm's work -------------------------------------------------------------------------

@dataclass
class Arm:
    """What one arm scores: its columns, the table and errors its rule is built on, its widths and
    subsets; `world` tells the tables of the data axis apart, whose fields are pooled."""
    name: str
    phenotype: str
    values: np.ndarray
    levels: List[List[str]]
    mu: np.ndarray
    sd: np.ndarray
    noise: np.ndarray
    power: np.ndarray
    widths: Tuple[int, ...]
    subsets: List[str]
    world: int = 0
    settings: dict = field(default_factory=dict)


def true_positions(start: np.ndarray, col: np.ndarray, levels: Sequence[Sequence[str]], n: int) -> np.ndarray:
    """Where the middle body of each field sits on the half-step scale of POSITION, by its own
    column's name for it (the module's docstring says which convention that is)."""
    t = S.target_offset(n)
    return np.array([POSITION[levels[c][s + t]] for s, c in zip(start, col)])


def field_stats(post: np.ndarray, start: np.ndarray, truth_at: np.ndarray, n: int, typical: bool) -> Dict[str, np.ndarray]:
    """What one posterior over places did on each field: right or not by the name of the middle
    body (truth_at, true_positions), within one level on POSITION's half-step scale (so on a T13
    column a T12 called L1, or an L1 called T12, is within one level, though two bodies apart),
    its top posterior, the log posterior of the true place (typical columns, where the place is
    the field's start) and the size of its 99 per cent set."""
    call = post.argmax(1)
    said_at = PLACE_POSITION[call + S.target_offset(n)]
    logp = np.log(np.maximum(post[np.arange(len(start)), start], 1e-300)) if typical else np.full(len(start), np.nan)
    size, _ = R.credible_sets(post, CLAIM)
    return {"hit": said_at == truth_at, "within": np.abs(said_at - truth_at) <= 1.0, "top": post.max(1),
            "logp": logp, "size": size.astype(np.int16)}


def floored_in(X: np.ndarray, idx: Sequence[int], power: np.ndarray) -> np.ndarray:
    """Whether each field holds a value at the generator's floor among the measures idx that scale
    with the size, where the rule, which has no floor, is not the generator's posterior."""
    scaled = np.asarray(power, float)[list(idx)] > 0
    return ((X[:, list(idx), :] == C.FLOOR) & scaled[None, :, None]).any((1, 2))


def score_fields(X: np.ndarray, offsets: np.ndarray, arm: Arm, names: Sequence[str], index: Dict[str, List[int]],
                 nodes) -> Dict[str, np.ndarray]:
    """The posterior over places of each field under every subset named, as one log likelihood
    per measure: the prefixes of the order read off its running sum, the rest summed afresh."""
    sizes, logw = nodes
    LL = R.loglik(X, offsets, arm.mu, arm.sd, R.SYNTH, sizes=sizes, noise=arm.noise, power=arm.power)
    order = index["prefix-%02d" % LL.shape[2]]                 # the whole order, the longest prefix
    running = np.cumsum(LL[:, :, order, :], axis=2)
    out = {}
    for name in names:
        idx = index[name]
        total = running[:, :, len(idx) - 1, :] if name.startswith("prefix-") else LL[:, :, idx, :].sum(2)
        out[name] = R.posterior(R.logsumexp(total + logw, 2))
    return out


_ARMS: List[Arm] = []
_INDEX: Dict[str, List[int]] = {}


def run_job(job: Tuple[int, int, int, int]) -> Tuple[int, int, int, dict]:
    """One job of the pool: the fields of columns c0 to c1 of one arm at one width."""
    from threadpoolctl import threadpool_limits
    a, n, c0, c1 = job
    arm = _ARMS[a]
    offsets = np.arange(n)
    nodes = R.trapezoid(R.SYNTH["scale_sd"])
    X, start, col = C.fields(arm.values[c0:c1], offsets)
    col = col + c0
    truth_at = true_positions(start, col, arm.levels, n)
    parts: Dict[str, List[dict]] = {name: [] for name in arm.subsets}
    with threadpool_limits(1):
        for f0 in range(0, len(X), FIELD_BLOCK):
            f1 = min(len(X), f0 + FIELD_BLOCK)
            posts = score_fields(X[f0:f1], offsets, arm, arm.subsets, _INDEX, nodes)
            for name, post in posts.items():
                st = field_stats(post, start[f0:f1], truth_at[f0:f1], n, arm.phenotype == "typical")
                st["floored"] = floored_in(X[f0:f1], _INDEX[name], arm.power)
                parts[name].append(st)
    stats = {name: {k: np.concatenate([p[k] for p in ps]) for k in ps[0]} for name, ps in parts.items() if ps}
    return a, n, c0, {"col": col, "world": arm.world, "stats": stats}


def precision_lower(answered: int, errors: int) -> float:
    """The exact two-sided 95 per cent lower bound of a precision with no error among `answered`
    fields (Clopper-Pearson: n right of n gives 0.025 ** (1 / n)); NaN where none was answered or
    any answered field is wrong, whose precision carries its clustered SE instead, 0 there too where
    every column that answered has the same share wrong. It counts the answered fields as
    independent trials; the fields of one column share its draws, so a bound that counted the
    columns instead could be lower. On the data axis, whose tables answer the same fields,
    pooled_rates gives it the count of the table that answered fewest, since a field answered by
    every table is not as many independent trials."""
    if errors or answered < 1:
        return float("nan")
    return 0.025 ** (1.0 / answered)


def rates(stats: Dict[str, np.ndarray], group: np.ndarray) -> dict:
    """The rates of one arm, phenotype, subset and width from its fields' stats: each share with
    its SE clustered by column, the precision at 0.99 with the ratio estimator's SE, the count
    answered and the errors, and the precision's lower bound where no answered field is wrong
    (precision_lower), since the ratio SE is then 0 however few were answered."""
    hit, within, top = stats["hit"].astype(float), stats["within"].astype(float), stats["top"]
    said = top >= CLAIM
    inv = np.unique(group, return_inverse=True)[1]
    wrong = np.bincount(inv, weights=said & (hit == 0))
    answered = np.bincount(inv, weights=said)
    n_answered, errors = int(said.sum()), int(round(float(wrong.sum())))
    out = {"n_fields": int(len(hit)), "n_columns": int(inv.max() + 1) if len(inv) else 0,
           "exact": float(hit.mean()), "exact_se": S.clustered_se(hit, group),
           "within_one": float(within.mean()), "within_one_se": S.clustered_se(within, group),
           "answered": float(said.mean()), "answered_se": S.clustered_se(said.astype(float), group),
           "precision": float(hit[said].mean()) if said.any() else float("nan"),
           "precision_se": S.ratio_se(wrong, answered), "n_answered": n_answered, "errors": errors,
           "precision_lower": precision_lower(n_answered, errors),
           "log_loss": float(-np.mean(stats["logp"])) if np.all(np.isfinite(stats["logp"])) else float("nan"),
           "predicted_error": float((1.0 - top).mean()) if np.all(np.isfinite(stats["logp"])) else float("nan"),
           "set_size": float(stats["size"].mean()), "floored": float(stats["floored"].mean())}
    return out


def crossed_se(v: np.ndarray, col: np.ndarray, world: np.ndarray) -> float:
    """The standard error of the mean of v over fields that come from every table on the same
    columns, columns and tables both drawn at random and crossed: sqrt((MS_columns +
    max(MS_tables - MS_interaction, 0)) / (C T)) from each (column, table) cell's mean, the two-way
    random-effects estimate, which counts the interaction once, as sqrt(se^2 + sd^2 / T) would
    not. NaN with fewer than two columns or tables, or where the cells are not all one size, as
    the two-way estimate needs and every table of the data axis gives, scoring the same fields."""
    cols, ci = np.unique(col, return_inverse=True)
    tabs, ti = np.unique(world, return_inverse=True)
    a, b = len(cols), len(tabs)
    if a < 2 or b < 2:
        return float("nan")
    m, k = np.zeros((a, b)), np.zeros((a, b))
    np.add.at(m, (ci, ti), np.asarray(v, float))
    np.add.at(k, (ci, ti), 1.0)
    if k.min() < 1 or k.max() != k.min():
        return float("nan")
    m /= k
    g, r, c = m.mean(), m.mean(1), m.mean(0)
    ms_c = b * ((r - g) ** 2).sum() / (a - 1)
    ms_t = a * ((c - g) ** 2).sum() / (b - 1)
    ms_e = ((m - r[:, None] - c[None, :] + g) ** 2).sum() / ((a - 1) * (b - 1))
    return float(math.sqrt((ms_c + max(ms_t - ms_e, 0.0)) / (a * b)))


def tables_se(stats: Dict[str, np.ndarray], col: np.ndarray, world: np.ndarray) -> dict:
    """The data axis's SEs that count the tables: each share's by crossed_se, and the precision's
    from its linearised residual, wrong - R said per field with R the pooled error rate, times N / A
    (N fields, A answered), as score.ratio_se linearises it by column."""
    hit = stats["hit"].astype(float)
    said = (stats["top"] >= CLAIM).astype(float)
    wrong = said * (1.0 - hit)
    n, answered = len(hit), said.sum()
    out = {"exact_se_tables": crossed_se(hit, col, world),
           "within_one_se_tables": crossed_se(stats["within"].astype(float), col, world),
           "answered_se_tables": crossed_se(said, col, world), "precision_se_tables": float("nan")}
    if answered > 0:
        resid = wrong - wrong.sum() / answered * said
        out["precision_se_tables"] = crossed_se(resid, col, world) * n / answered
    return out


# ---- the order ------------------------------------------------------------------------------

def log_loss(total: np.ndarray, truth: np.ndarray, logw: np.ndarray) -> float:
    """The mean over fields of minus the log posterior of the true place, from the summed log
    likelihood (fields, places, nodes)."""
    logev = R.logsumexp(total + logw, 2)
    return float(-(logev[np.arange(len(truth)), truth] - R.logsumexp(logev, 1)).mean())


def selection_loglik(pool: Sequence[MS.Measure], cols: C.Columns, n: int, nodes) -> Tuple[np.ndarray, np.ndarray]:
    """Every measure's log likelihood on the selection fields of one width, (fields, places,
    measures, nodes), kept in single precision, which ranks the measures as well as double does
    in a quarter of the memory of the three widths in double."""
    mu, sd = MS.arrays(pool)
    offsets = np.arange(n)
    X, truth, _ = C.fields(cols.values, offsets)
    parts = [R.loglik(X[f:f + FIELD_BLOCK], offsets, mu, sd, R.SYNTH, sizes=nodes[0], noise=MS.errors(pool),
                      power=MS.powers(pool)).astype(np.float32) for f in range(0, len(X), FIELD_BLOCK)]
    return np.concatenate(parts), truth


def greedy_order(pool: Sequence[MS.Measure], cols: C.Columns, widths: Sequence[int] = WIDTHS,
                 log=print) -> Tuple[List[int], List[dict]]:
    """Forward selection from no measure: at each step the measure whose addition gives the
    smallest log loss of the true place, summed over the widths, joins the order."""
    from threadpoolctl import threadpool_limits
    nodes = R.trapezoid(R.SYNTH["scale_sd"])
    with threadpool_limits(1):
        parts = [selection_loglik(pool, cols, n, nodes) for n in widths]
    running = [np.zeros((LL.shape[0], LL.shape[1], LL.shape[3])) for LL, _ in parts]
    order: List[int] = []
    trace: List[dict] = []
    for step in range(len(pool)):
        best = None
        for m in range(len(pool)):
            if m in order:
                continue
            losses = [log_loss(run + LL[:, :, m, :], truth, nodes[1]) for (LL, truth), run in zip(parts, running)]
            if best is None or sum(losses) < best[0]:
                best = (sum(losses), m, losses)
        order.append(best[1])
        for (LL, _), run in zip(parts, running):
            run += LL[:, :, best[1], :]
        trace.append({"step": step + 1, "measure": pool[best[1]].key, "loss": best[0],
                      "loss_by_width": {str(n): l for n, l in zip(widths, best[2])}})
        log("order: %2d %-26s log loss %.4f" % (step + 1, pool[best[1]].key, best[0]))
    return order, trace


# ---- the arms -------------------------------------------------------------------------------

def make_arms(pool: Sequence[MS.Measure], names: Sequence[str], quick: bool = False) -> List[Arm]:
    """Every arm of the study, columns drawn, at study_counts(quick)."""
    counts = study_counts(quick)
    mu, sd = MS.arrays(pool)
    noise, power = MS.errors(pool), MS.powers(pool)
    n_world = counts["world_columns"]
    robust = prefixes_and_seven(names)
    arms = []
    score = draw_pool(pool, "typical", SCORE_SEED, EXTRA_SEED, counts["score"])
    arms.append(Arm("nominal", "typical", score.values, score.levels, mu, sd, noise, power, NOMINAL_WIDTHS, list(names)))
    for ph in ANOMALOUS:
        c = draw_pool(pool, ph, ANOMALOUS_SEED, ANOMALOUS_EXTRA_SEED, counts["anomalous"])
        arms.append(Arm("nominal", ph, c.values, c.levels, mu, sd, noise, power, NOMINAL_WIDTHS, list(names)))
    for f in ERROR_SCALES:
        c = draw_pool(pool, "typical", SCORE_SEED, EXTRA_SEED, counts["score"], error_scale=f)
        arms.append(Arm("errors-%g" % f, "typical", c.values, c.levels, mu, sd, noise * f, power, WIDTHS, robust,
                        settings={"error_scale": f}))
    c = draw_correlated(pool, CORRELATED_SEED, counts["score"], R_BETWEEN)
    arms.append(Arm("correlated", "typical", c.values, c.levels, mu, sd, noise, power, WIDTHS, robust,
                    settings={"r_between": R_BETWEEN}))
    # the axis's limit, the table as printed, scored on the axis's own columns, so that every table
    # of the axis is read against it on the same fields: the first columns of the nominal arm are
    # not all of them, and a table read against the nominal arm would carry their difference
    arms.append(Arm("people-printed", "typical", score.values[:n_world], score.levels[:n_world], mu, sd, noise, power,
                    WIDTHS, robust, settings={"people": None, "rule": "printed", "sd_factor": 1.0, "tables": 1}))
    rng = np.random.default_rng(WORLD_SEED)
    for people, n_tables in counts["worlds"].items():
        for w in range(n_tables):
            emu, esd = estimated_table(pool, people, rng)
            for rule, fac in (("nominal", 1.0), ("predictive", predictive_factor(people))):
                arms.append(Arm("people-%d-%s" % (people, rule), "typical", score.values[:n_world], score.levels[:n_world],
                                emu, esd * fac, noise, power, WIDTHS, robust, world=w,
                                settings={"people": people, "rule": rule, "sd_factor": fac, "tables": n_tables}))
    return arms


def floor_counts(arms: Sequence[Arm], keys: Sequence[str]) -> Dict[str, dict]:
    """The values the generator's floor touched in each arm's columns (columns.floor_hits), by arm
    and phenotype. The data axis is not counted: it scores the first of the nominal columns, which
    are counted there, and its tables' specimens are drawn with no floor (estimated_table)."""
    out = {}
    for arm in arms:
        if "people" in arm.settings:
            continue
        n = len(arm.values)
        cols = C.Columns(values=arm.values, levels=arm.levels, measures=list(keys), phenotype=[arm.phenotype] * n,
                         scale=np.full(n, np.nan), transitional_at=[None] * n, meta={"power": list(map(float, arm.power))})
        out["%s/%s" % (arm.name, arm.phenotype)] = C.floor_hits(cols)
    return out


def jobs_of(arms: Sequence[Arm]) -> List[Tuple[int, int, int, int]]:
    """Every (arm, width, first column, last column) of the study, the narrowest fields first,
    since their jobs run longest (a column gives more fields, each with more places, the fewer
    bodies its fields hold), the fuller jobs before the rest at each width."""
    out = []
    for a, arm in enumerate(arms):
        for n in arm.widths:
            for c0 in range(0, len(arm.values), JOB_COLUMNS):
                out.append((a, n, c0, min(len(arm.values), c0 + JOB_COLUMNS)))
    return sorted(out, key=lambda j: (j[1], -(j[3] - j[2])))


def run_arms(arms: List[Arm], index: Dict[str, List[int]], processes: int = PROCESSES, log=print) -> Dict[tuple, dict]:
    """Every job of every arm on a pool of processes, gathered into the rates of every arm,
    phenotype, subset and width, the tables of one arm of the data axis pooled."""
    global _ARMS, _INDEX
    _ARMS, _INDEX = list(arms), dict(index)
    jobs = jobs_of(arms)
    gathered: Dict[tuple, Dict[str, List]] = {}
    t0 = time.time()
    if processes > 1:
        ctx = multiprocessing.get_context("fork")
        with ctx.Pool(processes) as pool:
            results = pool.imap_unordered(run_job, jobs)
            gathered = _gather(results, arms, len(jobs), t0, log)
    else:
        gathered = _gather(map(run_job, jobs), arms, len(jobs), t0, log)
    out = {}
    for (name, phenotype, n), parts in gathered.items():
        for sub in parts["stats"][0]:
            out[(name, phenotype, sub, n)] = pooled_rates(parts, sub)
    return out


def pooled_rates(parts: Dict[str, List], sub: str) -> dict:
    """One subset's rates over every job of an arm, phenotype and width, clustered by column.
    Where the fields come from several tables (the data axis), every table is scored on the same
    columns, so tables and columns are crossed and both drawn at random: the clustered SEs
    (exact_se, within_one_se, answered_se, precision_se) hold the columns' variation only, the
    tables drawn held fixed, and exact_se_tables, within_one_se_tables, answered_se_tables and
    precision_se_tables count the variation between tables too, by the two-way estimate
    (crossed_se), on T - 1 degrees of freedom for T tables: 7, 3, 1 and 1 at P = 12, 50, 200 and
    2,000 (WORLDS); NaN with one table, as for every arm off the axis and the table as printed.
    The spread of the rates between tables (*_table_sd, ddof 1) is given beside them. Where no
    table's answered field is wrong, the precision's lower bound takes the count answered of the
    table that answered fewest, not n_answered, which counts a field once for every table that
    answered it (precision_lower); like the clustered SEs, it holds the tables drawn fixed."""
    def joined(which):
        stats = {k: np.concatenate([p[sub][k] for p, keep in zip(parts["stats"], which) if keep])
                 for k in parts["stats"][0][sub]}
        return stats, np.concatenate([c for c, keep in zip(parts["col"], which) if keep])
    stats, col = joined([True] * len(parts["col"]))
    out = rates(stats, col)
    worlds = sorted(set(parts["world"]))
    for s in ("exact", "answered", "precision"):
        out[s + "_table_sd"] = float("nan")
    for s in TABLE_TERMS:
        out[s + "_se_tables"] = float("nan")
    if len(worlds) > 1:
        each = [rates(*joined([w == world for w in parts["world"]])) for world in worlds]
        for s in ("exact", "answered", "precision"):
            out[s + "_table_sd"] = float(np.std([e[s] for e in each], ddof=1))
        world = np.concatenate([np.full(len(c), w) for c, w in zip(parts["col"], parts["world"])])
        out.update(tables_se(stats, col, world))
        # the tables answer the same fields, so a field answered by several is not as many
        # independent trials; the bound on the fewest a table answered is at most the bound of the
        # table whose precision is lowest, and the pooled precision, the tables' weighted by the
        # fields each answered, is no lower than that table's
        counts = [e["n_answered"] for e in each if e["n_answered"] > 0]
        out["precision_lower"] = precision_lower(min(counts), out["errors"]) if counts else float("nan")
    return out


def _gather(results, arms: Sequence[Arm], n_jobs: int, t0: float, log) -> Dict[tuple, Dict[str, List]]:
    gathered: Dict[tuple, Dict[str, List]] = {}
    for i, (a, n, c0, res) in enumerate(results):
        arm = arms[a]
        g = gathered.setdefault((arm.name, arm.phenotype, n), {"col": [], "world": [], "stats": []})
        g["col"].append(res["col"])
        g["world"].append(res["world"])
        g["stats"].append(res["stats"])
        if (i + 1) % 50 == 0 or i + 1 == n_jobs:
            log("scored %d of %d jobs in %.0f s" % (i + 1, n_jobs, time.time() - t0))
    return gathered


# ---- the time to name a field ---------------------------------------------------------------

def _numpy_namer(mu, sd, noise, power, offsets, nodes):
    """rule.py with its table blocks built once, as a service builds them for a pattern of offsets."""
    sizes, logw = nodes
    blocks = R.table_blocks(offsets, mu, sd, R.SYNTH, sizes, noise, power)

    def name(X):
        LL = R.loglik(X, offsets, mu, sd, R.SYNTH, sizes=sizes, blocks=blocks)
        return R.posterior(R.log_evidence(LL, logw))
    return name


def _compiled_namer(mu, sd, noise, power, offsets, nodes):
    """compiled.py with its table blocks built once (ExactRule.prepare), as _numpy_namer builds
    rule.py's, so that both engines are timed on the fields' side alone."""
    from . import compiled as K
    rule = K.ExactRule(mu, sd, noise=noise, power=power, nodes=nodes)
    hyp = K.hypotheses(rule.n_levels, [offsets])
    prepared = rule.prepare(hyp)

    def name(X):
        return rule.evaluate(X, hyp, prepared=prepared)["all"]["post"]
    return name


ENGINES = {"numpy-trapezoid": (_numpy_namer, "trapezoid"), "numpy-gauss-hermite": (_numpy_namer, "gauss-hermite"),
           "pytensor-trapezoid": (_compiled_namer, "trapezoid")}


def _nodes(kind: str):
    return R.trapezoid(R.SYNTH["scale_sd"]) if kind == "trapezoid" else R.quadrature(R.SYNTH["scale_sd"])


def load_compiled() -> None:
    """Compile the compiled rule's functions now, outside the thread limit: compiling loads scipy's
    own BLAS, which Numba's BLAS calls use, and threadpool_limits holds only the libraries loaded
    when it is entered, so a limit entered first would leave that one at every thread."""
    from . import compiled as K
    K.function(), K.table_function(), K.fields_function()


def pools() -> List[dict]:
    """Every thread pool threadpoolctl sees, its library, API and threads, as they are now."""
    from threadpoolctl import threadpool_info
    return [{"library": os.path.basename(str(d.get("filepath", ""))), "api": str(d.get("internal_api", "")),
             "threads": int(d.get("num_threads", 0))} for d in threadpool_info()]


def numba_cache_files() -> Optional[int]:
    """How many files PyTensor's Numba cache holds now, or None where it cannot be read. The cache
    is base_compiledir/numba, which PyTensor's compiledir flag does not move: a run that compiles a
    graph adds files to it, and a later process running the same graph loads them from disk, with
    a far shorter setup; another process writing to the same cache meanwhile adds files too."""
    try:
        from pytensor.link.numba.cache import NUMBA_CACHE_PATH
        with os.scandir(NUMBA_CACHE_PATH) as entries:
            return sum(1 for e in entries if e.is_file())
    except (ImportError, OSError):
        return None


def machine() -> dict:
    """The machine the times were taken on, and its load then."""
    out = {"platform": platform.platform(), "machine": platform.machine(), "cpu_count": os.cpu_count(),
           "python": platform.python_version()}
    if hasattr(os, "sched_getaffinity"):
        out["cpus_usable"] = len(os.sched_getaffinity(0))
    if hasattr(os, "getloadavg"):
        out["load_average"] = [round(x, 2) for x in os.getloadavg()]
    return out


def versions() -> dict:
    """The versions of Python and of every library the study runs on, read from their metadata."""
    from importlib import metadata
    out = {"python": platform.python_version()}
    for name in VERSIONED:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "not installed"
    return out


def time_engine(namer, X: np.ndarray, calls: int = SPEED_CALLS, batch: int = SPEED_BATCH,
                batches: int = SPEED_BATCHES) -> dict:
    """The time to name one field, called one field at a time (median and largest over `calls`)
    and in a batch (median and largest over `batches` calls of the mean per field), each after one
    call of its own size, which keeps that size's first call out of the times. The warm-up keeps
    almost none of the memory the batch's arrays take, since each large array is given back to the
    system when it is freed: every timed batch call takes that memory afresh, and its time includes
    that page work."""
    namer(X[:1])
    single = []
    for i in range(calls):
        t0 = time.perf_counter()
        namer(X[i % len(X):i % len(X) + 1])
        single.append(time.perf_counter() - t0)
    size = min(batch, len(X))
    namer(X[:batch])                                  # the warm-up at the batch's own size
    per = []
    for _ in range(batches):
        t0 = time.perf_counter()
        namer(X[:batch])
        per.append((time.perf_counter() - t0) / size)
    return {"median_ms": 1e3 * float(np.median(single)), "max_ms": 1e3 * float(np.max(single)),
            "batch_ms": 1e3 * float(np.median(per)), "batch_max_ms": 1e3 * float(np.max(per))}


def timed_fields(start: np.ndarray, col: np.ndarray, calls: int, batch: int) -> dict:
    """The fields time_engine times, by place and column: field i % F for the i-th single call and
    the first `batch` for the batch, C.fields laying the fields out place by place."""
    single = [i % len(start) for i in range(calls)]
    many = list(range(min(batch, len(start))))
    return {"single": {"places": [LEVELS[start[i]] for i in single], "columns": [int(col[i]) for i in single]},
            "batch": {"places": [LEVELS[start[i]] for i in many], "columns": [int(col[i]) for i in many]}}


def speed(pool: Sequence[MS.Measure], order: Sequence[int], values: np.ndarray, widths: Sequence[int] = WIDTHS,
          ks: Optional[Sequence[int]] = None, engines: Sequence[str] = tuple(ENGINES), calls: int = SPEED_CALLS,
          batch: int = SPEED_BATCH, batches: int = SPEED_BATCHES, log=print) -> Tuple[Dict[tuple, dict], dict]:
    """{(engine, measures, width): times} at every prefix of the order (or the prefixes ks) on the
    fields of `values` (columns, bodies, measures), single-threaded, and how they were taken: the
    counts, the fields timed, every thread pool as it is inside the limit after the last timing,
    the machine and the versions."""
    from threadpoolctl import threadpool_limits
    mu, sd = MS.arrays(pool)
    noise, power = MS.errors(pool), MS.powers(pool)
    ks = list(range(1, len(order) + 1)) if ks is None else list(ks)
    if any(ENGINES[e][0] is _compiled_namer for e in engines):
        load_compiled()
    out, fields = {}, {}
    with threadpool_limits(1):
        for n in widths:
            offsets = np.arange(n)
            X, start, col = C.fields(values, offsets)
            fields[str(n)] = timed_fields(start, col, calls, batch)
            for engine in engines:
                make, kind = ENGINES[engine]
                nodes = _nodes(kind)
                for k in ks:
                    idx = list(order[:k])
                    namer = make(mu[idx], sd[idx], noise[idx], power[idx], offsets, nodes)
                    out[(engine, k, n)] = time_engine(namer, X[:, idx, :], calls, batch, batches)
                log("speed: %s at %d bodies, %d measures: %.2f ms a field alone, %.2f ms in a batch"
                    % (engine, n, ks[-1], out[(engine, ks[-1], n)]["median_ms"], out[(engine, ks[-1], n)]["batch_ms"]))
        threads = pools()
    how = {"calls": int(calls), "batch": int(batch), "batches": int(batches), "columns": int(len(values)),
           "measures": [int(k) for k in ks], "widths": [int(n) for n in widths], "engines": list(engines),
           "fields": fields, "threads": threads, "machine": machine(), "versions": versions()}
    return out, how


def nuts_fields(start: np.ndarray) -> np.ndarray:
    """Which fields NUTS runs on: one at each place, the i-th place's from the i-th column (modulo
    the columns that hold it), so that its distance from the exact posterior is measured where the
    posterior is spread as well as at C3, where C.fields's place-major layout puts its first fields."""
    places = np.unique(start)
    return np.array([np.flatnonzero(start == p)[i % np.count_nonzero(start == p)] for i, p in enumerate(places)])


def nuts_run(X: np.ndarray, hyp, mu: np.ndarray, sd: np.ndarray, keys: Sequence[str], noise: np.ndarray,
             power: np.ndarray, exact: np.ndarray, draws: int = NUTS_DRAWS, tune: int = NUTS_TUNE) -> dict:
    """One NUTS run on the fields X: the seconds a call to build the model (build_s) and to set the
    sampler up (setup_s: pm.sample's time less its own loop's, sampling_time, and the first
    hypothesis_posterior call's less the second's, which compiles nothing), the seconds a field of
    NUTS's own loop (sample_s) and of averaging the posterior (posterior_s, the second call); each
    field's distance from the exact posterior (gap, the largest over places), Monte Carlo error and
    R-hat, the divergences and leapfrog steps of the kept draws, and the files the run added to
    PyTensor's Numba cache (cache_files, numba_cache_files), some where it compiled some of its
    graph and none where its graph was compiled already, by an earlier run or process, NaN where
    the cache could not be read."""
    import arviz as az
    from . import model as MD
    F = len(X)
    cached = numba_cache_files()
    t0 = time.perf_counter()
    m = MD.naming(X, hyp, mu, sd, list(keys), noise=noise, power=power)
    t1 = time.perf_counter()
    idata = MD.sample(m, draws=draws, tune=tune, chains=NUTS_CHAINS, seed=NUTS_SEED)
    t2 = time.perf_counter()
    loop = float(idata.posterior.attrs.get("sampling_time", float("nan")))     # tuning and draws, after the setup
    MD.hypothesis_posterior(m, idata)                                           # the first call compiles p(h | x, s)
    t3 = time.perf_counter()
    post, mcse = MD.hypothesis_posterior(m, idata)
    t4 = time.perf_counter()
    now_cached = numba_cache_files()
    gap = np.abs(post - exact).max(1)
    rhat = np.asarray(az.rhat(idata, var_names=["log_s"])["log_s"].values, float).reshape(F)
    stats = idata.sample_stats
    return {"fields": F, "build_s": t1 - t0, "setup_s": (t2 - t1 - loop) + (t3 - t2) - (t4 - t3),
            "sample_s": loop / F, "posterior_s": (t4 - t3) / F,
            "gap": gap.tolist(), "mcse": mcse.max(1).tolist(), "rhat": rhat.tolist(),
            "max_gap": float(gap.max()), "max_mcse": float(mcse.max()), "max_rhat": float(rhat.max()),
            "divergences": int(np.asarray(stats["diverging"].values).sum()),
            "n_steps": int(np.asarray(stats["n_steps"].values).sum()),
            "cache_files": float("nan") if cached is None or now_cached is None else now_cached - cached}


def nuts_speed(pool: Sequence[MS.Measure], order: Sequence[int], values: np.ndarray, ks: Sequence[int] = NUTS_MEASURES,
               n: int = NUTS_WIDTH, draws: int = NUTS_DRAWS, tune: int = NUTS_TUNE,
               log=print) -> Tuple[Dict[int, dict], dict]:
    """NUTS on the naming model at each number of measures of the order (nuts_run), on one field at
    each place of the columns `values` (nuts_fields) sampled together in one model, and on the
    middle one of them alone, single-threaded as speed() is: {measures: {"together": run,
    "alone": run}}, each run with its fields' places, columns and positions among the together
    run's (at), and how it ran, with the files PyTensor's Numba cache held when it began."""
    from threadpoolctl import threadpool_limits
    from . import compiled as K
    mu, sd = MS.arrays(pool)
    noise, power = MS.errors(pool), MS.powers(pool)
    offsets = np.arange(n)
    X, start, col = C.fields(values, offsets)
    pick = nuts_fields(start)
    runs = (("together", list(range(len(pick)))), ("alone", [len(pick) // 2]))
    hyp = K.hypotheses(len(LEVELS), [offsets])
    cache_files = numba_cache_files()
    load_compiled()
    out = {}
    with threadpool_limits(1):
        for k in ks:
            idx = list(order[:k])
            Xk = X[pick][:, idx, :]
            exact = _numpy_namer(mu[idx], sd[idx], noise[idx], power[idx], offsets, _nodes("trapezoid"))(Xk)
            out[k] = {}
            for how, at in runs:
                run = nuts_run(Xk[at], hyp, mu[idx], sd[idx], [pool[i].key for i in idx], noise[idx], power[idx],
                               exact[at], draws, tune)
                run.update(at=list(at), places=[LEVELS[s] for s in start[pick[at]]], columns=col[pick[at]].tolist())
                out[k][how] = run
            t, a = out[k]["together"], out[k]["alone"]
            worst = int(np.argmax(t["gap"]))
            log("nuts: %d measures, %d fields together, %.2f s a field of NUTS's loop after %.1f s of setup, "
                "largest gap %.1e at %s (R-hat %.2f); alone at %s, %.2f s of loop, gap %.1e"
                % (k, t["fields"], t["sample_s"], t["setup_s"], t["max_gap"], t["places"][worst], t["rhat"][worst],
                   a["places"][0], a["sample_s"], a["max_gap"]))
        threads = pools()
    how = {"width": int(n), "draws": int(draws), "tune": int(tune), "chains": NUTS_CHAINS, "seed": NUTS_SEED,
           "measures": [int(k) for k in ks], "columns": int(len(values)), "places": [LEVELS[s] for s in start[pick]],
           "field_columns": col[pick].tolist(), "alone": LEVELS[start[pick[runs[1][1][0]]]], "threads": threads,
           "cache_files": cache_files, "machine": machine(), "versions": versions()}
    return out, how


def timings(pool: Sequence[MS.Measure], order: Sequence[int], values: np.ndarray, quick: bool = False,
            log=print) -> Tuple[Dict[tuple, dict], Dict[int, dict], dict]:
    """The times of the study at study_counts(quick): speed() and nuts_speed() on `values`, and
    how each was taken."""
    counts = study_counts(quick)
    times, speed_how = speed(pool, order, values, ks=counts["speed_measures"], calls=counts["speed_calls"],
                             batch=counts["speed_batch"], batches=counts["speed_batches"], log=log)
    nuts, nuts_how = nuts_speed(pool, order, values, ks=counts["nuts_measures"], log=log)
    return times, nuts, {"speed": speed_how, "nuts": nuts_how}


# ---- the record -----------------------------------------------------------------------------

def code_state() -> dict:
    """The package's digest, the table's digest as measures.py read it, and the git state, as they
    are now: run and add_speed take it before any work, so that a record names the code and the
    table that made it, and again when they build the record (changed_during)."""
    from .records import code_digest
    return {"digests": {"panjabi_long.csv": MS.dataset().attrs["sha256"], "schwingcheck": code_digest()},
            "git": git_state()}


def changed_during(before: dict, after: dict) -> dict:
    """What moved between two code_state()s, at the later's values: compiled.py and model.py are
    imported only when the times reach them, so a change here may have run."""
    out = {k: v for k, v in after["digests"].items() if before["digests"].get(k) != v}
    if after["git"] != before["git"]:
        out["git"] = after["git"]
    return out


def actual_counts(arms: Sequence[Arm], n_select: Optional[int], quick: bool) -> dict:
    """The counts the arms were scored at, read off the arms themselves, and the selection's."""
    typical = next((a for a in arms if a.name == "nominal" and a.phenotype == "typical"), None)
    anomalous = next((a for a in arms if a.phenotype in ANOMALOUS), None)
    axis = next((a for a in arms if "people" in a.settings), None)
    worlds: Dict[int, set] = {}
    for a in arms:
        if a.settings.get("people") and a.settings.get("rule") == "nominal":
            worlds.setdefault(int(a.settings["people"]), set()).add(a.world)
    return {"score": len(typical.values) if typical else None, "select": n_select,
            "anomalous": len(anomalous.values) if anomalous else None,
            "world_columns": len(axis.values) if axis else None,
            "worlds": {str(p): len(w) for p, w in sorted(worlds.items())} or None, "quick": bool(quick)}


def build_record(rate_rows: Dict[tuple, dict], pool: Sequence[MS.Measure], order: Sequence[int], trace: Sequence[dict],
                 index: Dict[str, List[int]], arms: Sequence[Arm], times: Dict[tuple, dict], nuts: Dict[int, dict],
                 command: str, quick: bool, made_by: Optional[dict] = None, how: Optional[dict] = None,
                 n_select: Optional[int] = None):
    """The study as one xarray DataTree: rates (arm, phenotype, subset, width) for every statistic,
    NaN where an arm did not score a subset, phenotype or width; the order and its selection log
    loss; the subsets' members; the times; and in the root's attributes the command, the seeds,
    the counts the arms were scored at, the settings, the digests and git state taken when the run
    began (made_by, code_state(), now when not given) with what changed by now (changed_during_run),
    how the times were taken (how["speed"], how["nuts"]), and the machine and versions that built it."""
    import arviz as az
    import xarray as xr
    from . import __version__
    now = code_state()
    made_by = made_by or now
    how = how or {}
    arm_names = list(dict.fromkeys(a.name for a in arms))
    phenotypes = ["typical"] + list(ANOMALOUS)
    subs = list(index)
    widths = sorted({n for a in arms for n in a.widths})
    shape = (len(arm_names), len(phenotypes), len(subs), len(widths))
    data = {s: np.full(shape, np.nan) for s in STATS}
    for (name, ph, sub, n), row in rate_rows.items():
        at = (arm_names.index(name), phenotypes.index(ph), subs.index(sub), widths.index(n))
        for s in STATS:
            data[s][at] = row[s]
    dims = ("arm", "phenotype", "subset", "width")
    rates_ds = xr.Dataset({s: (dims, v) for s, v in data.items()},
                          coords={"arm": arm_names, "phenotype": phenotypes, "subset": subs, "width": widths})
    keys = [m.key for m in pool]
    member = np.zeros((len(subs), len(keys)), bool)
    for i, sub in enumerate(subs):
        member[i, index[sub]] = True
    subsets_ds = xr.Dataset({"member": (("subset", "measure"), member)}, coords={"subset": subs, "measure": keys})
    order_ds = xr.Dataset({"measure": ("step", [t["measure"] for t in trace]), "loss": ("step", [t["loss"] for t in trace])},
                          coords={"step": np.arange(1, len(trace) + 1)})
    for n in WIDTHS:
        order_ds["loss_%d" % n] = ("step", [t["loss_by_width"][str(n)] for t in trace])
    tree = xr.DataTree.from_dict({"/rates": rates_ds, "/subsets": subsets_ds, "/order": order_ds,
                                  "/speed": speed_dataset(times), "/nuts": nuts_dataset(nuts)})
    settings = {a.name: a.settings for a in arms if a.settings}
    seeds = {"score": SCORE_SEED, "score_extra": EXTRA_SEED, "select": SELECT_SEED, "select_extra": SELECT_EXTRA_SEED,
             "anomalous": ANOMALOUS_SEED, "anomalous_extra": ANOMALOUS_EXTRA_SEED, "correlated": CORRELATED_SEED,
             "worlds": WORLD_SEED, "nuts": NUTS_SEED}
    tree.attrs.update({
        "command": command, "seeds": json.dumps(seeds, sort_keys=True),
        "counts": json.dumps(actual_counts(arms, n_select, quick), sort_keys=True),
        "synth": json.dumps(R.SYNTH, sort_keys=True), "settings": json.dumps(settings, sort_keys=True),
        "order": json.dumps([pool[i].key for i in order]),
        "pool": json.dumps([{"key": m.key, "kind": m.kind, "error": m.error, "power": m.size_power,
                             "family": family_of(m), "planes": list(m.planes)} for m in pool]),
        "speed": json.dumps(how.get("speed", {}), sort_keys=True),
        "nuts": json.dumps(how.get("nuts", {}), sort_keys=True),
        "floor": json.dumps(floor_counts(arms, keys), sort_keys=True),
        "digests": json.dumps(made_by["digests"], sort_keys=True),
        "git": json.dumps(made_by["git"], sort_keys=True),
        "changed_during_run": json.dumps(changed_during(made_by, now), sort_keys=True),
        "machine": json.dumps(machine(), sort_keys=True),
        "schwingcheck": __version__, "xarray": xr.__version__, "arviz": az.__version__,
        "nodes": "trapezoid, step %g in log s out to %g SD" % (R.TRAPEZOID_STEP, R.TRAPEZOID_REACH)})
    tree.attrs.update(versions())
    return tree


def speed_dataset(times: Dict[tuple, dict]):
    """The times as (engine, measures, width) arrays, NaN where none was measured."""
    import xarray as xr
    engines = list(ENGINES)
    ks = sorted({k for _, k, _ in times}) or [0]
    tw = sorted({n for _, _, n in times}) or list(WIDTHS)
    sp = {s: np.full((len(engines), len(ks), len(tw)), np.nan) for s in ("median_ms", "max_ms", "batch_ms", "batch_max_ms")}
    for (e, k, n), row in times.items():
        for s in sp:
            sp[s][engines.index(e), ks.index(k), tw.index(n)] = row.get(s, np.nan)
    return xr.Dataset({s: (("engine", "measures", "width"), v) for s, v in sp.items()},
                      coords={"engine": engines, "measures": ks, "width": tw})


NUTS_HOW = ("together", "alone")
NUTS_STATS = ("fields", "build_s", "setup_s", "sample_s", "posterior_s", "max_gap", "max_mcse", "max_rhat",
              "divergences", "n_steps", "cache_files")
NUTS_FIELD_STATS = ("gap", "mcse", "rhat")


def nuts_dataset(nuts: Dict[int, dict]):
    """NUTS's numbers as (measures, how) arrays, how being together or alone, and each field's gap,
    Monte Carlo error and R-hat as (measures, how, field) arrays over the together run's fields,
    with each field's place and column; NaN where none was measured."""
    import xarray as xr
    nk = sorted(nuts) or [0]
    first = nuts[nk[0]]["together"] if nuts else {"fields": 1, "places": [""], "columns": [-1]}
    F = int(first["fields"])
    scal = {s: np.full((len(nk), len(NUTS_HOW)), np.nan) for s in NUTS_STATS}
    per = {s: np.full((len(nk), len(NUTS_HOW), F), np.nan) for s in NUTS_FIELD_STATS}
    for i, k in enumerate(nk):
        for j, h in enumerate(NUTS_HOW):
            r = nuts.get(k, {}).get(h)
            if not r:
                continue
            for s in NUTS_STATS:
                scal[s][i, j] = r.get(s, np.nan)
            at = r.get("at", list(range(len(r.get("gap", [])))))
            for s in NUTS_FIELD_STATS:
                if s in r:
                    per[s][i, j, at] = r[s]
    data = {s: (("measures", "how"), v) for s, v in scal.items()}
    data.update({s: (("measures", "how", "field"), v) for s, v in per.items()})
    return xr.Dataset(data, coords={"measures": nk, "how": list(NUTS_HOW), "field": np.arange(F),
                                    "place": ("field", list(first["places"])),
                                    "column": ("field", np.asarray(first["columns"], int))})


def git_state() -> dict:
    """The commit the code ran from and whether the package's files differed from it, so a record
    names the code that made it even after later commits change the package's digest. git runs
    with its optional locks off, so that asking writes nothing into the repository's index."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

    def git(*a):
        return subprocess.run(["git", "-C", T.ROOT] + list(a), capture_output=True, text=True, env=env).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "package_changed": bool(git("status", "--porcelain", "--", "schwingcheck"))}


def add_speed(path: str, command: str, quick: bool = False, log=print) -> None:
    """Measure the times on the order a record holds and write them into the record, which is
    done apart from the scoring so that the times are taken with nothing else running; the code,
    the table and the git state that timed are recorded beside the scoring's (speed_digests,
    speed_git, speed_changed_during_run), and the record is replaced only once the new one is whole."""
    import xarray as xr
    from .records import read, write
    made_by = code_state()                   # before any timing: the code and the git state that time
    tree = read(path)
    tree.load()
    tree.close()
    pool = MS.pool()
    keys = [m.key for m in pool]
    order = [keys.index(k) for k in json.loads(tree.attrs["order"])]
    values = draw_pool(pool, "typical", SCORE_SEED, EXTRA_SEED, SPEED_COLUMNS).values
    times, nuts, how = timings(pool, order, values, quick, log)
    parts = {"/" + name: tree[name].to_dataset() for name in ("rates", "subsets", "order")}
    out = xr.DataTree.from_dict(dict(parts, **{"/speed": speed_dataset(times), "/nuts": nuts_dataset(nuts)}))
    out.attrs.update(tree.attrs)
    out.attrs.update({"speed_command": command, "speed_digests": json.dumps(made_by["digests"], sort_keys=True),
                      "speed_git": json.dumps(made_by["git"], sort_keys=True),
                      "speed_changed_during_run": json.dumps(changed_during(made_by, code_state()), sort_keys=True),
                      "speed": json.dumps(how["speed"], sort_keys=True), "nuts": json.dumps(how["nuts"], sort_keys=True)})
    write(out, path)


def run(outdir: Optional[str], command: str = "", quick: bool = False, processes: int = PROCESSES,
        with_speed: bool = True, log=print):
    """The whole study: the order, every arm, the times, written to outdir/curve.nc once the
    scoring is done and again with the times."""
    made_by = code_state()                   # before any work: the code and the table that run
    pool = MS.pool()
    t0 = time.time()
    select = draw_pool(pool, "typical", SELECT_SEED, SELECT_EXTRA_SEED, study_counts(quick)["select"])
    order, trace = greedy_order(pool, select, log=log)
    log("the order took %.0f s" % (time.time() - t0))
    index = subsets(pool, order)
    arms = make_arms(pool, list(index), quick)
    rate_rows = run_arms(arms, index, processes, log)

    def record(times, nuts, how):
        tree = build_record(rate_rows, pool, order, trace, index, arms, times, nuts, command, quick,
                            made_by=made_by, how=how, n_select=len(select.values))
        if outdir:
            from .records import write
            write(tree, os.path.join(outdir, "curve.nc"))
        return tree

    tree = record({}, {}, {})                # the scoring, kept whatever the timing does
    if with_speed:
        tree = record(*timings(pool, order, arms[0].values[:SPEED_COLUMNS], quick, log))
    log("the study took %.0f s" % (time.time() - t0))
    return tree
