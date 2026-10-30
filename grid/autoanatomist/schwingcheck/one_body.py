"""What one body alone tells: the one-vertebra evaluation, on synthetic columns of Panjabi's tables.

    python -m schwingcheck.one_body run [--columns 500]      # one_body.json
    python -m schwingcheck.one_body table [--table sets]     # a table of the record, or of chain_study's at one body
    python -m schwingcheck.one_body figures                  # the figures and FIGURES.md
    python -m schwingcheck.one_body check                    # whether the README's tables are the record's

The owner's queue of 27 October 2026, 09:44 UTC, item 1: "evaluate the Panjabi synthetic data fully
for 1-vertebra prediction". A C-arm shot that shows one vertebra is named from that body's measures
alone: no neighbour shares its patient's size and no step down the column says which name comes
next. This module asks what such a body tells, level by level, measure set by measure set, column
type by column type, and how much a known height gives back.

The fields. Every body of every column is a field of its own, so every level is scored as often as
any other, each on as many fields as there are columns of its type. The columns are the generator's
(curve.draw_pool: every measure of the pool for the same patients) of the chain's three types,
typical, six-lumbar and with a T13 (chain.TYPES). A field the chain's own law draws at one body is a
body of its column chosen uniformly (chain.draw_fields), so a type's rates over these fields are the
rates that law gives, and chain_study's one-body rows estimate them on fewer fields.

The rule. At one body the chain takes no step, so its paths are its states, and a body's likelihood
depends on its name alone, the L6 and the T13 on the columns chain.extended_table builds: the
posterior over the 24 names is rule.py's at offsets (0,) on the extended table under a prior over
the names that sums each type's weight over the names it has (prior_over_names). The tests hold it
to chain.logev at one body. The priors: `typical`, the typical column alone, which is step d's rule
at one body and has no L6 or T13 to name; `chain`, the three types at the stated weights
(chain.WEIGHTS); and the clinical reread's weights (chain_study.WEIGHT_SETS).

The measures. The seven, all 32, the four each of the lateral and the AP views (measures.REGIMES, the
archive's regimes, h_post in both), and every prefix of the build-up study's greedy order, read from
its record (CURVE_RECORD), whose seven first measures are not the seven.

The size. A patient's size multiplies every length, and at one body nothing else in the field says
what it is: the size is one of the two things a lone body loses against a field of several, beside
the step down the column that says which name comes next. Four rules take it four ways (SIZES),
each on the same fields:

- unknown: log s ~ N(0, 0.07^2), the generator's spread, as every rule before;
- height, model: the patient's height known and taken as covariates.CovariateModel takes it,
  isometric scaling with its coefficient's prior integrated, log s ~ N(log(h / 167.75), 0.07^2 +
  0.5^2 log(h / 167.75)^2), which overstates the spread once the height is known;
- height, generator: the same height with the spread of size about it that the generator drew, what
  a model whose residual had been estimated from patients would take from it;
- size given: the patient's own size, the most that anything which tells the size could give.

A known height means something only where the generator ties size to height, which Panjabi's twelve
spines cannot do (covariates.py). So each column's patient has a height drawn log-normal about the
twelve specimens' mean with the spread of their log heights (0.041, specimen_log_height_sd), and a
size by isometric scaling with a residual that keeps the generator's own spread of size (draw_sizes):
log s = log(h / 167.75) + e, e ~ N(0, 0.07^2 - 0.041^2), so that log s ~ N(0, 0.07^2) as before and
the first rule is the generator's posterior still. The tie is an assumption made for this test, the
covariate model's prior mean taken as the truth, and no measurement.

The coarse answers. A lone body that cannot be named may still say on which side of a border it
lies. Each of the coarse study's six claims (coarse/study.py, CLAIMS) is the posterior mass on the
names it holds, decided when that mass reaches 0.99 either way, as coarse.score_claims decides it. A
name holds a claim by where it sits on curve.POSITION: below a border is at or past its first level
below, at or above is at or before the level named, within is between the two ends. So an L6 is
below every border, and a T13, the thoracic body between T12 and L1, is below C7 and T5, not at or
above T6, not below T12 nor below L2, and within T11 to L2.

The data axis at one body is chain_study's own record at one body (the table `axis`): its tables,
re-estimated from 12 to 2,000 people, were scored there at one body on its fields, two a column.

Every number is about synthetic columns drawn from Panjabi's tables; nothing here is a patient.
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import platform
import re
import time
from typing import Dict, List, Sequence, Tuple

import numpy as np

from . import chain as CH
from . import chain_study as CS
from . import covariates as CO
from . import curve as CV
from . import measures as MS
from . import records as RC
from . import rule as R
from . import score as S
from . import table as T
from .figures import INK, SERIF, letter, save, sha256, style, write_csv

COLUMNS = 500
SEED, EXTRA_SEED, HEIGHT_SEED = 801, 901, 1001
PROCESSES = 3
CLAIM = CV.CLAIM
PRIORS = ("typical", "chain") + tuple(CS.WEIGHT_SETS)
SIZES = ("unknown", "height, model", "height, generator", "size given")
VIEWS = ("seven", "lateral", "ap", "all")
LEVEL_RULES = [(p, "unknown") for p in PRIORS] + [("chain", s) for s in SIZES[1:]]   # the rules scored level by level
CONFUSION = (("typical", "seven"), ("typical", "all"), ("chain", "seven"), ("chain", "all"))
ROOT = CS.ROOT
CURVE_RECORD = os.path.join(ROOT, "records", "curve-2026-10-28", "curve.nc")
RECORD_DIR = os.path.join(ROOT, "records", "one-body-2026-10-29")
RECORD = os.path.join(RECORD_DIR, "one_body.json")
OUTDIR = os.path.join(RECORD_DIR, "figures")
README = CS.README
QUICK = {"columns": 3}


# ---- the fields -----------------------------------------------------------------------------

def specimen_log_height_sd() -> float:
    """The SD of the log heights of Panjabi's twelve specimens (thoracic Table 1)."""
    h = np.array([float(r["height_cm"]) for r in T.read_specimens_csv()])
    return float(np.std(np.log(h), ddof=1))


def draw_sizes(n: int, seed: int, scale_sd: float = R.SYNTH["scale_sd"]) -> Tuple[np.ndarray, np.ndarray, float]:
    """n patients' heights (cm) and sizes, and the residual SD of log size about log height: log
    height about the specimens' mean with their spread, log size isometric with it plus a residual
    that keeps the generator's spread of size, scale_sd, whole."""
    spread = specimen_log_height_sd()
    if spread >= scale_sd:
        raise ValueError("the heights' spread %.4f leaves no room in a size spread of %.4f" % (spread, scale_sd))
    resid = math.sqrt(scale_sd ** 2 - spread ** 2)
    rng = np.random.default_rng(seed)
    dlogh = rng.normal(0.0, spread, n)
    log_s = dlogh + rng.normal(0.0, resid, n)
    return CO.HEIGHT_REF * np.exp(dlogh), np.exp(log_s), resid


def every_body(cols) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every body of every column as a field of one body: X (fields, measures, 1), the name of each
    as an index into chain.NAMES, and its column."""
    X, names, col = [], [], []
    for c in range(len(cols)):
        for p, level in enumerate(cols.levels[c]):
            X.append(cols.values[c, p, :][:, None])
            names.append(CH.NAME_INDEX[level])
            col.append(c)
    return np.array(X), np.array(names), np.array(col)


def draw_type(pool, ti: int, n_columns: int):
    """One type's columns, its patients' heights and sizes, and every body of them as a field."""
    kind = CH.TYPES[ti]
    height, size, resid = draw_sizes(n_columns, HEIGHT_SEED + ti)
    cols = CV.draw_pool(pool, kind, SEED + ti, EXTRA_SEED + ti, n_columns, scale=size)
    X, names, col = every_body(cols)
    return {"kind": kind, "X": X, "names": names, "col": col, "height": height, "size": size, "resid": resid}


# ---- the rule -------------------------------------------------------------------------------

def prior_over_names(prior: str) -> np.ndarray:
    """The prior over chain.NAMES of a lone body: each type's weight spread evenly over its names
    and summed, as the chain's start is at one body."""
    if prior == "typical":
        weights = {"typical": 1.0}
    elif prior == "chain":
        weights = dict(CH.WEIGHTS)
    else:
        weights = dict(zip(CH.TYPES, CS.WEIGHT_SETS[prior]))
    out = np.zeros(len(CH.NAMES))
    for kind, w in weights.items():
        levels = CH.type_levels(kind)
        for level in levels:
            out[CH.NAME_INDEX[level]] += w / len(levels)
    return out


def size_priors(height: np.ndarray, size: np.ndarray, resid: float) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Each size rule's prior of log s for every column, (mean, SD), the SD 0 where the size is given."""
    n = len(height)
    dlogh = np.log(height / CO.HEIGHT_REF)
    model_mean, model_sd = CO.CovariateModel().size_prior([CO.Covariates(height_cm=float(h)) for h in height])
    return {"unknown": (np.zeros(n), np.full(n, R.SYNTH["scale_sd"])),
            "height, model": (np.asarray(model_mean, float), np.asarray(model_sd, float)),
            "height, generator": (dlogh, np.full(n, resid)),
            "size given": (np.log(size), np.zeros(n))}


def nodes_of(mean: float, sd: float) -> Tuple[np.ndarray, np.ndarray]:
    """Sizes and log weights for log s ~ N(mean, sd^2): the trapezoid's grid for N(0, sd^2) moved to
    the mean, so that it holds the prior whole wherever the height puts it; one node at the size
    where sd is 0."""
    if sd <= 0:
        return np.array([math.exp(mean)]), np.zeros(1)
    s, logw = R.trapezoid(sd)
    return s * math.exp(mean), logw


def subsets_of(pool, order: Sequence[str]) -> Tuple[Dict[str, List[int]], List[int]]:
    """The named measure sets as indices into the pool, and the build-up order's."""
    keys = [m.key for m in pool]
    sets = {"seven": [keys.index(k) for k in MS.SPINEPS_7], "lateral": [keys.index(k) for k in MS.REGIMES["lateral"]],
            "ap": [keys.index(k) for k in MS.REGIMES["ap"]], "all": list(range(len(keys)))}
    return sets, [keys.index(k) for k in order]


def column_logev(X: np.ndarray, nodes, mu_e, sd_e, noise, power, sets, order=None) -> Dict[str, np.ndarray]:
    """log p(body | name) of one column's bodies, (fields, names), under every named set and, with
    an order, every prefix of it, as 'first k'."""
    sizes, logw = nodes
    LL = R.loglik(X, (0,), mu_e, sd_e, R.SYNTH, sizes=sizes, noise=noise, power=power)     # (f, names, M, J)
    out = {k: R.log_evidence(LL, logw, idx) for k, idx in sets.items()}
    if order is not None:
        acc = np.cumsum(LL[:, :, order, :], axis=2)
        pref = R.logsumexp(acc + logw[None, None, None, :], 3)
        for i in range(len(order)):
            out["first %d" % (i + 1)] = pref[:, :, i]
    return out


_JOB: dict = {}


def job(task: Tuple[int, int, int]) -> Tuple[int, int, Dict[Tuple[str, str], np.ndarray]]:
    """The log evidence of columns c0 to c1 of one type under every size rule and measure set, the
    prefixes of the order under the unknown size alone."""
    from threadpoolctl import threadpool_limits
    ti, c0, c1 = task
    a = _JOB
    d = a["drawn"][ti]
    priors = size_priors(d["height"], d["size"], d["resid"])
    out: Dict[Tuple[str, str], list] = {}
    with threadpool_limits(1):
        for c in range(c0, c1):
            X = d["X"][d["col"] == c]
            for size in SIZES:
                nodes = nodes_of(priors[size][0][c], priors[size][1][c])
                order = a["order"] if size == "unknown" else None
                for k, v in column_logev(X, nodes, a["mu_e"], a["sd_e"], a["noise"], a["power"], a["sets"], order).items():
                    out.setdefault((size, k), []).append(v)
    return ti, c0, {k: np.concatenate(v) for k, v in out.items()}


def logevidence(drawn, order, sets, mu_e, sd_e, noise, power, processes: int, log=print) -> List[Dict[tuple, np.ndarray]]:
    """Every type's log evidence by (size rule, measure set), its fields in their drawn order."""
    global _JOB
    _JOB = {"drawn": drawn, "order": order, "sets": sets, "mu_e": mu_e, "sd_e": sd_e, "noise": noise, "power": power}
    step = max(1, len(drawn[0]["height"]) // 10)
    tasks = [(ti, c0, min(c0 + step, len(d["height"]))) for ti, d in enumerate(drawn) for c0 in range(0, len(d["height"]), step)]
    t0 = time.time()
    if processes > 1:
        with multiprocessing.get_context("fork").Pool(processes) as p:
            results = []
            for r in p.imap_unordered(job, tasks):
                results.append(r)
                log("one body: %d of %d jobs in %.0f s" % (len(results), len(tasks), time.time() - t0))
    else:
        results = [job(t) for t in tasks]
    out: List[Dict[tuple, list]] = [{} for _ in drawn]
    for ti, c0, part in sorted(results, key=lambda r: (r[0], r[1])):
        for k, v in part.items():
            out[ti].setdefault(k, []).append(v)
    return [{k: np.concatenate(v) for k, v in each.items()} for each in out]


# ---- the scores -----------------------------------------------------------------------------

def stats_of(post: np.ndarray, truth: np.ndarray, X: np.ndarray, idx: Sequence[int], power: np.ndarray) -> dict:
    st = CS.name_stats(post, truth)
    st["floored"] = CV.floored_in(X, idx, power)
    return st


def claims():
    """The coarse study's claims, read from it, so that the two never part."""
    from coarse import study as coarse_study
    return coarse_study.CLAIMS


def claim_holds(claim: dict) -> np.ndarray:
    """Which of chain.NAMES the claim is true of, by where each sits on curve.POSITION."""
    at = CS.NAME_POSITION
    if "below" in claim:
        return at >= CV.POSITION[claim["below"]]
    if "above" in claim:
        return at <= CV.POSITION[claim["above"]]
    ends = [CV.POSITION[n] for n in claim["interval"]]
    return (at >= min(ends)) & (at <= max(ends))


def claim_rates(post: np.ndarray, truth: np.ndarray, col: np.ndarray, claim: dict) -> dict:
    """One claim on every field: how often it is decided at 0.99 either way, said true and said
    false, and right of those decided, with the precision's SE clustered by column."""
    holds = claim_holds(claim)
    mass = post[:, holds].sum(1)
    t = holds[truth]
    yes, no = mass >= CLAIM, mass <= 1.0 - CLAIM
    decided = yes | no
    wrong = (yes & ~t) | (no & t)
    inv = np.unique(col, return_inverse=True)[1]
    n_dec, errors = int(decided.sum()), int(wrong.sum())
    return {"decided": float(decided.mean()), "decided_se": S.clustered_se(decided.astype(float), col),
            "said_true": float(yes.mean()), "said_false": float(no.mean()), "n_decided": n_dec, "errors": errors,
            "true_share": float(t.mean()),
            "precision": float(1.0 - errors / n_dec) if n_dec else float("nan"),
            "precision_se": S.ratio_se(np.bincount(inv, weights=wrong), np.bincount(inv, weights=decided)),
            "precision_lower": CV.precision_lower(n_dec, errors)}


def level_rows(post, truth, X, idx, power, col, **keys) -> List[dict]:
    """The rates of every true name the fields hold, and the name each is most often taken for."""
    said = post.argmax(1)
    rows = []
    for n in np.unique(truth):
        f = truth == n
        st = stats_of(post[f], truth[f], X[f], idx, power)
        wrong = said[f][said[f] != n]
        common = np.bincount(wrong, minlength=len(CH.NAMES))
        rows.append({**keys, "name": CH.NAMES[n], **CV.rates(st, col[f]),
                     "most_taken_for": CH.NAMES[int(common.argmax())] if len(wrong) else None,
                     "most_taken_share": float(common.max() / f.sum()) if len(wrong) else 0.0})
    return rows


def score(drawn, logev, sets, order, power) -> dict:
    """Every table of the record from every type's log evidence."""
    named = dict(sets)
    prefixes = {"first %d" % (i + 1): order[:i + 1] for i in range(len(order))}
    rows, levels, coarse, confusion = [], [], [], []
    the_claims = claims()
    for d, ev in zip(drawn, logev):
        kind, X, truth, col = d["kind"], d["X"], d["names"], d["col"]
        for prior in PRIORS:
            with np.errstate(divide="ignore"):          # the typical column has no L6 and no T13
                lp = np.log(prior_over_names(prior))
            for size in SIZES:
                for k, idx in list(named.items()) + list(prefixes.items()):
                    if (size, k) not in ev or (size != "unknown" and prior not in ("typical", "chain")):
                        continue
                    post = R.posterior(ev[size, k], lp)
                    keys = {"type": kind, "prior": prior, "size": size, "measures": k}
                    rows.append({**keys, "n_measures": len(idx), **CV.rates(stats_of(post, truth, X, idx, power), col)})
                    if k in named and (prior, size) in LEVEL_RULES:
                        levels += level_rows(post, truth, X, idx, power, col, **keys)
                    if (k in named and (prior, size) in LEVEL_RULES) or (prior == "chain" and size == "unknown"):
                        for c in the_claims:
                            coarse.append({**keys, "claim": c["name"], **claim_rates(post, truth, col, c)})
                    if size == "unknown" and (prior, k) in CONFUSION:
                        said = post.argmax(1)
                        m = np.zeros((len(CH.NAMES), len(CH.NAMES)), int)
                        np.add.at(m, (truth, said), 1)
                        confusion.append({**keys, "counts": m.tolist()})
    return {"rows": rows, "levels": levels, "coarse": coarse, "confusion": confusion}


def build_up_order(path: str = CURVE_RECORD) -> List[str]:
    """The build-up study's greedy order of the 32, from its record."""
    tree = RC.read(path)
    try:
        return json.loads(tree.attrs["order"])
    finally:
        tree.close()


def run(n_columns: int = COLUMNS, processes: int = PROCESSES, log=print, order=None) -> dict:
    made_by = CV.code_state()
    pool, _, mu, sd, noise, power, _ = CS.setting()
    order = build_up_order() if order is None else list(order)
    sets, order_idx = subsets_of(pool, order)
    mu_e, sd_e = CH.extended_table(mu, sd)
    drawn = [draw_type(pool, ti, n_columns) for ti in range(len(CH.TYPES))]
    t0 = time.time()
    logev = logevidence(drawn, order_idx, sets, mu_e, sd_e, noise, power, processes, log)
    seconds = time.time() - t0
    scored = score(drawn, logev, sets, order_idx, power)
    d0 = drawn[0]
    return {"command": "python -m schwingcheck.one_body run --columns %d --processes %d" % (n_columns, processes),
            "columns_per_type": n_columns, "processes": processes,
            "fields_per_type": {d["kind"]: int(len(d["names"])) for d in drawn},
            "seeds": {"columns": SEED, "extra": EXTRA_SEED, "heights": HEIGHT_SEED}, "claim": CLAIM,
            "priors": {p: dict(zip(CH.NAMES, prior_over_names(p).tolist())) for p in PRIORS},
            "weights": {"chain": CH.WEIGHTS, **{k: dict(zip(CH.TYPES, v)) for k, v in CS.WEIGHT_SETS.items()}},
            "sizes": list(SIZES), "scale_sd": R.SYNTH["scale_sd"], "height_ref_cm": CO.HEIGHT_REF,
            "log_height_sd": specimen_log_height_sd(), "size_residual_sd": d0["resid"],
            "sets": {k: [pool[i].key for i in v] for k, v in sets.items()}, "order": order,
            "order_from": {"record": os.path.relpath(CURVE_RECORD, ROOT),
                           "sha256": sha256(CURVE_RECORD) if os.path.exists(CURVE_RECORD) else None},
            "claims": [c["name"] for c in claims()], "seconds": seconds, "machine": CV.machine(),
            "versions": CV.versions(), **CS.made(made_by), **scored}


# ---- the tables -----------------------------------------------------------------------------

pct = CS.pct
TYPE_LABEL = {"typical": "typical", "six_lumbar": "six-lumbar", "t13": "t13"}
SET_LABEL = {"seven": "the seven", "lateral": "lateral 4", "ap": "AP 4", "all": "all 32"}


def keyed(rows: List[dict], *keys: str) -> Dict[tuple, dict]:
    return {tuple(r[k] for k in keys): r for r in rows}


def answered_cell(r: dict) -> str:
    return "%s / %s (%d of %d)" % (pct(r["answered"]), pct(r["precision"], 2), r["n_answered"] - r["errors"], r["n_answered"])


def sets_table(record: dict) -> str:
    """Each type, measure set and rule, the size unknown: named exactly (SE), within one level, the
    99 per cent set's mean size, and the answers at 0.99 with the share of them right."""
    key = keyed(record["rows"], "type", "prior", "size", "measures")
    head = ["Column", "Measures", "Rule", "Exact (SE)", "Within one", "99% set", "Answered at 0.99 / right"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---|" + "---:|" * 4]
    for kind in CH.TYPES:
        for k in VIEWS:
            for prior in ("typical", "chain"):
                r = key[kind, prior, "unknown", k]
                out.append("| %s | %s | %s | %s (%s) | %s | %.2f | %s |" % (
                    TYPE_LABEL[kind], SET_LABEL[k], prior, pct(r["exact"]), pct(r["exact_se"]), pct(r["within_one"]),
                    r["set_size"], answered_cell(r)))
    return "\n".join(out) + "\n"


def levels_table(record: dict, prior: str = "chain") -> str:
    """Level by level, the size unknown: each name on its own columns (C3 to L5 on the typical
    ones, the L6 and the T13 on theirs), the seven and all 32: named exactly, the 99 per cent set's
    size, the answers at 0.99 and right of them, and what the seven most often take it for."""
    key = keyed(record["levels"], "type", "prior", "size", "measures", "name")
    head = ["Level", "The seven: exact", "99% set", "Answered / right", "Most often taken for",
            "All 32: exact", "99% set", "Answered / right"]
    out = ["| " + " | ".join(head) + " |", "|---|" + "---:|" * 3 + "---|" + "---:|" * 3]
    places = [("typical", n) for n in CH.type_levels("typical")] + [("six_lumbar", "L6"), ("t13", "T13")]
    for kind, name in places:
        s, a = key[kind, prior, "unknown", "seven", name], key[kind, prior, "unknown", "all", name]
        taken = "-" if s["most_taken_for"] is None else "%s (%s)" % (s["most_taken_for"], pct(s["most_taken_share"]))
        out.append("| %s | %s | %.2f | %s | %s | %s | %.2f | %s |" % (
            name if kind == "typical" else "%s (%s)" % (name, TYPE_LABEL[kind]), pct(s["exact"]), s["set_size"],
            answered_cell(s), taken, pct(a["exact"]), a["set_size"], answered_cell(a)))
    return "\n".join(out) + "\n"


def buildup_table(record: dict, counts=(1, 2, 3, 4, 5, 7, 10, 13, 16, 20, 24, 28, 32)) -> str:
    """The build-up study's order at one body, the chain, the size unknown: each type's share named
    exactly and its answers at 0.99, at the counts given, beside the seven."""
    key = keyed(record["rows"], "type", "prior", "size", "measures")
    head = ["Measures", "Last added"] + ["%s: exact / answered / right" % TYPE_LABEL[k] for k in CH.TYPES]
    out = ["| " + " | ".join(head) + " |", "|---|---|" + "---:|" * len(CH.TYPES)]

    def cells(k):
        return " | ".join("%s / %s / %s" % (pct(r["exact"]), pct(r["answered"]), pct(r["precision"], 2))
                          for r in (key[t, "chain", "unknown", k] for t in CH.TYPES))
    for n in counts:
        if n <= len(record["order"]):
            out.append("| first %d | %s | %s |" % (n, record["order"][n - 1], cells("first %d" % n)))
    out.append("| the seven | - | %s |" % cells("seven"))
    return "\n".join(out) + "\n"


def coarse_table(record: dict) -> str:
    """The coarse claims of a lone body, the chain, the size unknown: decided at 0.99 either way,
    and right of those, each type, the seven and all 32."""
    key = keyed(record["coarse"], "type", "prior", "size", "measures", "claim")
    head = ["Claim", "Measures"] + ["%s: decided / right" % TYPE_LABEL[k] for k in CH.TYPES]
    out = ["| " + " | ".join(head) + " |", "|---|---|" + "---:|" * len(CH.TYPES)]
    for c in record["claims"]:
        for k in VIEWS:
            cells = []
            for kind in CH.TYPES:
                r = key[kind, "chain", "unknown", k, c]
                cells.append("%s / %s (%d of %d)" % (pct(r["decided"]), pct(r["precision"], 2), r["n_decided"] - r["errors"],
                                                    r["n_decided"]))
            out.append("| %s | %s | %s |" % (c, SET_LABEL[k], " | ".join(cells)))
    return "\n".join(out) + "\n"


def size_table(record: dict) -> str:
    """What knowing the size gives a lone body: the chain on each type's fields, each measure set,
    the four size rules: named exactly (SE), the 99 per cent set and the answers at 0.99."""
    key = keyed(record["rows"], "type", "prior", "size", "measures")
    head = ["Column", "Measures"] + list(record["sizes"])
    out = ["| " + " | ".join(head) + " |", "|---|---|" + "---:|" * len(record["sizes"])]
    for kind in CH.TYPES:
        for k in VIEWS:
            cells = []
            for size in record["sizes"]:
                r = key[kind, "chain", size, k]
                cells.append("%s (%s); %.2f; %s / %s" % (pct(r["exact"]), pct(r["exact_se"]), r["set_size"],
                                                        pct(r["answered"]), pct(r["precision"], 2)))
            out.append("| %s | %s | %s |" % (TYPE_LABEL[kind], SET_LABEL[k], " | ".join(cells)))
    return "\n".join(out) + "\n"


def weights_table(record: dict) -> str:
    """The type weights at one body, the size unknown: each type's share named exactly and the
    L6's and the T13's on their own columns, the seven and all 32, every prior of the record."""
    key = keyed(record["rows"], "type", "prior", "size", "measures")
    lv = keyed(record["levels"], "type", "prior", "size", "measures", "name")
    head = ["Measures", "Prior", "Six-lumbar, t13"] + ["%s: exact" % TYPE_LABEL[k] for k in CH.TYPES] + \
           ["L6: exact / answered", "T13: exact / answered"]
    out = ["| " + " | ".join(head) + " |", "|---|---|---|" + "---:|" * (len(CH.TYPES) + 2)]
    for k in ("seven", "all"):
        for prior in PRIORS:
            w = record["weights"].get(prior, {"typical": 1.0, "six_lumbar": 0.0, "t13": 0.0})
            exact = ["%s (%s)" % (pct(key[t, prior, "unknown", k]["exact"]), pct(key[t, prior, "unknown", k]["exact_se"]))
                     for t in CH.TYPES]
            l6, t13 = lv["six_lumbar", prior, "unknown", k, "L6"], lv["t13", prior, "unknown", k, "T13"]
            out.append("| %s | %s | %.4g, %.4g | %s | %s / %s | %s / %s |" % (
                SET_LABEL[k], prior, w["six_lumbar"], w["t13"], " | ".join(exact), pct(l6["exact"]), pct(l6["answered"]),
                pct(t13["exact"]), pct(t13["answered"])))
    return "\n".join(out) + "\n"


TABLES = {"sets": sets_table, "levels": levels_table, "buildup": buildup_table, "coarse": coarse_table,
          "size": size_table, "weights": weights_table}


def load(path: str = RECORD) -> dict:
    with open(path) as f:
        return json.load(f)


def tables(path: str = RECORD) -> Dict[str, str]:
    """Every README table of the one-body section, by its marker."""
    record = load(path)
    out = {"one_body:%s" % name: fn(record) for name, fn in TABLES.items()}
    if os.path.exists(CS.RECORDS["axis"]) and os.path.exists(CS.RECORDS["main"]):
        axis, main = CS.load("axis"), CS.load("main")
        if 1 in axis["widths"] and 1 in main["widths"]:
            out["one_body:axis"] = CS.axis_table(axis, main, 1, "all")
            out["one_body:axis-seven"] = CS.axis_table(axis, main, 1, "seven")
    return out


def check(readme: str = README, path: str = RECORD) -> List[str]:
    """What differs between the README's one-body tables and the record's, as chain_study.check
    reads its own: an empty list when nothing does."""
    with open(readme) as f:
        have = CS.readme_blocks(f.read(), "one_body")
    return CS.compare_blocks(have, tables(path))


# ---- the figures ----------------------------------------------------------------------------

TYPE_NAME = {"typical": "Typical", "six_lumbar": "Six lumbar", "t13": "With a T13"}
SET_STYLE = {"seven": dict(linestyle="-", marker="o", markerfacecolor=INK),
             "all": dict(linestyle="--", marker="s", markerfacecolor="white"),
             "lateral": dict(linestyle=":", marker="^", markerfacecolor="white"),
             "ap": dict(linestyle="-.", marker="D", markerfacecolor="white", markersize=3.4)}
TYPE_STYLE = {"typical": dict(linestyle="-", marker="o", markerfacecolor=INK, markersize=3.2),
              "six_lumbar": dict(linestyle="--", marker="s", markerfacecolor="white", markersize=3.2),
              "t13": dict(linestyle=":", marker="^", markerfacecolor="white", markersize=3.2)}
CLAIM_MARKERS = ("o", "s", "^", "D", "v", "x")
CAPTIONS = {
    "one_body_levels":
        "A lone body named from its own measures, synthetic typical columns, %s fields a level, the chain's "
        "prior, size unknown: A, per cent named exactly; B, the mean size of the 99 per cent set; C, per cent "
        "named at 0.99. Lines, the measure sets.",
    "one_body_buildup":
        "A lone body as the build-up study's measures are added in its order, synthetic columns, every body of "
        "%s a type a field, the chain's prior, size unknown: A, per cent named exactly; B, per cent named at "
        "0.99; C, per cent within one level. Lines, the three column types.",
    "one_body_coarse":
        "Coarse claims a lone body decides at 0.99 either way, synthetic typical columns, the chain's prior, "
        "size unknown, %s fields a point, as the build-up study's measures are added: A, per cent decided; B, "
        "per cent of those right, dotted at 99. Markers, the six claims.",
    "one_body_size":
        "What knowing the patient's size gives a lone body, synthetic typical columns, the chain's prior, %s "
        "fields a point: A, per cent named exactly; B, per cent named at 0.99; from size unknown through a known "
        "height to the size itself. Lines, the measure sets.",
}


def percent(x) -> float:
    return 100.0 * x if x is not None and np.isfinite(x) else float("nan")


def fields_of(record: dict, kind: str = "typical") -> int:
    return record["fields_per_type"][kind]


def fig_levels(record: dict, outdir: str) -> List[str]:
    plt = style()
    key = keyed(record["levels"], "type", "prior", "size", "measures", "name")
    names = CH.type_levels("typical")
    x = np.arange(len(names))
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.6), layout="constrained")
    rows = []
    for ax, (panel, stat, label) in zip(axes, (("A", "exact", "Per cent named exactly"),
                                              ("B", "set_size", "Names in the 99 per cent set"),
                                              ("C", "answered", "Per cent named at 0.99"))):
        for k in VIEWS:
            ys = [key["typical", "chain", "unknown", k, n][stat] for n in names]
            ys = [y if stat == "set_size" else percent(y) for y in ys]
            ax.plot(x, ys, color=INK, label=SET_LABEL[k], **SET_STYLE[k])
            rows += [{"panel": panel, "measures": k, "level": n, "stat": stat, "value": y,
                      "fields": key["typical", "chain", "unknown", k, n]["n_fields"]} for n, y in zip(names, ys)]
        ax.set_xticks(x[::3])
        ax.set_xticklabels(names[::3])
        ax.set_xlabel("True level")
        ax.set_ylabel(label)
        letter(ax, panel)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncol=4)
    name = "one_body_levels"
    return save(fig, outdir, name, CAPTIONS[name] % "{:,}".format(record["columns_per_type"])) + [write_csv(outdir, name, rows)]


def fig_buildup(record: dict, outdir: str) -> List[str]:
    plt = style()
    key = keyed(record["rows"], "type", "prior", "size", "measures")
    counts = list(range(1, len(record["order"]) + 1))
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.6), layout="constrained")
    rows = []
    for ax, (panel, stat, label) in zip(axes, (("A", "exact", "Per cent named exactly"),
                                              ("B", "answered", "Per cent named at 0.99"),
                                              ("C", "within_one", "Per cent within one level"))):
        for kind in CH.TYPES:
            ys = [percent(key[kind, "chain", "unknown", "first %d" % n][stat]) for n in counts]
            ax.plot(counts, ys, color=INK, label=TYPE_NAME[kind], **TYPE_STYLE[kind])
            rows += [{"panel": panel, "type": kind, "measures": n, "stat": stat, "percent": y,
                      "fields": key[kind, "chain", "unknown", "first %d" % n]["n_fields"]} for n, y in zip(counts, ys)]
        ax.set_xticks([1, 8, 16, 24, 32])
        ax.set_xlabel("Measures, in the build-up order")
        ax.set_ylabel(label)
        letter(ax, panel)
    axes[0].legend(loc="lower right")
    name = "one_body_buildup"
    return save(fig, outdir, name, CAPTIONS[name] % "{:,}".format(record["columns_per_type"])) + [write_csv(outdir, name, rows)]


def fig_coarse(record: dict, outdir: str) -> List[str]:
    plt = style()
    key = keyed(record["coarse"], "type", "prior", "size", "measures", "claim")
    counts = list(range(1, len(record["order"]) + 1))
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), layout="constrained")
    rows = []
    for ci, c in enumerate(record["claims"]):
        cells = [key["typical", "chain", "unknown", "first %d" % n, c] for n in counts]
        dec = [percent(r["decided"]) for r in cells]
        right = [percent(r["precision"]) for r in cells]
        style_ = dict(color=INK, marker=CLAIM_MARKERS[ci], markerfacecolor="white", markersize=3.2, linewidth=0.8)
        axes[0].plot(counts, dec, label=c, **style_)
        axes[1].plot(counts, right, **style_)
        rows += [{"panel": p, "claim": c, "measures": n, "percent": v, "decided_fields": r["n_decided"]}
                 for p, vs in (("A", dec), ("B", right)) for n, v, r in zip(counts, vs, cells)]
    axes[1].axhline(99.0, color=INK, linestyle=":", linewidth=0.6)
    for ax, panel, label in zip(axes, "AB", ("Per cent decided at 0.99", "Per cent of those right")):
        ax.set_xticks([1, 8, 16, 24, 32])
        ax.set_xlabel("Measures, in the build-up order")
        ax.set_ylabel(label)
        letter(ax, panel)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncol=3)
    name = "one_body_coarse"
    return save(fig, outdir, name, CAPTIONS[name] % "{:,}".format(fields_of(record))) + [write_csv(outdir, name, rows)]


def fig_size(record: dict, outdir: str) -> List[str]:
    plt = style()
    key = keyed(record["rows"], "type", "prior", "size", "measures")
    sizes = record["sizes"]
    x = np.arange(len(sizes))
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), layout="constrained")
    rows = []
    for ax, (panel, stat, label) in zip(axes, (("A", "exact", "Per cent named exactly"),
                                              ("B", "answered", "Per cent named at 0.99"))):
        for k in VIEWS:
            ys = [percent(key["typical", "chain", s, k][stat]) for s in sizes]
            ax.plot(x, ys, color=INK, label=SET_LABEL[k], **SET_STYLE[k])
            rows += [{"panel": panel, "measures": k, "size": s, "stat": stat, "percent": y} for s, y in zip(sizes, ys)]
        ax.set_xticks(x)
        ax.set_xticklabels([s.replace(", ", ",\n") for s in sizes])
        ax.set_xlim(-0.4, len(sizes) - 0.6)
        ax.set_ylabel(label)
        letter(ax, panel)
    fig.legend(*axes[0].get_legend_handles_labels(), loc="outside lower center", ncol=4)
    name = "one_body_size"
    return save(fig, outdir, name, CAPTIONS[name] % "{:,}".format(fields_of(record))) + [write_csv(outdir, name, rows)]


def write_figures_md(outdir: str, written: List[str], path: str = RECORD) -> str:
    import matplotlib
    here = os.path.dirname(os.path.abspath(__file__))
    lines = ["# The one-body evaluation's figures", "",
             "Built with `python -m schwingcheck.one_body figures --outdir %s`." % os.path.relpath(outdir, ROOT), "",
             "- Record: `%s`, sha256 %s." % (os.path.relpath(path, ROOT), sha256(path))]
    for name in ("figures.py", "one_body.py"):
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


def draw_figures(record: dict, outdir: str, figures_md: bool = False, path: str = RECORD) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    written = fig_levels(record, outdir) + fig_buildup(record, outdir) + fig_coarse(record, outdir) + fig_size(record, outdir)
    if figures_md:
        written.append(write_figures_md(outdir, written, path))
    return written


# ---- the command ----------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.one_body")
    ap.add_argument("what", choices=("run", "table", "figures", "check"))
    ap.add_argument("--columns", type=int, default=COLUMNS)
    ap.add_argument("--processes", type=int, default=PROCESSES)
    ap.add_argument("--out", default=RECORD, help="where run writes the record, and where the rest read it")
    ap.add_argument("--outdir", default=OUTDIR)
    ap.add_argument("--table", choices=tuple(TABLES) + ("axis", "axis-seven"), default="sets")
    a = ap.parse_args(argv)
    if a.what == "run":
        CS.write(run(a.columns, a.processes), a.out)
    elif a.what == "table":
        print(tables(a.out)["one_body:%s" % a.table], end="")
    elif a.what == "figures":
        for p in draw_figures(load(a.out), a.outdir, figures_md=True, path=a.out):
            print(os.path.relpath(p, ROOT))
    else:
        problems = check(path=a.out)
        for p in problems:
            print(p)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
