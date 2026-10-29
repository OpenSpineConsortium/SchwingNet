"""The exact rule as a second opinion on a registration's answer, recorded for the white paper.

    python run.py second-opinion --outdir ../records/whitepaper-2026-10-26

The white paper of 2026-10-26 (docs/SCHWINGCHECK_LEVELCHECK.md) asks what the exact rule adds
beside a registration method such as LevelCheck, which copies the labels of the patient's own CT
onto the radiograph. A registration that converges to the wrong vertebra is most often one level
off, so the question is how often the exact rule's posterior at that adjacent level is low enough
to contradict it, and how often its posterior at a correct answer is that low, which would
contradict a registration that was right.

On the exact study's own scoring columns (the record's seed, table and settings, both planes),
for every field of n consecutive bodies and every place it could be, this tallies the posterior
the rule gives the true place and the two places one level away, and the share of each below 0.01
and 0.05, and at or above 0.5, 0.9 and 0.99. The same shares are kept for the fields centred on
each level (`by_centre`), since the overall shares weight every place alike and a registration's
one-level errors need not fall on fields at random: the paper's review found the flag rate varies
several-fold along the spine. It refuses to write unless the share it names exactly at each width
equals the record's, so these counts and the record cannot disagree. `latency` times
the rule on one field at a time on the machine it runs on. Every number is
about synthetic columns drawn from Panjabi's tables, never a patient; how a registration fails is
not modelled here, only what the rule would say about an answer one level off.

The combination itself is Bayes' rule with the registration's confusion rates (white paper,
section "Combining the two"), and holds only where the two fail for unrelated reasons.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Dict, Optional, Sequence

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import exact as E          # noqa: E402
import neighbour as NB     # noqa: E402
import panjabi as P        # noqa: E402

RECORD = os.path.join(HERE, "..", "records", "exact-2026-10-26", "exact.json")
WIDTHS = (1, 3, 5, 9)
LOW = (0.01, 0.05)
HIGH = (0.5, 0.9, 0.99)
CHUNK = 250


def scoring_columns(d: dict):
    """The record's scoring columns as values, with the table and settings they were scored with."""
    measures = list(d["measures"])
    synth = {k: d["synth"][k] for k in ("rho", "noise_mm", "scale_sd")}
    if any(abs(NB.SYNTH[k] - synth[k]) > 1e-12 for k in synth) or int(d["score_seed"]) != int(E.SCORE_SEED):
        raise ValueError("the record was scored with other settings than the generator's defaults")
    ref = P.load_reference(measures=measures)
    cols = NB.draw_columns(ref, ["typical"], int(d["score_seed"]), int(d["n_columns"]), measures)
    mu, sd = E.table_arrays(ref, measures)
    return E.column_values(cols, measures), mu, sd, synth


def posteriors_at(V: np.ndarray, mu, sd, synth: dict, n: int):
    """For every field of n bodies: the posterior at its true place, at the places one level away,
    whether the rule names it exactly, and the level its target body sits at for each of the true
    and the adjacent answers."""
    at_true, at_adjacent, named, centre_true, centre_adjacent = [], [], [], [], []
    for start in range(len(E.LEVELS) + 1 - n):
        X = V[:, :, start:start + n]
        post = np.concatenate([E.chunked_posterior(X[i:i + CHUNK], mu, sd, synth, n)
                               for i in range(0, len(X), CHUNK)])
        centre = start + E.target_offset(n)
        named.append(post.argmax(1) == start)
        at_true.append(post[:, start])
        centre_true.append(np.full(len(X), centre))
        for j in (start - 1, start + 1):
            if 0 <= j < post.shape[1]:
                at_adjacent.append(post[:, j])
                centre_adjacent.append(np.full(len(X), centre))
    return (np.concatenate(at_true), np.concatenate(at_adjacent), np.concatenate(named),
            np.concatenate(centre_true), np.concatenate(centre_adjacent))


def tally(at_true: np.ndarray, at_adjacent: np.ndarray) -> Dict[str, float]:
    out = {"fields": int(at_true.size), "adjacent_answers": int(at_adjacent.size)}
    for t in LOW:
        out["off_by_one_below_%g" % t] = float(np.mean(at_adjacent < t))
        out["correct_below_%g" % t] = float(np.mean(at_true < t))
    for t in HIGH:
        out["off_by_one_at_least_%g" % t] = float(np.mean(at_adjacent >= t))
        out["correct_at_least_%g" % t] = float(np.mean(at_true >= t))
    return out


def by_centre(at_true: np.ndarray, at_adjacent: np.ndarray, centre_true: np.ndarray,
              centre_adjacent: np.ndarray) -> Dict[str, Dict[str, float]]:
    """The tally for the fields whose target body sits at each level, keyed by that level's name."""
    return {E.LEVELS[c]: tally(at_true[centre_true == c], at_adjacent[centre_adjacent == c])
            for c in np.unique(centre_true)}


def summarise(at_true, at_adjacent, named, centre_true, centre_adjacent) -> dict:
    """One width's entry in the record."""
    return dict(tally(at_true, at_adjacent), exact=float(named.mean()),
                by_centre=by_centre(at_true, at_adjacent, centre_true, centre_adjacent))


def latency(V: np.ndarray, mu, sd, synth: dict, n: int = 3, calls: int = 50) -> dict:
    """Wall time of the rule on one field at a time, after one warm call: a measurement of this
    machine, not of clinical hardware, and without the step that reads the measures off images."""
    import platform
    X = V[:, :, 5:5 + n]
    E.chunked_posterior(X[:1], mu, sd, synth, n)
    times = []
    for i in range(calls):
        t = time.perf_counter()
        E.chunked_posterior(X[i:i + 1], mu, sd, synth, n)
        times.append(1000.0 * (time.perf_counter() - t))
    return {"bodies": n, "calls": calls, "median_ms": float(np.median(times)), "max_ms": float(np.max(times)),
            "machine": platform.machine(), "cpus": os.cpu_count(), "python": platform.python_version(),
            "numpy": np.__version__}


def run(outdir: Optional[str] = None, record_json: str = RECORD, widths: Sequence[int] = WIDTHS) -> dict:
    t0 = time.time()
    with open(record_json, encoding="utf-8") as fh:
        d = json.load(fh)
    V, mu, sd, synth = scoring_columns(d)
    out = {"study": "the exact rule as a second opinion on a registration's answer",
           "record": os.path.relpath(os.path.abspath(record_json), os.path.join(HERE, "..")).replace(os.sep, "/"),
           "score_seed": int(d["score_seed"]), "n_columns": int(d["n_columns"]), "regime": "both",
           "low": list(LOW), "high": list(HIGH), "widths": {}}
    for n in widths:
        parts = posteriors_at(V, mu, sd, synth, n)
        named = parts[2]
        recorded = d["widths"][str(n)]["regimes"]["both"]["exact"]
        if abs(float(named.mean()) - recorded) > 1e-12:
            raise ValueError("%d bodies: named exactly %.6f here, %.6f in the record" % (n, named.mean(), recorded))
        out["widths"][str(n)] = summarise(*parts)
        print("%d bodies: %s" % (n, json.dumps({k: v for k, v in out["widths"][str(n)].items() if k != "by_centre"})))
    out["latency"] = latency(V, mu, sd, synth)
    out["seconds"] = round(time.time() - t0, 1)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "second_opinion.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return out
