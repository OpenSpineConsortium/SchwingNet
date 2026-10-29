"""The archive's exact rule on an imported study: measures missing on some bodies, gaps between
bodies, and a scale that is known, spread or unknown.

    python -m scanimport name  imports/verse/fields/s0001.csv
    python -m scanimport score imports/verse --n 1 3 5 9

The rule is archive/bordercall/exact.py's, unchanged in what it assumes: a field of bodies sits
at some place in the column C3 to L5, and given the place and the patient's size s each
measure's values are normal with mean s mu and covariance Delta + u u' (Panjabi's means and
SDs, rho 0.5, 1 mm of measurement error, log s normal with SD 0.07; neighbour.SYNTH). An imported
field differs from the archive's synthetic ones in three ways, and each is a marginal of the
same model, not a new one:

- A measure missing on a body (NaN: not taken, cut by the field of view, not shown by the view)
  is integrated out. For a normal vector the marginal of the entries present is normal with the
  entries' own mean and covariance, and the covariance of a subset of a diagonal-plus-rank-one
  matrix is the subset's diagonal plus the subset's rank one, so Sherman-Morrison runs over the
  entries present alone (`place_loglik`, the terms of the missing entries set to zero).
- Bodies with a gap between them (a body the labels skip, a body not measured) sit at places
  `offset` apart in the column, so at place k the body with offset o is compared with level
  k + o. The fields' offsets come from the names (column.offsets_of), never guessed.
- The size is integrated with the study's own scale spread added: a CT's millimetres are the
  patient's, so the spread is the generator's 0.07; a film's are divided by a nominal
  magnification whose spread (radiograph.py) adds in quadrature; a film with no pixel size has
  no scale at all, and the size is integrated under a flat prior on log s over a window wide
  enough for any place, with the 1 mm measurement error carried by the scale too (in pixels it
  is so many pixels as a millimetre is, which s holds), so the rule gives the same answer in any
  unit and the chords' proportions alone name the field.

The integral is the trapezoid on a fine grid in log s (exact.trapezoid, 1801 nodes over 9 SDs),
the archive's own independent check of its Gauss-Hermite rule, because a field of many bodies
pins s more tightly than Gauss-Hermite's 161 nodes resolve when the spread is wider than the
archive's. On a complete field of consecutive bodies at the archive's settings the log evidence
equals exact.evidence_lean with the same nodes to 1e-10 (tests/test_bridge.py).

A field is named under a uniform prior over the places it fits, as the archive scores; a study
whose labels were counted from C2 (column.facts_from_levels) is scored against its own names.
Studies whose phenotype is not typical are scored apart: the rule is the typical column's, so
on them it is measured, never trusted.
"""
from __future__ import annotations

import csv
import json
import math
import os
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import RULE_LEVELS, SEVEN, archive_path
from .column import Column, offsets_of

archive_path()
import exact as EX                                                   # noqa: E402
import neighbour as NB                                               # noqa: E402
import panjabi as P                                                  # noqa: E402

L = len(RULE_LEVELS)
LOG2PI = math.log(2.0 * math.pi)
UNKNOWN_HALF_WIDTH = 2.5           # log s window either side of the field's own estimate, flat prior
UNKNOWN_NODES = 2501
WIDTHS = (1, 3, 5, 9, 15)
TYPICAL = ("typical", "typical_as_far_as_the_scheme_says")
assert RULE_LEVELS == list(EX.LEVELS), "the import's rule levels must be the archive's"


def reference(measures: Sequence[str] = SEVEN, path: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray]:
    ref = P.load_reference(path or P.DEFAULT_REFERENCE, list(measures))
    return EX.table_arrays(ref, list(measures))


def places(offsets: Sequence[int]) -> int:
    """How many places in the column a field with these offsets fits."""
    return L - int(offsets[-1])


def place_loglik(X: np.ndarray, offsets: Sequence[int], mu: np.ndarray, sd: np.ndarray, start: int,
                 sizes: np.ndarray, rho: float, noise_mm: float, noise_scales: bool = False) -> np.ndarray:
    """log density of one field's present values at place `start`, per measure and size node:
    (measures, nodes). X is (measures, n) with NaN where a value is missing. With noise_scales
    the measurement error is noise_mm at size 1 and grows with s, as it must when the chords are
    in an unknown unit and s carries the unit."""
    nm = X.shape[0]
    pos = start + np.asarray(offsets, int)
    s = sizes[:, None]
    out = np.zeros((nm, len(sizes)))
    for m in range(nm):
        have = np.isfinite(X[m])
        if not have.any():
            continue
        x = X[m, have]
        mw, sw = mu[m, pos[have]], sd[m, pos[have]]
        noise2 = s * s * noise_mm * noise_mm if noise_scales else noise_mm * noise_mm
        delta = s * s * (1.0 - rho * rho) * sw * sw + noise2                   # (J, k)
        d = 1.0 / delta
        u = s * rho * sw
        r = x - s * mw
        a = (u * u * d).sum(1)
        quad = (r * r * d).sum(1) - ((r * u * d).sum(1)) ** 2 / (1.0 + a)
        logdet = np.log(delta).sum(1) + np.log1p(a)
        out[m] = -0.5 * (quad + logdet + have.sum() * LOG2PI)
    return out


def size_nodes(X: np.ndarray, mu: np.ndarray, scale_sd: float,
               scale_log_mean: float = 0.0, scale_extra_sd: Optional[float] = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """Sizes and log weights. A known scale: log s normal about scale_log_mean with the spread of
    the generator and of the study added in quadrature. An unknown one (scale_extra_sd None): a
    flat prior on log s about the field's own estimate, the same window at every place, so the
    prior's constant cancels between places."""
    if scale_extra_sd is not None:
        sdv = math.sqrt(scale_sd ** 2 + scale_extra_sd ** 2)
        sizes, logw = EX.trapezoid(sdv)
        return sizes * math.exp(scale_log_mean), logw
    have = np.isfinite(X)
    rows = np.nonzero(have.any(1))[0]
    centre = float(np.median(np.log(X[have]))) - float(np.median(np.log(mu[rows])))
    t = np.linspace(centre - UNKNOWN_HALF_WIDTH, centre + UNKNOWN_HALF_WIDTH, UNKNOWN_NODES)
    h = t[1] - t[0]
    logw = np.full(len(t), math.log(h / (2.0 * UNKNOWN_HALF_WIDTH)))
    logw[[0, -1]] += math.log(0.5)
    return np.exp(t), logw


def log_evidence(X: np.ndarray, offsets: Sequence[int], mu: np.ndarray, sd: np.ndarray, synth: dict,
                 scale_log_mean: float = 0.0, scale_extra_sd: Optional[float] = 0.0) -> np.ndarray:
    """log p(field | place) at every place the field fits, the size integrated out."""
    sizes, logw = size_nodes(X, mu, synth["scale_sd"], scale_log_mean, scale_extra_sd)
    unknown = scale_extra_sd is None
    return np.array([EX.logsumexp(place_loglik(X, offsets, mu, sd, k, sizes, synth["rho"], synth["noise_mm"], unknown)
                                  .sum(0) + logw, axis=0) for k in range(places(offsets))])


def posterior(logev: np.ndarray) -> np.ndarray:
    p = np.exp(logev - logev.max())
    return p / p.sum()


def named(post: np.ndarray, offsets: Sequence[int], level: float = 0.99) -> dict:
    """The answer: the place, the names it gives each body, its posterior, its mapping quality
    and the smallest set of places holding `level`."""
    order = np.argsort(-post)
    k = int(order[0])
    cum = np.cumsum(post[order])
    keep = order[:int(np.searchsorted(cum, level) + 1)]
    return {"place": k, "names": [RULE_LEVELS[k + o] for o in offsets], "posterior": float(post[k]),
            "mapq": float(EX.mapq(np.array([post[k]]))[0]),
            "credible_%g" % level: [RULE_LEVELS[int(j)] for j in sorted(keep)]}


# ---- an imported study ---------------------------------------------------------------------------

def study_scale(study: dict) -> Tuple[float, Optional[float]]:
    """(log mean, extra spread) of the study's scale; spread None for an unknown scale."""
    if study.get("scale_known") is False:
        return 0.0, None
    return float(study.get("scale_log_mean") or 0.0), float(study.get("scale_log_sd") or 0.0)


def rule_fields(col: Column, n: int, measures: Sequence[str]) -> List[Tuple[int, np.ndarray]]:
    """Every window of n consecutive rule levels the column holds with at least one value on
    each body: (the true place, values (measures, n))."""
    by_level = {b.level: b for b in col.bodies}
    out = []
    for k in range(L - n + 1):
        lv = RULE_LEVELS[k:k + n]
        if not all(x in by_level for x in lv):
            continue
        X = np.array([[by_level[x].values.get(m, math.nan) for x in lv] for m in measures], float)
        if np.isfinite(X).any(0).all():
            out.append((k, X))
    return out


def score_column(col: Column, mu: np.ndarray, sd: np.ndarray, measures: Sequence[str], synth: dict,
                 widths: Sequence[int] = WIDTHS) -> List[dict]:
    """The rule on every window of each width in a countable study, each against the study's
    own names."""
    mean, extra = study_scale(col.study)
    rows = []
    for n in widths:
        for k, X in rule_fields(col, n, measures):
            post = posterior(log_evidence(X, list(range(n)), mu, sd, synth, mean, extra))
            top = int(np.argmax(post))
            rows.append({"study_id": col.study["study_id"], "source": col.study.get("source"),
                         "phenotype": col.study.get("phenotype"), "n": n, "truth": RULE_LEVELS[k],
                         "called": RULE_LEVELS[top], "hit": int(top == k), "within_one": int(abs(top - k) <= 1),
                         "p_top": float(post[top]), "p_truth": float(post[k]),
                         "measures": int(np.isfinite(X).any(1).sum())})
    return rows


def summarise(rows: List[dict]) -> List[dict]:
    """Per group (typical or apart) and width: fields, studies, the rate exact and within one,
    and the share answered and the precision at posterior 0.99, with a standard error clustered
    by study."""
    groups: Dict[Tuple[str, int], List[dict]] = defaultdict(list)
    for r in rows:
        groups[("typical" if r["phenotype"] in TYPICAL else "apart", r["n"])].append(r)
    out = []
    for (group, n), rs in sorted(groups.items()):
        hit = np.array([r["hit"] for r in rs], float)
        p = np.array([r["p_top"] for r in rs])
        ans = p >= 0.99
        out.append({"group": group, "n": n, "fields": len(rs), "studies": len({r["study_id"] for r in rs}),
                    "exact": float(hit.mean()), "exact_se": clustered_se(rs, "hit"),
                    "within_one": float(np.mean([r["within_one"] for r in rs])),
                    "mean_p_top": float(p.mean()), "answered_099": float(ans.mean()),
                    "precision_099": float(hit[ans].mean()) if ans.any() else None})
    return out


def clustered_se(rows: List[dict], key: str) -> float:
    """The standard error of a mean over fields, clustered by study (fields of one spine share it)."""
    by: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        by[r["study_id"]].append(float(r[key]))
    g = len(by)
    if g < 2:
        return float("nan")
    tot = sum(len(v) for v in by.values())
    mean = sum(sum(v) for v in by.values()) / tot
    s = sum((sum(v) - len(v) * mean) ** 2 for v in by.values())
    return math.sqrt(g / (g - 1) * s) / tot


# ---- a field file ----------------------------------------------------------------------------------

def field_header(lines: Sequence[str]) -> dict:
    """The scale a field file's '#' lines state (column.write_field's): scale_known,
    scale_log_mean and scale_log_sd, each only where the file states it."""
    out = {}
    for line in lines:
        parts = line[1:].split()
        if len(parts) != 2:
            continue
        key, value = parts
        if key == "scale_known":
            out[key] = value == "True"
        elif key in ("scale_log_mean", "scale_log_sd"):
            out[key] = float(value)
    return out


def read_field(path: str) -> Tuple[List[str], np.ndarray, List[int], List[str], dict]:
    """A field CSV (column.write_field's, or schwingcheck's: `body`, the measures, optional
    `offset`): the measures it holds, values (measures, bodies), offsets, notes, and the scale its
    header states."""
    with open(path) as fh:
        lines = fh.read().splitlines()
    header = field_header([l for l in lines if l.startswith("#")])
    rows = list(csv.DictReader(l for l in lines if not l.startswith("#")))
    if not rows:
        raise SystemExit("%s holds no bodies" % path)
    measures = [m for m in SEVEN if m in rows[0]]
    if not measures:
        raise SystemExit("%s has none of the measures %s" % (path, ", ".join(SEVEN)))
    X = np.array([[float(r[m]) if (r.get(m) or "").strip() else math.nan for r in rows] for m in measures])
    notes = []
    if "offset" in rows[0] and all((r.get("offset") or "").strip() for r in rows):
        offs = [int(r["offset"]) for r in rows]
        offs = [o - offs[0] for o in offs]
    else:
        offs = list(range(len(rows)))
        notes.append("no offsets: the bodies are taken as consecutive")
    if any(b <= a for a, b in zip(offs, offs[1:])):
        raise SystemExit("%s: offsets must rise from the top body down" % path)
    keep = np.isfinite(X).any(0)
    if not keep.any():
        raise SystemExit("%s holds no measured body" % path)
    if not keep.all():
        notes.append("%d bodies with no value left out" % int((~keep).sum()))
        X, offs = X[:, keep], [o for o, k in zip(offs, keep) if k]
        offs = [o - offs[0] for o in offs]
    if offs[-1] >= L:
        raise SystemExit("%s spans %d levels, more than the rule's column holds" % (path, offs[-1] + 1))
    return measures, X, offs, notes, header


def name_field(path: str, scale_known: Optional[bool] = None, scale_extra_sd: Optional[float] = None,
               scale_log_mean: Optional[float] = None) -> dict:
    """Name one field file. The scale is the file's own (its header), each part overridden by an
    argument given; a file that states none is read as millimetres at the generator's spread."""
    measures, X, offs, notes, header = read_field(path)
    known = header.get("scale_known", True) if scale_known is None else scale_known
    extra = header.get("scale_log_sd", 0.0) if scale_extra_sd is None else scale_extra_sd
    shift = header.get("scale_log_mean", 0.0) if scale_log_mean is None else scale_log_mean
    if not known:
        notes.append("scale unknown: named from the chords' proportions alone")
    mu, sd = reference(measures)
    post = posterior(log_evidence(X, offs, mu, sd, NB.SYNTH, shift, extra if known else None))
    out = named(post, offs)
    out.update({"field": path, "measures": measures, "bodies": len(offs), "offsets": offs, "notes": notes,
                "posterior_by_place": {RULE_LEVELS[k]: round(float(p), 6) for k, p in enumerate(post)}})
    return out


def score_directory(directories: Sequence[str], measures: Sequence[str] = SEVEN,
                    widths: Sequence[int] = WIDTHS, include_uncountable: bool = False) -> dict:
    from .column import read_columns
    mu, sd = reference(measures)
    rows, skipped = [], defaultdict(int)
    for d in directories:
        for col in read_columns(d):
            if not col.study.get("countable") and not include_uncountable:
                skipped["not counted from C2"] += 1
                continue
            if offsets_of(col.levels) is None:
                skipped["names out of order or unnamed bodies"] += 1
                continue
            rows += score_column(col, mu, sd, measures, NB.SYNTH, widths)
    return {"rows": rows, "summary": summarise(rows), "skipped": dict(skipped),
            "measures": list(measures), "synth": NB.SYNTH, "widths": list(widths)}


def write_scores(out: str, result: dict) -> None:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "scores.csv"), "w", newline="") as fh:
        fields = ["study_id", "source", "phenotype", "n", "truth", "called", "hit", "within_one", "p_top",
                  "p_truth", "measures"]
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in result["rows"]:
            w.writerow(r)
    with open(os.path.join(out, "scores.json"), "w", newline="\n") as fh:
        json.dump({k: v for k, v in result.items() if k != "rows"}, fh, indent=1, sort_keys=True)
        fh.write("\n")
