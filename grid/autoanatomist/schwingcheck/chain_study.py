"""The chain of levels scored against step d's rule: the first rung of step e's methods (TODO.md,
item P, step e).

    python -m schwingcheck.chain_study run [--columns 100]      # chain.json, the table as printed, about 8 minutes
    python -m schwingcheck.chain_study axis [--columns 100]     # axis.json, the data axis, about 46 minutes on 3 processes
    python -m schwingcheck.chain_study speed                    # speed.json, the time to name one field, about 20 minutes
    python -m schwingcheck.chain_study pymc [--processes 3]     # pymc.json, both PyMC models against the exact answer
    python -m schwingcheck.chain_study table [--table main|claims|weights|axis|speed|pymc]   # a record's table
    python -m schwingcheck.chain_study check                    # whether the README's tables are the records'

The records are in records/chain-2026-10-28/.

Fields are drawn by the chain's own law (chain.draw_fields: each step misses a body with
probability 1/6, chain.step_law at chain.SKIP 0.2 cut at one missed, before the fit to the column)
from the generator's columns of the three types,
typical, six-lumbar and with a T13, every measure of the pool drawn for the same patients
(curve.draw_pool). Four rules name the middle body of each, on the same fields:

- consecutive: step d's rule, which takes the bodies as consecutive on a typical column;
- gaps: the chain of the typical column alone, its missed bodies summed out;
- chain: the whole chain, its missed bodies and its three types summed out;
- known gaps: the rule told each field's true gaps, on the typical column (TODO.md item 4c).

Each is scored as curve.py scores (curve.rates: the name right, within one level on curve.POSITION's
scale, the answers at 0.99 with their precision, each with its SE clustered by column), at 1, 3, 5
and 9 bodies, on the seven SPINEPS measures and on all 32. The first three are chain.py's exact sum
over the paths read along their shared beginnings (chain.prepare and chain.logev), which gives
chain.path_logev's answer (the tests hold the two within 1e-9) in a small part of its time, the
smaller the more bodies (`speed`). The chain's L6 and T13 columns are the generator's construction
(chain.extended_table), so on those columns it is scored against the truth it was built from.

A posterior of exactly 0 for the true body, from a rule with no name for it (the three
typical-column rules on a lone L6 or T13) or from a placement so confident that the true one
underflows (fields that hold an L6 or a T13 away from the middle), is floored at 1e-300 by
name_stats, so each such field counts 690.8 nats of log loss and the log loss says mostly how
often that happens.

The chain's type weights, 0.9, 0.05 and 0.05, are a stated choice (chain.WEIGHTS). `run` also
scores the chain at the weights the clinical reread found in the papers (WEIGHT_SETS, PR 21, the
counts as its second reader checked them in PR 26): six lumbar bodies in 11 of 443 skeletons
(Eisenstein 1977, 2 true L6 and 9 lumbarised S1, the reread's point prior) or in 2 of 443 (the true
L6 alone), and a T13 at 12 of 517, Duman 2026's rib-bearing vertebrae below the twelfth rib-bearer
on CT, which no paper tells apart from a T13. That last is a stand-in and a modelling choice, not a
bound: the reread found no count of a T13 in the papers and no bound for one. The typical type takes
the rest. The fields are the same, so the rows differ only by the prior.

The data axis (`axis`) builds the four rules on the build-up study's own tables (curve.WORLDS from
curve.WORLD_SEED, drawn in curve.make_arms' order, so the same 8, 4, 2 and 2 tables re-estimated
from 12, 50, 200 and 2,000 people), as if exact (nominal) and with each SD widened to a new
person's spread about a P-person table (predictive, curve.predictive_factor), the L6 and T13 built
from each table as from the printed one, and scores them on the same fields as `run`, so every row
of the axis is read against the table as printed on the same fields. Its SEs are curve.pooled_rates':
clustered by column with the tables held fixed, and crossed with the tables, on one degree of
freedom fewer than the tables.

The speed (`speed`) is the time to name the middle body of one field, single-threaded, with the rule
built beforehand as a service would build it once (chain.prepare, whose seconds are given beside),
at 1, 3, 5, 7 and 9 bodies, for the consecutive, gaps and chain rules (the rule told the true gaps
is no rule a service could run, and is not timed) and each measure set alone: the median and the
largest over 30 single fields, and per field in a batch of 128, the median and the largest of five
calls after one that warms them, as curve.time_engine takes them. chain.path_logev, which builds its
blocks inside every call, is timed beside the chain at every width on fewer calls
(REFERENCE_COUNTS). Numba's first compile in a process loads scipy's own BLAS, so `speed` compiles
the loops before it sets the thread limit (load_loops); a loop compiled again for another array
layout inside the limit falls in time_engine's warm-up call, and every pool's threads are recorded
inside the limit. `run` and `axis` compile them the same way first, and record the pools too, so
`run`'s prepare_seconds hold no compile (the records of commit 9d94314 were made before they did:
chain.json says single_threaded, and its first prepare_seconds hold the compile; neither table reads
them). Each measure set is timed as a rule cut to its measures (cut), the table, errors, powers
and fields taken to those measures alone, as a service that reads only the seven would build it,
so its loops run over seven measures and not over all 32 with the rest masked out.

The two PyMC models of chain_pymc.py (`pymc`) are set against the exact answer on `run`'s own
fields at three bodies, the first field of each of the first six columns of each type, so that the
exact posterior each is held to is `run`'s: model (a), the offsets sampled with the chain summed out
by pymc-extras' forward algorithm, and model (b), the chain and the offsets summed out exactly in the
model's own marginalisation, each sampled by NUTS on a rule cut to the seven and to all 32, four
chains of 500 draws after 500 tuning steps, on each field alone, as a service would name a field:
in a trial before the record, the six typical fields sampled together in one model took model (a)
with all 32 measures to trees of depth 8, 255 leapfrog steps a draw, where one field alone takes 2
to 7, and the build-up study found one field of twenty sampled together wrong with an R-hat of 1.00
(curve's NUTS table); model (b), and model (a) on the seven, took little more together than alone.
Each field's posterior over the middle body's name is the draws' average of p(name | field, size),
with a Monte Carlo error from ten batches of each chain's draws. A field is within where every name
is within five errors plus 0.001 (PYMC_WITHIN), the bound the naming model's NUTS test puts on every
place, and passes that test where, besides, every name the exact posterior puts above 0.05 is within
five errors with no 0.001 beside them and the largest R-hat is below 1.02 (PYMC_RHAT), the test's
other two checks; beside them the largest R-hat, NUTS's leapfrog steps a draw, the divergences and
NUTS's seconds a field. The three types run in a pool of processes, each holding its thread pools
at one thread once load_models has loaded them, and the record lists the pools.

The README's tables are drawn from the records alone: their widths, the stated weights and the
numbers of people come from the record, not from this module's constants, and `check` also holds
the records to one another, `run`'s, `axis`'s and `speed`'s fields drawn from the same columns and
seeds (consistent).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import time
from typing import Dict, List, Tuple

import numpy as np

from . import chain as CH
from . import curve as CV
from . import measures as MS
from . import rule as R
from . import score as S

WIDTHS = (1, 3, 5, 9)
SPEED_WIDTHS = (1, 3, 5, 7, 9)
ARMS = ("consecutive", "gaps", "chain", "known gaps")
CHAIN_ARMS = ARMS[:3]
SUBSETS = ("seven", "all")
SEED, EXTRA_SEED, FIELD_SEED, PER_COLUMN = 401, 501, 601, 2
RULES = ("nominal", "predictive")
SIX_LUMBAR = {"high": 11 / 443, "low": 2 / 443}     # Eisenstein 1977 p. 177: L6 or lumbarised S1, true L6 alone
T13_STAND_IN = 12 / 517                            # Duman 2026 Table 5: a rib below the twelfth rib-bearer
WEIGHT_SETS = {"papers, %s" % k: (1.0 - v - T13_STAND_IN, v, T13_STAND_IN) for k, v in SIX_LUMBAR.items()}
PROCESSES = 4
SPEED_COUNTS = {"calls": 30, "batch": 128, "batches": 5}
REFERENCE_COUNTS = {"calls": 3, "batch": 16, "batches": 2}
PYMC_MODELS = ("enumerated", "sampled")
PYMC = {"widths": (3,), "fields": 6, "draws": 500, "tune": 500, "chains": 4, "batches": 10, "seed": 701}
PYMC_WITHIN = (5.0, 1e-3)      # every name within five Monte Carlo errors plus 0.001 of the exact posterior,
                               # the bound the naming model's NUTS test puts on every place
PYMC_RHAT = 1.02               # and the R-hat that test holds every variable below
QUICK = {"columns": 3, "widths": (1, 3), "worlds": {12: 2, 2000: 2}, "speed_widths": (1, 3),
         "speed": {"calls": 2, "batch": 4, "batches": 1}, "reference": {"calls": 1, "batch": 2, "batches": 1},
         "pymc": {"widths": (3,), "fields": 2, "draws": 100, "tune": 100, "chains": 2, "batches": 5, "seed": 701}}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD_DIR = os.path.join(ROOT, "records", "chain-2026-10-28")
RECORDS = {"main": os.path.join(RECORD_DIR, "chain.json"), "axis": os.path.join(RECORD_DIR, "axis.json"),
           "speed": os.path.join(RECORD_DIR, "speed.json"), "pymc": os.path.join(RECORD_DIR, "pymc.json")}
README = os.path.join(ROOT, "schwingcheck", "README.md")
NAME_POSITION = np.array([CV.POSITION[n] for n in CH.NAMES])


def name_stats(post: np.ndarray, truth: np.ndarray) -> Dict[str, np.ndarray]:
    """What a posterior over NAMES did on each field, in curve.field_stats' terms."""
    said_at, truth_at = NAME_POSITION[post.argmax(1)], NAME_POSITION[truth]
    size, _ = R.credible_sets(post, CV.CLAIM)
    return {"hit": said_at == truth_at, "within": np.abs(said_at - truth_at) <= 1.0, "top": post.max(1),
            "logp": np.log(np.maximum(post[np.arange(len(truth)), truth], 1e-300)), "size": size.astype(np.int16)}


def chains(n_bodies: int) -> Dict[str, CH.Chain]:
    return {"consecutive": CH.build(("typical",), (1.0,), (1.0,), n_bodies),
            "gaps": CH.build(("typical",), (1.0,), CH.step_law(), n_bodies),
            "chain": CH.build(CH.TYPES, None, CH.step_law(), n_bodies)}


def setting():
    """The pool, its subsets, its table, errors and powers, and the size's nodes."""
    pool = MS.pool()
    keys = [m.key for m in pool]
    subsets = {"seven": [keys.index(k) for k in MS.SPINEPS_7], "all": list(range(len(pool)))}
    mu, sd = MS.arrays(pool)
    return pool, subsets, mu, sd, MS.errors(pool), MS.powers(pool), R.trapezoid(R.SYNTH["scale_sd"])


def draw_all(pool, n_columns: int, widths) -> Dict[Tuple[str, int], tuple]:
    """The scored fields of every type and width, (X, names, offsets, col), from the seeds above:
    a type's columns from SEED and EXTRA_SEED plus its index, a width's fields from FIELD_SEED plus
    ten times the type's index plus the width."""
    out = {}
    for ti, kind in enumerate(CH.TYPES):
        cols = CV.draw_pool(pool, kind, SEED + ti, EXTRA_SEED + ti, n_columns)
        for B in widths:
            out[kind, B] = CH.draw_fields(cols, CH.step_law(), B, PER_COLUMN, FIELD_SEED + 10 * ti + B)
    return out


def prepared(n_bodies: int, mu_e, sd_e, subsets, noise, power, nodes) -> Tuple[Dict[str, CH.PathRule], Dict[str, float]]:
    """The three chain rules at this width, each built once, with the seconds each took."""
    rules, seconds = {}, {}
    for arm, ch in chains(n_bodies).items():
        t0 = time.perf_counter()
        rules[arm] = CH.prepare(CH.paths_of(ch), mu_e, sd_e, subsets, noise, power, nodes)
        seconds[arm] = time.perf_counter() - t0
    return rules, seconds


def name_middle(rule: CH.PathRule, X: np.ndarray, t: int) -> Dict[str, np.ndarray]:
    """Body t's posterior over NAMES under each of the rule's subsets."""
    return {k: CH.body_posterior(CH.posterior(v, rule.log_prior), rule.names, t) for k, v in CH.logev(rule, X).items()}


def chain_stats(rule: CH.PathRule, drawn, subsets, power) -> Dict[str, dict]:
    """One chain rule's stats on one type's fields at one width, by subset."""
    X, names, _, _ = drawn
    t = S.target_offset(X.shape[2])
    out = {}
    for k, p in name_middle(rule, X, t).items():
        out[k] = name_stats(p, names[:, t])
        out[k]["floored"] = CV.floored_in(X, subsets[k], power)
    return out


def score_fields(rules, drawn, mu, sd, subsets, noise, power, nodes) -> List[dict]:
    """The four rules on one type's fields at one width, each subset's stats and the seconds a field."""
    X, names, offsets, col = drawn
    B = X.shape[2]
    t = S.target_offset(B)
    truth = names[:, t]
    out = []
    for arm in ARMS:
        t0 = time.perf_counter()
        if arm == "known gaps":
            post = CH.known_pattern_posterior(X, offsets, mu, sd, subsets, noise, power, nodes, t)
        else:
            post = name_middle(rules[arm], X, t)
        seconds = (time.perf_counter() - t0) / len(X)
        for k, p in post.items():
            stats = name_stats(p, truth)
            stats["floored"] = CV.floored_in(X, subsets[k], power)
            out.append({"arm": arm, "subset": k, "seconds": seconds, "stats": stats, "col": col})
    return out


def run(n_columns: int, widths=WIDTHS) -> dict:
    from threadpoolctl import threadpool_limits
    made_by = CV.code_state()
    pool, subsets, mu, sd, noise, power, nodes = setting()
    mu_e, sd_e = CH.extended_table(mu, sd)
    drawn = draw_all(pool, n_columns, widths)
    load_loops(subsets, mu_e, sd_e, noise, power, nodes, drawn["typical", widths[0]][0])
    rows: List[dict] = []
    weight_rows: List[dict] = []
    setup = {}
    with threadpool_limits(1):
        for B in widths:
            rules, seconds = prepared(B, mu_e, sd_e, subsets, noise, power, nodes)
            setup[str(B)] = seconds
            for kind in CH.TYPES:
                for r in score_fields(rules, drawn[kind, B], mu, sd, subsets, noise, power, nodes):
                    rows.append({"type": kind, "bodies": B, "arm": r["arm"], "subset": r["subset"],
                                 "seconds_per_field_both_subsets": r["seconds"], **CV.rates(r["stats"], r["col"])})
            for name, w in WEIGHT_SETS.items():
                rule = CH.prepare(CH.paths_of(CH.build(CH.TYPES, w, CH.step_law(), B)), mu_e, sd_e, subsets, noise, power, nodes)
                for kind in CH.TYPES:
                    for k, st in chain_stats(rule, drawn[kind, B], subsets, power).items():
                        weight_rows.append({"weights": name, "type": kind, "bodies": B, "subset": k,
                                            **CV.rates(st, drawn[kind, B][3])})
        threads = CV.pools()
    return {"command": "python -m schwingcheck.chain_study run --columns %d" % n_columns, "columns_per_type": n_columns,
            "fields_per_column": PER_COLUMN, "seeds": [SEED, EXTRA_SEED, FIELD_SEED], "skip": CH.SKIP,
            "max_step": CH.MAX_STEP, "weights": CH.WEIGHTS, "widths": list(widths),
            "weight_sets": {k: dict(zip(CH.TYPES, v)) for k, v in WEIGHT_SETS.items()},
            "prepare_seconds": setup, "threads": threads, "machine": CV.machine(), "versions": CV.versions(),
            **made(made_by), "rows": rows, "weight_rows": weight_rows}


def made(made_by: dict) -> dict:
    """The code and table a record was made by, taken before any work (curve.code_state), and what
    of them changed by the time the record was built (curve.changed_during), empty when nothing."""
    return {"made_by": made_by, "changed_during_run": CV.changed_during(made_by, CV.code_state())}


# ---- the data axis --------------------------------------------------------------------------

def axis_tables(pool, worlds) -> List[Tuple[int, int, np.ndarray, np.ndarray]]:
    """The build-up study's tables, (people, index, mu, sd), drawn as curve.make_arms draws them:
    one generator from curve.WORLD_SEED, the people in WORLDS' order, the tables of each in turn."""
    rng = np.random.default_rng(CV.WORLD_SEED)
    out = []
    for people, n_tables in worlds.items():
        for w in range(n_tables):
            emu, esd = CV.estimated_table(pool, people, rng)
            out.append((people, w, emu, esd))
    return out


_AXIS: dict = {}


def axis_job(job: Tuple[int, str, int]) -> Tuple[int, str, int, List[dict], List[dict]]:
    """One table, one rule and one width: the four rules on every type's fields, and every thread
    pool as it stood inside the limit once they had run."""
    from threadpoolctl import threadpool_limits
    i, rule, B = job
    a = _AXIS
    people, w, emu, esd = a["tables"][i]
    esd = esd * (CV.predictive_factor(people) if rule == "predictive" else 1.0)
    mu_e, sd_e = CH.extended_table(emu, esd)
    out = []
    with threadpool_limits(1):
        rules, _ = prepared(B, mu_e, sd_e, a["subsets"], a["noise"], a["power"], a["nodes"])
        for kind in CH.TYPES:
            for r in score_fields(rules, a["drawn"][kind, B], emu, esd, a["subsets"], a["noise"], a["power"], a["nodes"]):
                out.append({"type": kind, "arm": r["arm"], "subset": r["subset"], "stats": r["stats"], "col": r["col"]})
        threads = CV.pools()
    return i, rule, B, out, threads


def axis(n_columns: int, widths=WIDTHS, worlds=None, processes: int = PROCESSES, log=print) -> dict:
    global _AXIS
    made_by = CV.code_state()
    worlds = dict(CV.WORLDS if worlds is None else worlds)
    pool, subsets, mu, sd, noise, power, nodes = setting()
    tables = axis_tables(pool, worlds)
    _AXIS = {"tables": tables, "drawn": draw_all(pool, n_columns, widths), "subsets": subsets, "noise": noise,
             "power": power, "nodes": nodes}
    mu_e, sd_e = CH.extended_table(mu, sd)
    load_loops(subsets, mu_e, sd_e, noise, power, nodes, _AXIS["drawn"]["typical", widths[0]][0])
    jobs = sorted(((i, rule, B) for i in range(len(tables)) for rule in RULES for B in widths), key=lambda j: -j[2])
    t0 = time.time()
    if processes > 1:
        with multiprocessing.get_context("fork").Pool(processes) as p:
            results = list(_logged(p.imap_unordered(axis_job, jobs), len(jobs), t0, log))
    else:
        results = list(_logged(map(axis_job, jobs), len(jobs), t0, log))
    rows = axis_rows(results, tables, worlds)
    threads = sorted({json.dumps(r[4], sort_keys=True) for r in results})
    return {"command": "python -m schwingcheck.chain_study axis --columns %d --processes %d" % (n_columns, processes),
            "columns_per_type": n_columns,
            "fields_per_column": PER_COLUMN, "seeds": [SEED, EXTRA_SEED, FIELD_SEED], "world_seed": CV.WORLD_SEED,
            "worlds": {str(k): v for k, v in worlds.items()}, "widths": list(widths), "rules": list(RULES),
            "threads": [json.loads(t) for t in threads], "machine": CV.machine(), "versions": CV.versions(), **made(made_by), "rows": rows}


def axis_rows(results, tables, worlds) -> List[dict]:
    """The axis's rows from its jobs' results, which the pool of processes hands back in the order
    they finish: sorted by table, rule and width first, so that the fields are pooled, and the log
    loss and the predicted error summed over them, in one order whatever the order of finishing,
    and the record is made again to the bit."""
    parts: Dict[tuple, dict] = {}
    for i, rule, B, out, _ in sorted(results, key=lambda r: (r[0], r[1], r[2])):
        people, w = tables[i][0], tables[i][1]
        for r in out:
            g = parts.setdefault((people, rule, r["type"], B, r["arm"]), {"col": [], "world": [], "stats": []})
            g["col"].append(r["col"])
            g["world"].append(w)
            g["stats"].append({r["subset"]: r["stats"]})
    rows = []
    for (people, rule, kind, B, arm), g in sorted(parts.items()):
        for sub in SUBSETS:
            have = [k for k, st in enumerate(g["stats"]) if sub in st]
            sel = {"col": [g["col"][k] for k in have], "world": [g["world"][k] for k in have],
                   "stats": [g["stats"][k] for k in have]}
            rows.append({"people": people, "rule": rule, "tables": worlds[people], "type": kind, "bodies": B, "arm": arm,
                         "subset": sub, **CV.pooled_rates(sel, sub)})
    return rows


def _logged(results, n: int, t0: float, log):
    for i, r in enumerate(results):
        if (i + 1) % 8 == 0 or i + 1 == n:
            log("axis: %d of %d jobs in %.0f s" % (i + 1, n, time.time() - t0))
        yield r


# ---- the speed ------------------------------------------------------------------------------

def load_loops(subsets, mu_e, sd_e, noise, power, nodes, X: np.ndarray) -> None:
    """Compile chain.prepare's and chain.logev's loops now, outside the thread limit: Numba's first
    compile loads scipy's own BLAS, and threadpool_limits holds only the libraries loaded when it is
    entered, so a limit entered first would leave that one at every thread (curve.load_compiled, the
    build-up study's same step). Numba compiles a loop once for each layout of the arrays it is
    given, and a rule of one subset hands logev's walk a contiguous row where a rule of two hands it
    a strided one, so the loops are compiled on both, each on one field and on two with a value not
    read, the layouts `speed` times. The two fields are copies of X's first, so one field is enough,
and the chain is as wide as X."""
    part = np.array(X[[0, 0]])
    part[1, 0, 0] = np.nan
    paths = CH.paths_of(chains(X.shape[2])["chain"])
    for name, idx in subsets.items():
        rule = CH.prepare(paths, *cut(name, idx, mu_e, sd_e, noise, power), nodes)
        CH.logev(rule, part[:1, idx, :])
        CH.logev(rule, part[:, idx, :])
    CH.logev(CH.prepare(paths, mu_e, sd_e, subsets, noise, power, nodes), part)


def speed(n_columns: int = 100, widths=SPEED_WIDTHS, counts=None, reference=None, log=print) -> dict:
    """The time to name the middle body of one field, single-threaded (the module's docstring), on
    the typical type's fields of `run`'s seeds."""
    from threadpoolctl import threadpool_limits
    made_by = CV.code_state()
    counts = dict(SPEED_COUNTS if counts is None else counts)
    reference = dict(REFERENCE_COUNTS if reference is None else reference)
    pool, subsets, mu, sd, noise, power, nodes = setting()
    mu_e, sd_e = CH.extended_table(mu, sd)
    drawn = draw_all(pool, n_columns, widths)
    load_loops(subsets, mu_e, sd_e, noise, power, nodes, drawn["typical", widths[0]][0])
    rows = []
    with threadpool_limits(1):
        for B in widths:
            t = S.target_offset(B)
            for sub in SUBSETS:
                table, X = cut(sub, subsets[sub], mu_e, sd_e, noise, power), drawn["typical", B][0][:, subsets[sub], :]
                for arm, ch in chains(B).items():
                    pa = CH.paths_of(ch)
                    t0 = time.perf_counter()
                    rule = CH.prepare(pa, *table, nodes)
                    setup = time.perf_counter() - t0
                    times = CV.time_engine(lambda x: name_middle(rule, x, t), X, counts["calls"], counts["batch"], counts["batches"])
                    rows.append({"engine": "prepared", "arm": arm, "subset": sub, "measures": X.shape[1], "bodies": B,
                                 "paths": len(pa), "prepare_s": setup, **times})
                    log("speed: %s, %s, %d bodies: %.2f ms a field alone, %.2f ms in a batch"
                        % (arm, sub, B, times["median_ms"], times["batch_ms"]))
                ch = chains(B)["chain"]
                pa = CH.paths_of(ch)

                def ref(x, table=table):
                    ev = CH.path_logev(x, pa, ch, table[0], table[1], table[2], table[3], table[4], nodes)
                    return {k: CH.body_posterior(CH.posterior(v, pa.log_prior), pa.names, t) for k, v in ev.items()}
                times = CV.time_engine(ref, X, reference["calls"], reference["batch"], reference["batches"])
                rows.append({"engine": "path_logev", "arm": "chain", "subset": sub, "measures": X.shape[1], "bodies": B,
                             "paths": len(pa), "prepare_s": 0.0, **times})
                log("speed: path_logev, %s, %d bodies: %.0f ms a field alone, %.0f ms in a batch"
                    % (sub, B, times["median_ms"], times["batch_ms"]))
        threads = CV.pools()
    return {"command": "python -m schwingcheck.chain_study speed", "columns_per_type": n_columns,
            "fields_per_column": PER_COLUMN, "seeds": [SEED, EXTRA_SEED, FIELD_SEED], "cut": True,
            "counts": counts, "reference_counts": reference, "widths": list(widths), "threads": threads,
            "machine": CV.machine(), "versions": CV.versions(), **made(made_by), "rows": rows}


def cut(name: str, idx, mu_e: np.ndarray, sd_e: np.ndarray, noise: np.ndarray, power: np.ndarray):
    """A rule's inputs cut to these measures: the extended table, one subset of this name holding
    all of them, their errors and their powers, so that a rule built from them runs its loops over
    these measures alone, as a service that reads only these would build it."""
    idx = list(idx)
    return (mu_e[idx], sd_e[idx], {name: list(range(len(idx)))}, np.asarray(noise, float)[idx],
            np.asarray(power, float)[idx])


# ---- the PyMC models against the exact answer -------------------------------------------------

_PYMC: dict = {}


def pymc_fields(drawn, kind: str, B: int, n: int):
    """The fields the PyMC models are run on: the first field of each of the first n columns of
    `run`'s fields of this type and width, so that their exact posteriors are `run`'s."""
    X, names, _, col = drawn[kind, B]
    pick = np.arange(n) * PER_COLUMN
    return X[pick], names[pick], col[pick]


def load_models(a: dict, X: np.ndarray, ch: CH.Chain) -> None:
    """Load every library the job's work loads, outside the thread limit, as load_loops does for
    the chain's loops: Numba's first compile loads scipy's own BLAS, and PyMC and PyTensor load
    theirs as they import and compile, so both models are sampled for a few draws on one field of
    the seven first; threadpool_limits then holds them all."""
    import pymc as pm
    from . import chain_pymc as CP
    load_loops(a["subsets"], a["mu_e"], a["sd_e"], a["noise"], a["power"], a["nodes"], X)
    mu_s, sd_s, _, noise_s, power_s = cut("seven", a["subsets"]["seven"], a["mu_e"], a["sd_e"], a["noise"], a["power"])
    for build in (CP.enumerated, CP.sampled):
        with build(X[:1, a["subsets"]["seven"], :], ch, mu_s, sd_s, noise_s, power_s):
            pm.sample(draws=2, tune=2, chains=1, cores=1, random_seed=0, progressbar=False, compute_convergence_checks=False)


def pymc_job(job: Tuple[str, int]) -> Tuple[List[dict], List[dict]]:
    """pymc_type on one type and width, with PyMC's notes on each of its many samplings held back."""
    import logging
    pymc_log = logging.getLogger("pymc")
    level = pymc_log.level
    pymc_log.setLevel(logging.ERROR)
    try:
        return pymc_type(_PYMC, *job)
    finally:
        pymc_log.setLevel(level)


def pymc_type(a: dict, kind: str, B: int) -> Tuple[List[dict], List[dict]]:
    """Both PyMC models on one type's fields at one width, each measure set cut to its measures:
    each field's posterior of the middle body's name against the exact one; and every thread pool
    as it stood inside the limit once they had run."""
    import warnings
    from threadpoolctl import threadpool_limits
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        X, names, col = pymc_fields(a["drawn"], kind, B, a["sampling"]["fields"])
        ch = chains(B)["chain"]
        pa = CH.paths_of(ch)
        t = S.target_offset(B)
        load_models(a, X, ch)
        out = []
        with threadpool_limits(1):
            for sub in a["which"]:
                table = cut(sub, a["subsets"][sub], a["mu_e"], a["sd_e"], a["noise"], a["power"])
                Xs = X[:, a["subsets"][sub], :]
                exact = name_middle(CH.prepare(pa, *table, a["nodes"]), Xs, t)[sub]
                for model in PYMC_MODELS:
                    r = pymc_run(model, Xs, ch, pa, table, t, exact, a["sampling"])
                    out.append({"type": kind, "bodies": B, "subset": sub, "model": model, "columns": col.tolist(),
                                "truth": [CH.NAMES[n] for n in names[:, t]], **r})
            threads = CV.pools()
    return out, threads


def pymc_run(model: str, X: np.ndarray, ch: CH.Chain, pa: CH.Paths, table, t: int, exact: np.ndarray,
             sampling: dict) -> dict:
    """One model sampled by NUTS on each field of X alone, as a service would name a field: the
    seconds to build it and those of NUTS's own loop, each field's largest gap from the exact
    posterior, its Monte Carlo error there and its largest gap in Monte Carlo errors at names the
    exact posterior puts above 0.05, whether every name is within PYMC_WITHIN, whether the model's
    name is the exact one's, the largest R-hat of the field's variables, NUTS's mean leapfrog
    steps a draw and the divergences."""
    fields = [pymc_field(model, X[i:i + 1], ch, pa, table, t, sampling) for i in range(len(X))]
    post, se = np.concatenate([f["post"] for f in fields]), np.concatenate([f["se"] for f in fields])
    gap = np.abs(post - exact)
    k, tol = PYMC_WITHIN
    big = exact > 0.05
    in_errors = np.where(big, gap / np.maximum(se, 1e-12), 0.0).max(1)
    worst = gap.argmax(1)
    within = np.all(gap <= k * se + tol, axis=1)
    return {"build_s": float(np.mean([f["build_s"] for f in fields])),
            "sample_s": float(np.mean([f["sample_s"] for f in fields])),
            "gap": gap.max(1).tolist(), "gap_mcse": se[np.arange(len(X)), worst].tolist(),
            "gap_name": [CH.NAMES[w] for w in worst], "gap_in_errors": in_errors.tolist(),
            "within": bool(within.all()), "fields_within": int(within.sum()), "within_each": within.tolist(),
            "same_name": (post.argmax(1) == exact.argmax(1)).tolist(), "exact_top": exact.max(1).tolist(),
            "model_top": post.max(1).tolist(), "rhat": [f["rhat"] for f in fields],
            "steps": [f["steps"] for f in fields], "divergences": int(sum(f["divergences"] for f in fields))}


def pymc_field(model: str, X: np.ndarray, ch: CH.Chain, pa: CH.Paths, table, t: int, sampling: dict) -> dict:
    """One field's model built and sampled: its posterior over the middle body's names with the
    Monte Carlo error of each, from the batches of every chain's draws, and its diagnostics."""
    import arviz as az
    import pymc as pm
    from . import chain_pymc as CP
    mu_s, sd_s, _, noise_s, power_s = table
    t0 = time.perf_counter()
    m = (CP.enumerated if model == "enumerated" else CP.sampled)(X, ch, mu_s, sd_s, noise_s, power_s)
    t1 = time.perf_counter()
    with m:
        idata = pm.sample(draws=sampling["draws"], tune=sampling["tune"], chains=sampling["chains"], cores=1,
                          random_seed=sampling["seed"], progressbar=False, compute_convergence_checks=False)
    if model == "enumerated":
        post, batches = CP.body_posterior_enumerated(idata, X, pa, mu_s, sd_s, noise_s, power_s, t,
                                                     n_batches=sampling["batches"])
    else:
        post, batches = CP.body_posterior_sampled(idata, X, ch, mu_s, sd_s, noise_s, power_s, t,
                                                  n_batches=sampling["batches"])
    rh = az.rhat(idata, var_names=["log_s"] + (["z"] if model == "sampled" else []))
    rhat = float(np.max([np.max(np.asarray(v.values, float)) for v in rh.data_vars.values()]))
    stats = idata.sample_stats
    return {"post": post, "se": CP.mcse(batches), "build_s": t1 - t0, "rhat": rhat,
            "sample_s": float(idata.posterior.attrs.get("sampling_time", float("nan"))),
            "steps": float(np.mean(stats["n_steps"].values)),
            "divergences": int(np.asarray(stats["diverging"].values).sum())}


def pymc_compare(n_columns: int = 100, sampling=None, processes: int = 3, subsets=SUBSETS, log=print) -> dict:
    """Both PyMC models against chain.py's exact answer, type by type in a pool of processes (the
    module's docstring), each process's thread pools held at one thread once load_models has
    loaded them, and recorded so (threads)."""
    global _PYMC
    made_by = CV.code_state()
    sampling = dict(PYMC if sampling is None else sampling)
    pool, every, mu, sd, noise, power, nodes = setting()
    mu_e, sd_e = CH.extended_table(mu, sd)
    _PYMC = {"drawn": draw_all(pool, n_columns, sampling["widths"]), "subsets": every, "which": list(subsets),
             "mu_e": mu_e, "sd_e": sd_e, "noise": noise, "power": power, "nodes": nodes, "sampling": sampling}
    jobs = [(kind, B) for B in sampling["widths"] for kind in CH.TYPES]
    t0 = time.time()
    if processes > 1:
        with multiprocessing.get_context("fork").Pool(min(processes, len(jobs))) as p:
            results = p.map(pymc_job, jobs)
    else:
        results = list(map(pymc_job, jobs))
    log("pymc: %d jobs in %.0f s" % (len(jobs), time.time() - t0))
    rows = [r for out, _ in results for r in out]
    threads = [{"type": kind, "bodies": B, "pools": pools} for (kind, B), (_, pools) in zip(jobs, results)]
    return {"command": "python -m schwingcheck.chain_study pymc --processes %d" % processes, "columns_per_type": n_columns,
            "fields_per_column": PER_COLUMN, "seeds": [SEED, EXTRA_SEED, FIELD_SEED], "subsets": list(subsets),
            "sampling": {k: list(v) if isinstance(v, tuple) else v for k, v in sampling.items()},
            "within": list(PYMC_WITHIN), "rhat_below": PYMC_RHAT, "threads": threads, "machine": CV.machine(), "versions": pymc_versions(),
            **made(made_by), "rows": rows}


def pymc_versions() -> dict:
    """curve.versions() and pymc-extras', whose marginalisation both models are built on."""
    from importlib import metadata
    out = CV.versions()
    try:
        out["pymc-extras"] = metadata.version("pymc-extras")
    except metadata.PackageNotFoundError:
        out["pymc-extras"] = "not installed"
    return out


# ---- the tables -----------------------------------------------------------------------------

def pct(x: float, digits: int = 1) -> str:
    return "-" if x is None or not np.isfinite(x) else "%.*f" % (digits, 100 * x)


def main_table(record: dict) -> str:
    out = ["| Column | Bodies | Measures | " + " | ".join(ARMS) + " |", "|---|---:|---|" + "---:|" * len(ARMS)]
    key = {(r["type"], r["bodies"], r["subset"], r["arm"]): r for r in record["rows"]}
    for kind in CH.TYPES:
        for B in record["widths"]:
            for k in SUBSETS:
                cells = ["%s (%s)" % (pct(key[kind, B, k, a]["exact"]), pct(key[kind, B, k, a]["exact_se"])) for a in ARMS]
                out.append("| %s | %d | %s | %s |" % (kind.replace("_", "-"), B, k, " | ".join(cells)))
    return "\n".join(out) + "\n"


def claims_table(record: dict) -> str:
    """The answers at 0.99: the share answered and right of those answered, each rule, all 32, at
    every width of the record."""
    out = ["| Column | Bodies | " + " | ".join("%s: answered / right" % a for a in ARMS) + " |",
           "|---|---:|" + "---:|" * len(ARMS)]
    key = {(r["type"], r["bodies"], r["subset"], r["arm"]): r for r in record["rows"]}
    for kind in CH.TYPES:
        for B in record["widths"]:
            cells = []
            for a in ARMS:
                r = key[kind, B, "all", a]
                cells.append("%s / %s (%d of %d)" % (pct(r["answered"]), pct(r["precision"], 2),
                                                    r["n_answered"] - r["errors"], r["n_answered"]))
            out.append("| %s | %d | %s |" % (kind.replace("_", "-"), B, " | ".join(cells)))
    return "\n".join(out) + "\n"


def weights_table(record: dict, bodies=(1, 5, 9)) -> str:
    """The chain at its stated type weights and at the clinical reread's (WEIGHT_SETS): each type's
    share named exactly (SE) and the precision of the answers at 0.99, on the same fields; one body
    among the widths, since a lone body is where the prior counts most. The weights are the
    record's, and the widths those of `bodies` the record holds."""
    stated = {(r["type"], r["bodies"], r["subset"]): r for r in record["rows"] if r["arm"] == "chain"}
    other = {(r["weights"], r["type"], r["bodies"], r["subset"]): r for r in record["weight_rows"]}
    sets = [("stated", record["weights"])] + list(record["weight_sets"].items())
    head = ["Bodies", "Measures", "Weights", "Six-lumbar, t13"] + \
           ["%s: exact / right at 0.99" % k.replace("_", "-") for k in CH.TYPES]
    out = ["| " + " | ".join(head) + " |", "|---:|---|---|---|" + "---:|" * len(CH.TYPES)]
    for B in [b for b in bodies if b in record["widths"]]:
        for sub in SUBSETS[::-1]:
            for name, w in sets:
                rs = [stated[k, B, sub] if name == "stated" else other[name, k, B, sub] for k in CH.TYPES]
                cells = ["%s (%s) / %s" % (pct(r["exact"]), pct(r["exact_se"]), pct(r["precision"], 2)) for r in rs]
                out.append("| %d | %s | %s | %.4g, %.4g | %s |" % (B, sub, name, w["six_lumbar"], w["t13"], " | ".join(cells)))
    return "\n".join(out) + "\n"


def axis_table(record: dict, main: dict, bodies: int = 5, subset: str = "all") -> str:
    """The data axis at one width and measure set: each type's share named exactly by the chain,
    with both SEs and the difference from the table as printed on the same fields, and the
    chain's precision at 0.99 over the three types, against the consecutive rule's typical share."""
    printed = {(r["type"], r["bodies"], r["subset"], r["arm"]): r for r in main["rows"]}
    rows = {(r["people"], r["rule"], r["type"], r["bodies"], r["subset"], r["arm"]): r for r in record["rows"]}
    head = ["People", "Rule", "Tables"] + ["Chain, %s" % k.replace("_", "-") for k in CH.TYPES] + \
           ["Chain, right at 0.99 (typical / six-lumbar / t13)", "Consecutive, typical"]
    out = ["| " + " | ".join(head) + " |", "|---:|---|---:|" + "---:|" * (len(head) - 3)]

    def cell(r, ref=None, two=True):
        se = "%s / %s" % (pct(r["exact_se"]), pct(r.get("exact_se_tables", float("nan")))) if two else pct(r["exact_se"])
        diff = "" if ref is None else ", %+.1f" % (100 * (r["exact"] - ref["exact"]))
        return "%s (%s)%s" % (pct(r["exact"]), se, diff)

    p = [printed[k, bodies, subset, "chain"] for k in CH.TYPES]
    out.append("| as printed | - | 1 | " + " | ".join(cell(r, two=False) for r in p) + " | " +
               " / ".join(pct(r["precision"], 2) for r in p) + " | " +
               cell(printed["typical", bodies, subset, "consecutive"], two=False) + " |")
    worlds = {int(k): v for k, v in record["worlds"].items()}
    for people in sorted(worlds):
        for rule in record["rules"]:
            c = [rows[people, rule, k, bodies, subset, "chain"] for k in CH.TYPES]
            cells = [cell(r, ref) for r, ref in zip(c, p)]
            prec = " / ".join(pct(r["precision"], 2) for r in c)
            cons = cell(rows[people, rule, "typical", bodies, subset, "consecutive"], printed["typical", bodies, subset, "consecutive"])
            out.append("| {:,} | {} | {} | {} | {} | {} |".format(people, rule, worlds[people], " | ".join(cells), prec, cons))
    return "\n".join(out) + "\n"


def speed_table(record: dict) -> str:
    """Milliseconds to name one field, alone (median / largest) and in a batch, all 32 and seven."""
    key = {(r["engine"], r["arm"], r["subset"], r["bodies"]): r for r in record["rows"]}
    head = ["Bodies", "Paths, chain"] + ["%s, %s" % (a, k) for a in CHAIN_ARMS for k in ("all 32", "seven")] + \
           ["chain, all 32, path_logev"]
    out = ["| " + " | ".join(head) + " |", "|---:|---:|" + "---:|" * (len(head) - 2)]
    for B in record["widths"]:
        cells = []
        for a in CHAIN_ARMS:
            for k in ("all", "seven"):
                r = key["prepared", a, k, B]
                cells.append("%s / %s; %s" % (_ms(r["median_ms"]), _ms(r["max_ms"]), _ms(r["batch_ms"])))
        r = key["path_logev", "chain", "all", B]
        cells.append("%s / %s; %s" % (_ms(r["median_ms"]), _ms(r["max_ms"]), _ms(r["batch_ms"])))
        out.append("| %d | %s | %s |" % (B, "{:,}".format(key["prepared", "chain", "all", B]["paths"]), " | ".join(cells)))
    return "\n".join(out) + "\n"


def pymc_table(record: dict) -> str:
    """Both PyMC models against the exact answer: for each type, measure set and model, the fields,
    those within five Monte Carlo errors plus 0.001 at every name, those that pass the naming
    model's NUTS test (naming_test), those named as the exact rule names them, the largest gap and
    its Monte Carlo error, the largest gap in Monte Carlo errors where the exact posterior is above
    0.05, the largest R-hat, NUTS's mean leapfrog steps a draw, the divergences and NUTS's seconds a
    field."""
    head = ["Column", "Bodies", "Measures", "Model", "Fields within", "Naming test", "Same name",
            "Largest gap (MC error)", "Gap in MC errors, above 0.05", "Largest R-hat", "Steps a draw", "Divergences",
            "Seconds a field"]
    out = ["| " + " | ".join(head) + " |", "|---|---:|---|---|" + "---:|" * (len(head) - 4)]
    for r in record["rows"]:
        F = len(r["gap"])
        i = int(np.argmax(r["gap"]))
        out.append("| %s | %d | %s | %s | %d of %d | %d of %d | %d of %d | %.4f (%.4f) | %.1f | %.3f | %.1f | %d | %s |"
                   % (r["type"].replace("_", "-"), r["bodies"], r["subset"], r["model"], r["fields_within"], F,
                      naming_test(r), F, sum(r["same_name"]), F, r["gap"][i], r["gap_mcse"][i],
                      max(r["gap_in_errors"]), max(r["rhat"]),
                      float(np.mean(r["steps"])), r["divergences"], _ms(r["sample_s"])))
    return "\n".join(out) + "\n"


def naming_test(row: dict) -> int:
    """The fields of a row that pass all three checks of the naming model's NUTS test
    (tests/test_schwingcheck_model.py): every name within PYMC_WITHIN, every name the exact
    posterior puts above 0.05 within five Monte Carlo errors, and the largest R-hat below PYMC_RHAT.
    A record made before pymc_run kept each field's within (commit 9d94314's) is read only where
    every field is within, as every row of that record is."""
    each = row.get("within_each")
    if each is None:
        if row["fields_within"] != len(row["gap"]):
            raise ValueError("the row keeps no field's own within, and not every field is within")
        each = [True] * len(row["gap"])
    k = PYMC_WITHIN[0]
    return sum(1 for w, e, h in zip(each, row["gap_in_errors"], row["rhat"]) if w and e <= k and h < PYMC_RHAT)


def _ms(v: float) -> str:
    return "%.3g" % v if v < 100 else "{:,.0f}".format(v)


def load(which: str) -> dict:
    with open(RECORDS[which]) as f:
        return json.load(f)


def tables() -> Dict[str, str]:
    """Every README table of the chain, by its marker."""
    main = load("main")
    out = {"chain:main": main_table(main), "chain:claims": claims_table(main), "chain:weights": weights_table(main)}
    if os.path.exists(RECORDS["axis"]):
        ax = load("axis")
        out["chain:axis-5"] = axis_table(ax, main, 5, "all")
        out["chain:axis-5-seven"] = axis_table(ax, main, 5, "seven")
    if os.path.exists(RECORDS["speed"]):
        out["chain:speed"] = speed_table(load("speed"))
    if os.path.exists(RECORDS["pymc"]):
        out["chain:pymc"] = pymc_table(load("pymc"))
    return out


def readme_blocks(text: str, prefix: str = "chain") -> Dict[str, List[str]]:
    """The tables between <!-- prefix:name --> and <!-- /prefix:name --> in the README, by name,
    each as often as it is written."""
    out: Dict[str, List[str]] = {}
    for m in re.finditer(r"<!-- (%s:[\w-]+) -->\n(.*?)<!-- /\1 -->" % re.escape(prefix), text, re.S):
        out.setdefault(m.group(1), []).append(m.group(2))
    return out


def check(readme: str = README, records: bool = True) -> List[str]:
    """What differs between the README's chain tables and the records', and, with records, what
    keeps the records from reading on the same fields (consistent): an empty list when none."""
    with open(readme) as f:
        have = readme_blocks(f.read())
    out = compare_blocks(have, tables())
    if records:
        out += consistent({k: load(k) for k, path in RECORDS.items() if os.path.exists(path)})
    return out


def compare_blocks(have: Dict[str, List[str]], want: Dict[str, str]) -> List[str]:
    """What differs between the README's blocks and the tables the records give. A block may carry
    notes below its table after a blank line; the table itself must be the record's, with no row
    of its own after the record's last and no text right after it, which GitHub would draw as one
    more row."""
    out = []
    for name, table in want.items():
        if name not in have:
            out.append("the README has no block %s" % name)
        elif len(have[name]) > 1:
            out.append("the README writes %s more than once" % name)
        elif not have[name][0].startswith(table):
            out.append("the README's %s is not the record's" % name)
        elif have[name][0][len(table):].startswith("|"):
            out.append("the README's %s has rows after the record's table" % name)
        elif have[name][0][len(table):] and not have[name][0][len(table):].startswith("\n"):
            out.append("the README's %s has text right after the record's table" % name)
    for name in have:
        if name not in want:
            out.append("the README's %s has no record" % name)
    return out


SHARED = ("columns_per_type", "fields_per_column", "seeds")


def consistent(records: Dict[str, dict]) -> List[str]:
    """What keeps the records from reading on the same fields: every record's columns, fields a
    column and seeds must be `run`'s, and the axis's widths too, since the axis table reads each of
    its rows against `run`'s on the same fields; an empty list when they agree."""
    main, out = records.get("main"), []
    if main is None:
        return out
    for which, record in records.items():
        for key in SHARED:
            if record.get(key) != main.get(key):
                out.append("the %s record's %s are %r, the main record's %r" % (which, key, record.get(key), main.get(key)))
    if "axis" in records and records["axis"].get("widths") != main.get("widths"):
        out.append("the axis record's widths are %r, the main record's %r" % (records["axis"].get("widths"), main.get("widths")))
    return out


def write(record: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(record, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.chain_study")
    ap.add_argument("what", choices=("run", "axis", "speed", "pymc", "table", "check"))
    ap.add_argument("--columns", type=int, default=100)
    ap.add_argument("--processes", type=int, default=PROCESSES)
    ap.add_argument("--out", default=None, help="where run, axis, speed or pymc writes its record")
    ap.add_argument("--table", choices=("main", "claims", "weights", "axis", "speed", "pymc"), default="main")
    a = ap.parse_args(argv)
    if a.what == "run":
        write(run(a.columns), a.out or RECORDS["main"])
    elif a.what == "axis":
        write(axis(a.columns, processes=a.processes), a.out or RECORDS["axis"])
    elif a.what == "speed":
        write(speed(a.columns), a.out or RECORDS["speed"])
    elif a.what == "pymc":
        write(pymc_compare(a.columns, processes=a.processes), a.out or RECORDS["pymc"])
    elif a.what == "table":
        main_rec = load("main")
        if a.table == "main":
            print(main_table(main_rec), end="")
        elif a.table == "claims":
            print(claims_table(main_rec), end="")
        elif a.table == "weights":
            print(weights_table(main_rec), end="")
        elif a.table == "axis":
            print(axis_table(load("axis"), main_rec), end="")
        elif a.table == "pymc":
            print(pymc_table(load("pymc")), end="")
        else:
            print(speed_table(load("speed")), end="")
    else:
        problems = check()
        for p in problems:
            print(p)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
