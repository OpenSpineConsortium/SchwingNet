"""Checks the second review of the exact study asked for, recorded beside its record.

    OMP_NUM_THREADS=1 python run.py exact-supplement --outdir ../records/exact-2026-10-26

The readers of the exact study's results checked several statements with scripts of their own,
and four of what they found are worth a number in a file rather than a sentence that says a
reader saw it:

1. THE REGION CLAIM NEAR A REGIONAL BORDER. The record counts the region claim (cervical,
   thoracic or lumbar, at posterior 0.99) over every field only. Most single bodies are far from
   a regional border, where the claim is almost never wrong, so the pooled rate says little about the bodies
   near C7/T1 and T12/L1, where the claim is in effect that border's claim. `region_split`
   tallies it apart for the bodies within two levels of each regional border and for the rest,
   under the generator on the scoring columns and in the robustness worlds of the record (the
   specimen, level and combined worlds), drawn again from the record's own seeds.
2. THE QUADRATURE ON EVERY SCORING COLUMN. The record measures the quadrature on the first 100
   of the 2,000 scoring columns; `quadrature_all` repeats exact.quadrature_check on all of them.
3. THE EXACT RULE ON THE CLASSIFIER'S FIELDS. The identifiability study scored its classifier on
   the first 1,000 of the 2,000 columns drawn here (same seed, same measures, drawn in order);
   `first_columns` gives the exact rule's rate on those 1,000 alone.
4. COLUMNS OF ANOTHER LENGTH. The rule has places for typical columns only; `anomalous` scores
   its names at 0.99 on the generator's six-lumbar, four-lumbar and T13 columns, each middle body
   judged by the name the column's own count gives it.

Nothing here changes the exact study's record; the tables of a robustness world are drawn by the
same calls robust_task makes, so the region tallies of the worlds reproduce the record's own
region counts (the test checks one specimen and one level world, and `matches_record` checks
every pooled count).
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, List, Optional, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import exact as E          # noqa: E402
import neighbour as NB     # noqa: E402
import panjabi as P        # noqa: E402

REGION_WIDTHS = (1, 3)
REGIONAL_BORDERS = {"C7/T1": E.LEVELS.index("T1"), "T12/L1": E.LEVELS.index("L1")}
WORLD_KINDS = ("specimens", "levels", "combined")
FIRST_COLUMNS = 1000
FIRST_WIDTHS = (1, 3, 5, 7, 9)
ANOMALOUS = ("six_lumbar", "four_lumbar", "t13")
ANOMALOUS_SEED = 99
ANOMALOUS_COLUMNS = 150
ANOMALOUS_WIDTHS = (1, 3, 5)


def near_border(levels: np.ndarray, cut: int) -> np.ndarray:
    """The bodies within two levels of the border between level cut - 1 and level cut: the two
    above it and the two below, as the record's claims count them."""
    return np.abs(levels - (cut - 0.5)) <= 2


def region_tally(tp: np.ndarray, levels: np.ndarray) -> Dict[str, List[int]]:
    """Region claims made and wrong, for every body, near each regional border and far from both,
    as [made, wrong, bodies]."""
    reg = E.region_decisions(tp)
    made = reg >= 0
    wrong = made & (reg != E.REGION_INDEX[levels])
    near = {name: near_border(levels, cut) for name, cut in REGIONAL_BORDERS.items()}
    far = ~np.logical_or.reduce(list(near.values()))
    groups = dict(all=np.ones(len(levels), bool), far=far, **near)
    return {name: [int((made & g).sum()), int((wrong & g).sum()), int(g.sum())] for name, g in groups.items()}


def add_tally(a: Dict[str, List[int]], b: Dict[str, List[int]]) -> Dict[str, List[int]]:
    return {k: [x + y for x, y in zip(a.get(k, [0, 0, 0]), b[k])] for k in b}


def describe_tally(t: Dict[str, List[int]]) -> Dict[str, dict]:
    """Counts with the share made and the share right, for reading."""
    out = {}
    for name, (made, wrong, bodies) in t.items():
        out[name] = {"made": made, "wrong": wrong, "bodies": bodies,
                     "said_for": made / bodies if bodies else None,
                     "precision": 1.0 - wrong / made if made else None}
    return out


def region_split_generator(V: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict,
                           widths: Sequence[int] = REGION_WIDTHS) -> Dict[str, dict]:
    """The region claim of the exact rule, both planes, on the scoring columns, split by distance
    from the regional borders."""
    out = {}
    for n in widths:
        X, truth, _ = E.fields(V, n)
        tp = E.target_posterior(E.chunked_posterior(X, mu, sd, synth, n), n)
        out[str(n)] = describe_tally(region_tally(tp, truth + E.target_offset(n)))
    return out


def world_task_tally(task: tuple, ref, measures: Sequence[str], synth: dict,
                     widths: Sequence[int] = REGION_WIDTHS) -> Dict[str, Dict[str, Dict[str, List[int]]]]:
    """One table or combined world of the record, drawn as robust_task draws it, every rule of
    E.RULES on the same columns: {rule: {width: tally}}."""
    kind, mode, _, world_seed, col_seed = task
    drawn = E.redrawn_table(ref, measures, np.random.default_rng(world_seed), mode, synth)
    rule_ref, data_ref = (drawn, ref) if mode == "specimens" else (ref, drawn)
    data_synth, r_data = dict(synth), 0.0
    if kind == "combined":
        data_synth["noise_mm"], r_data = E.COMBINED["noise_mm"], E.COMBINED["r_between"]
    cols = NB.draw_columns(data_ref, ["typical"], col_seed, E.ROBUST_COLUMNS, measures, r_between=r_data,
                           **{k: data_synth[k] for k in ("rho", "noise_mm", "scale_sd")})
    V = E.column_values(cols, measures)
    out = {}
    for name, spec in E.RULES.items():
        rs = E.rule_synth(synth, spec)
        mu, sd = E.table_arrays(E.rule_table(rule_ref, measures, spec), measures)
        out[name] = {}
        for n in widths:
            X, truth, _ = E.fields(V, n)
            tp = E.target_posterior(E.chunked_posterior(X, mu, sd, rs, n), n)
            out[name][str(n)] = region_tally(tp, truth + E.target_offset(n))
    return out


def world_kind(task: tuple) -> Optional[str]:
    if task[0] == "table":
        return task[1]
    return "combined" if task[0] == "combined" else None


def _world_job(args):
    task, ref, measures, synth = args
    return world_kind(task), world_task_tally(task, ref, measures, synth)


def region_split_worlds(results) -> Dict[str, dict]:
    """Pooled over the worlds of each kind: {kind: {rule: {width: described tally}}}."""
    pooled: Dict[str, dict] = {}
    for kind, by_rule in results:
        for rule, by_width in by_rule.items():
            for n, t in by_width.items():
                slot = pooled.setdefault(kind, {}).setdefault(rule, {})
                slot[n] = add_tally(slot.get(n, {}), t)
    return {kind: {rule: {n: describe_tally(t) for n, t in by_width.items()} for rule, by_width in by_rule.items()}
            for kind, by_rule in pooled.items()}


def matches_record(split: Dict[str, dict], record: dict) -> Dict[str, bool]:
    """Whether the pooled region counts of each kind, rule and width equal the record's own
    (robust.table_<kind> or robust.combined_worlds, <rule>.<n>.claims.regions_*). The record
    pools the claims made as a share of the bodies, and the claims wrong as a count."""
    keys = {"specimens": "table_specimens", "levels": "table_levels", "combined": "combined_worlds"}
    out = {}
    for kind, by_rule in split.items():
        cell = record.get("robust", {}).get(keys[kind], {})
        for rule, by_width in by_rule.items():
            for n, t in by_width.items():
                rec = cell.get(rule, {}).get(n, {}).get("claims", {})
                if "regions_decided" not in rec:
                    continue
                share = t["all"]["made"] / t["all"]["bodies"]
                out["%s.%s.%s" % (kind, rule, n)] = (abs(rec["regions_decided"] - share) < 1e-12
                                                     and rec["regions_errors"] == t["all"]["wrong"])
    return out


def _quadrature_job(args):
    V, mu, sd, synth = args
    return E.quadrature_check(V, mu, sd, synth)


def pool_quadrature(parts: List[dict], fields_per_width: Dict[str, int]) -> dict:
    """exact.quadrature_check over chunks of columns, the largest difference and the calls
    changed summed."""
    out = {"used": parts[0]["used"], "reference": parts[0]["reference"],
           "max_abs_posterior_difference": {}, "calls_changed": {}, "fields": fields_per_width}
    for n in parts[0]["max_abs_posterior_difference"]:
        out["max_abs_posterior_difference"][n] = {J: max(p["max_abs_posterior_difference"][n][J] for p in parts)
                                                  for J in parts[0]["max_abs_posterior_difference"][n]}
        out["calls_changed"][n] = {J: sum(p["calls_changed"][n][J] for p in parts)
                                   for J in parts[0]["calls_changed"][n]}
    return out


def first_columns(V: np.ndarray, mu: np.ndarray, sd: np.ndarray, synth: dict, keep: Sequence[int],
                  n_first: int = FIRST_COLUMNS, widths: Sequence[int] = FIRST_WIDTHS) -> Dict[str, dict]:
    """The exact rule's share named exactly on the first n_first columns and on all of them."""
    out = {}
    for n in widths:
        row = {}
        for name, Vs in (("first", V[:n_first]), ("all", V)):
            X, truth, _ = E.fields(Vs[:, list(keep), :], n)
            post = E.chunked_posterior(X, mu[list(keep)], sd[list(keep)], synth, n)
            row[name] = float((post.argmax(1) == truth).mean())
        row["fields_first"] = int(min(n_first, len(V)) * (E.L - n + 1))
        out[str(n)] = row
    return out


def anomalous(ref, measures: Sequence[str], mu: np.ndarray, sd: np.ndarray, synth: dict,
              phenotypes: Sequence[str] = ANOMALOUS, seed: int = ANOMALOUS_SEED,
              n_columns: int = ANOMALOUS_COLUMNS, widths: Sequence[int] = ANOMALOUS_WIDTHS) -> Dict[str, dict]:
    """The rule's names at 0.99 on columns of another length, each field's middle body judged by
    the name its own column's count gives it (an L6 is never named right, since the rule has no
    place for it)."""
    out = {}
    for ph in phenotypes:
        cols = NB.draw_columns(ref, [ph], seed, n_columns, measures)
        out[ph] = {}
        for n in widths:
            answered = wrong = fields = 0
            for c in cols:
                Vc = np.array([[c.values[m] for m in measures]])
                nl = Vc.shape[2]
                X = np.concatenate([Vc[:, :, k:k + n] for k in range(nl - n + 1)])
                names = [c.levels[k + E.target_offset(n)] for k in range(nl - n + 1)]
                post = E.chunked_posterior(X, mu, sd, synth, n)
                calls = [E.LEVELS[k + E.target_offset(n)] for k in post.argmax(1)]
                said = post.max(1) >= E.CLAIM_LEVEL
                answered += int(said.sum())
                wrong += sum(1 for i in range(len(calls)) if said[i] and calls[i] != names[i])
                fields += len(calls)
            out[ph][str(n)] = {"fields": fields, "answered": answered, "wrong": wrong,
                               "precision": 1.0 - wrong / answered if answered else None}
    return out


def save(rec: dict, outdir: Optional[str]) -> None:
    if not outdir:
        return
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "supplement.json")
    with open(path + ".tmp", "w", newline="\n") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=NB._jsonable)
        fh.write("\n")
    os.replace(path + ".tmp", path)


def run(outdir: Optional[str] = None, record_json: Optional[str] = None, processes: int = E.PROCESSES,
        n_score: int = E.N_SCORE, n_worlds: int = E.ROBUST_WORLDS, quick: bool = False) -> dict:
    from concurrent.futures import ProcessPoolExecutor
    t0 = time.time()
    measures = list(E.MEASURES7)
    synth = dict(rho=NB.SYNTH["rho"], noise_mm=NB.SYNTH["noise_mm"], scale_sd=NB.SYNTH["scale_sd"])
    ref = P.load_reference(measures=measures)
    mu, sd = E.table_arrays(ref, measures)
    V = E.column_values(NB.draw_columns(ref, ["typical"], E.SCORE_SEED, n_score, measures), measures)
    keep = sorted(measures.index(m) for m in E.REGIMES["both"])
    rec: dict = {"study": "exact-supplement", "of": "exact.json", "measures": measures, "synth": synth,
                 "score_seed": E.SCORE_SEED, "n_columns": n_score, "quick": bool(quick), "complete": False,
                 "python": sys.version.split()[0], "numpy": np.__version__, "finished_after_seconds": {}}

    def done(part: str) -> None:
        rec["finished_after_seconds"][part] = round(time.time() - t0, 1)
        rec["seconds"] = round(time.time() - t0, 1)
        save(rec, outdir)

    tasks = [t for t in E.robust_tasks(n_worlds) if world_kind(t) in WORLD_KINDS]
    chunks = [V[c0:c0 + E.CHUNK] for c0 in range(0, len(V), E.CHUNK)]
    with ProcessPoolExecutor(max_workers=max(1, processes)) as pool:
        worlds = [pool.submit(_world_job, (t, ref, measures, synth)) for t in tasks]
        quads = [pool.submit(_quadrature_job, (c, mu, sd, synth)) for c in chunks]
        rec["first_columns"] = first_columns(V, mu, sd, synth, keep, n_first=min(FIRST_COLUMNS, n_score))
        rec["region_split"] = {"generator": region_split_generator(V, mu, sd, synth)}
        rec["anomalous"] = anomalous(ref, measures, mu, sd, synth, n_columns=10 if quick else ANOMALOUS_COLUMNS)
        done("generator")
        rec["region_split"]["worlds"] = region_split_worlds([j.result() for j in worlds])
        if record_json and os.path.exists(record_json):
            with open(record_json) as fh:
                rec["region_split"]["matches_record"] = matches_record(rec["region_split"]["worlds"], json.load(fh))
        done("worlds")
        fields_per_width = {str(n): int(len(V) * (E.L - n + 1)) for n in (1, 3, 5, 9, 15, 21)}
        rec["quadrature_all"] = pool_quadrature([j.result() for j in quads], fields_per_width)
        done("quadrature")
    rec["complete"] = True
    done("all")
    return rec
