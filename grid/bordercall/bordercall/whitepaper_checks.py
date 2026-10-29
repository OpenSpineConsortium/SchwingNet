"""Two checks the white paper's review asked for, recorded before the paper quotes them.

    python run.py whitepaper-checks --outdir ../records/whitepaper-2026-10-26

The review of the white paper of 2026-10-26 (docs/SCHWINGCHECK_LEVELCHECK.md) found two numbers
the paper needs that no record held.

Within one level. The exact study's table gives, beside the share named exactly, the share named
within one level by the rule that names the likeliest place. That rule is the Bayes rule for
naming exactly, not for naming within one level, so its within-one share is not a ceiling. The
Bayes rule for the within-one loss names the centre of the likeliest run of three places: the j
that maximises p(j - 1) + p(j) + p(j + 1), a missing neighbour at either end counting as zero.
`within_one` scores both rules on all 2,000 of the exact study's scoring columns (seed 97, both
planes, the record's table and settings) at 1, 3, 5 and 9 bodies, and refuses to write unless the
likeliest-place rule's exact and within-one shares equal the record's.

The count from C2. The supplement scored the rule's names at 0.99 on three anomalous phenotypes
against each column's own names, which call the thirteenth rib-bearing body T13: the rib reading.
The white paper's study takes as truth each body's number counted from C2, under which that body
is L1 and every body below it takes the next name down (neighbour.py, the signed offset). On six-
and four-lumbar columns the two conventions agree, since the count from C2 names their lumbar
bodies L1 onwards as the columns do; on thirteen-rib columns they differ below T12. `anomalous`
scores the same columns (seed 99, 150 per phenotype) both ways, at 1, 3, 5 and 9 bodies, and
refuses to write unless the own-name counts at 1, 3 and 5 bodies equal the supplement's.

Every number is about synthetic columns drawn from Panjabi's tables, never a patient.
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

import exact as E              # noqa: E402
import exact_supplement as S   # noqa: E402
import neighbour as NB         # noqa: E402
import panjabi as P            # noqa: E402
import second_opinion as SO    # noqa: E402

RECORD = SO.RECORD
SUPPLEMENT = os.path.join(HERE, "..", "records", "exact-2026-10-26", "supplement.json")
WIDTHS = (1, 3, 5, 9)
# Each body's name counted from C2 by its position, the column's first body being C3: seven
# cervical and twelve thoracic bodies, then lumbar names for every body after them.
COUNT_FROM_C2 = P.CERVICAL + P.THORACIC + ["L%d" % i for i in range(1, 8)]


def best_within_one(post: np.ndarray) -> np.ndarray:
    """For each field, the place at the centre of the likeliest run of three places."""
    padded = np.pad(post, ((0, 0), (1, 1)))
    runs = padded[:, :-2] + padded[:, 1:-1] + padded[:, 2:]
    return runs.argmax(1)


def run_mass(post: np.ndarray, centre: np.ndarray) -> np.ndarray:
    """The posterior the rule gives the run of three places around each field's chosen centre."""
    padded = np.pad(post, ((0, 0), (1, 1)))
    rows = np.arange(len(post))
    return padded[rows, centre] + padded[rows, centre + 1] + padded[rows, centre + 2]


def within_one_at(V: np.ndarray, mu, sd, synth: dict, n: int) -> dict:
    """Both rules' shares on every field of n bodies."""
    hits = {"exact": 0, "argmax_within_one": 0, "best_within_one": 0}
    predicted = 0.0
    fields = 0
    for start in range(len(E.LEVELS) + 1 - n):
        X = V[:, :, start:start + n]
        post = np.concatenate([E.chunked_posterior(X[i:i + SO.CHUNK], mu, sd, synth, n)
                               for i in range(0, len(X), SO.CHUNK)])
        call = post.argmax(1)
        best = best_within_one(post)
        hits["exact"] += int((call == start).sum())
        hits["argmax_within_one"] += int((np.abs(call - start) <= 1).sum())
        hits["best_within_one"] += int((np.abs(best - start) <= 1).sum())
        predicted += float(run_mass(post, best).sum())
        fields += len(X)
    out = {k: v / fields for k, v in hits.items()}
    out["best_within_one_predicted"] = predicted / fields
    out["fields"] = fields
    return out


def within_one(d: dict, widths: Sequence[int] = WIDTHS) -> Dict[str, dict]:
    V, mu, sd, synth = SO.scoring_columns(d)
    out = {}
    for n in widths:
        row = within_one_at(V, mu, sd, synth, n)
        rec = d["widths"][str(n)]["regimes"]["both"]
        for mine, theirs in (("exact", "exact"), ("argmax_within_one", "within_one")):
            if abs(row[mine] - rec[theirs]) > 1e-12:
                raise ValueError("%d bodies: %s %.6f here, %.6f in the record" % (n, mine, row[mine], rec[theirs]))
        out[str(n)] = row
        print("within one, %d bodies: %s" % (n, json.dumps(row)))
    return out


def names_both_ways(cols: List[P.Column], mu, sd, synth: dict, n: int, measures: Sequence[str]) -> dict:
    """The rule's calls on every field of n bodies in these columns, judged by the column's own
    names and by the count from C2: how many it names at 0.99 and how many of those are wrong, and
    how many of all its calls are right."""
    t = {"fields": 0, "answered": 0, "wrong_own": 0, "wrong_count": 0, "right_own_all": 0, "right_count_all": 0}
    off = E.target_offset(n)
    for c in cols:
        Vc = np.array([[c.values[m] for m in measures]])
        nl = Vc.shape[2]
        X = np.concatenate([Vc[:, :, k:k + n] for k in range(nl - n + 1)])
        own = [c.levels[k + off] for k in range(nl - n + 1)]
        count = [COUNT_FROM_C2[k + off] for k in range(nl - n + 1)]
        post = E.chunked_posterior(X, mu, sd, synth, n)
        calls = [E.LEVELS[k + off] for k in post.argmax(1)]
        said = post.max(1) >= E.CLAIM_LEVEL
        t["fields"] += len(calls)
        t["answered"] += int(said.sum())
        t["wrong_own"] += sum(1 for i in range(len(calls)) if said[i] and calls[i] != own[i])
        t["wrong_count"] += sum(1 for i in range(len(calls)) if said[i] and calls[i] != count[i])
        t["right_own_all"] += sum(1 for i in range(len(calls)) if calls[i] == own[i])
        t["right_count_all"] += sum(1 for i in range(len(calls)) if calls[i] == count[i])
    a = t["answered"]
    t["precision_own"] = 1.0 - t["wrong_own"] / a if a else None
    t["precision_count"] = 1.0 - t["wrong_count"] / a if a else None
    t["exact_own"] = t["right_own_all"] / t["fields"]
    t["exact_count"] = t["right_count_all"] / t["fields"]
    return t


def anomalous(d: dict, supplement: dict, widths: Sequence[int] = WIDTHS) -> Dict[str, dict]:
    measures = list(d["measures"])
    synth = {k: d["synth"][k] for k in ("rho", "noise_mm", "scale_sd")}
    ref = P.load_reference(measures=measures)
    mu, sd = E.table_arrays(ref, measures)
    out = {}
    for ph in S.ANOMALOUS:
        cols = NB.draw_columns(ref, [ph], S.ANOMALOUS_SEED, S.ANOMALOUS_COLUMNS, measures)
        out[ph] = {}
        for n in widths:
            row = names_both_ways(cols, mu, sd, synth, n, measures)
            rec = supplement["anomalous"][ph].get(str(n))
            if rec is not None and (row["fields"], row["answered"], row["wrong_own"]) != \
                    (rec["fields"], rec["answered"], rec["wrong"]):
                raise ValueError("%s at %d bodies: %r here, %r in the supplement" % (ph, n, row, rec))
            out[ph][str(n)] = row
            print("%s, %d bodies: %s" % (ph, n, json.dumps(row)))
    return out


def run(outdir: Optional[str] = None, record_json: str = RECORD, supplement_json: str = SUPPLEMENT,
        widths: Sequence[int] = WIDTHS) -> dict:
    t0 = time.time()
    with open(record_json, encoding="utf-8") as fh:
        d = json.load(fh)
    with open(supplement_json, encoding="utf-8") as fh:
        supplement = json.load(fh)
    if int(supplement["score_seed"]) != int(d["score_seed"]):
        raise ValueError("the supplement and the record were scored on different columns")
    root = os.path.join(HERE, "..")
    out = {"study": "checks the white paper's review asked for: the within-one Bayes rule, and anomalous "
                    "columns judged by the count from C2",
           "record": os.path.relpath(os.path.abspath(record_json), root).replace(os.sep, "/"),
           "supplement": os.path.relpath(os.path.abspath(supplement_json), root).replace(os.sep, "/"),
           "score_seed": int(d["score_seed"]), "n_columns": int(d["n_columns"]), "regime": "both",
           "anomalous_seed": S.ANOMALOUS_SEED, "anomalous_columns": S.ANOMALOUS_COLUMNS,
           "claim_level": E.CLAIM_LEVEL}
    out["within_one"] = within_one(d, widths)
    out["anomalous"] = anomalous(d, supplement, widths)
    out["seconds"] = round(time.time() - t0, 1)
    if outdir:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "checks.json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(out, fh, indent=1, sort_keys=True)
            fh.write("\n")
    return out
