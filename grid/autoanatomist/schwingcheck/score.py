"""What a rule did on every field: the archive's rates, computed the same way.

`summary` is exact.summary of the archive with its keys unchanged (exact, within_one, the Bayes
error the posterior predicts beside the one counted, the log loss, the share answered and the
precision at each posterior threshold with its clustered standard error, the 99 per cent set's
size and coverage, the mapping quality, the calibration, the rates per true start and per true
centre level, the landmark windows, the confusion of offsets), and `claims` is exact.claims_summary,
what a field lets one say about its middle body at 0.99. The rescoring test holds both to the
record of 2026-10-26 (tests/test_schwingcheck_record.py), so a rate here means what it meant
there. Standard errors are clustered by column, since the fields of one column share its draws.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

import numpy as np

from . import LEVELS
from .rule import credible_sets

THRESHOLDS = (0.9, 0.99, 0.999)
CREDIBLE = 0.99
CLAIM_LEVEL = 0.99
MAPQ_CAP = 60.0
L = len(LEVELS)
REGION_NAMES = ("cervical", "thoracic", "lumbar")
REGION_INDEX = np.array(["CTL".index(lv[0]) for lv in LEVELS])
CUT_NAMES = ["%s/%s" % (LEVELS[c - 1], LEVELS[c]) for c in range(1, L)]
LANDMARKS = {"cervicothoracic": ("C7", "T1"), "mid_thoracic": ("T3", "T10"), "thoracolumbar": ("T12", "L1")}


def clustered_se(hit: np.ndarray, group: np.ndarray) -> float:
    """The standard error of a rate whose fields come in columns: the per-column rates' SD over
    the square root of the number of columns, with no loop over columns."""
    cols, inv = np.unique(group, return_inverse=True)
    if len(cols) < 2:
        return float("nan")
    rates = np.bincount(inv, weights=hit) / np.bincount(inv)
    return float(rates.std(ddof=1) / math.sqrt(len(cols)))


def ratio_se(errors: np.ndarray, answered: np.ndarray) -> float:
    """The ratio estimator's standard error of a pooled error rate, clustered."""
    e, a = np.asarray(errors, float), np.asarray(answered, float)
    w = len(a)
    if w < 2 or a.sum() == 0:
        return float("nan")
    r = e - (e.sum() / a.sum()) * a
    return float(math.sqrt(w / (w - 1.0) * (r * r).sum()) / a.sum())


def mapq(p: np.ndarray, cap: float = MAPQ_CAP) -> np.ndarray:
    return np.minimum(-10.0 * np.log10(np.maximum(1.0 - p, 10.0 ** (-cap / 10.0))), cap)


def target_offset(n: int) -> int:
    """Which body of the field a claim is about: the middle one, the upper of the two middle ones
    when n is even."""
    return (n - 1) // 2


def calibration(top: np.ndarray, hit: np.ndarray, edges=(0.0, 0.5, 0.7, 0.9, 0.99, 0.999, 1.0001)) -> List[dict]:
    """The posterior of the named place against how often it was right, by bins of the posterior
    (the archive's keys)."""
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (top >= lo) & (top < hi)
        out.append({"lo": lo, "hi": min(hi, 1.0), "n": int(sel.sum()),
                    "mean_posterior": float(top[sel].mean()) if sel.any() else float("nan"),
                    "correct": float(hit[sel].mean()) if sel.any() else float("nan")})
    return out


def summary(post: np.ndarray, truth: np.ndarray, group: np.ndarray, n: int, detail: bool = True,
            levels: Sequence[str] = LEVELS) -> dict:
    """What one rule did on every field of one width (the archive's exact.summary)."""
    call = post.argmax(1)
    top = post.max(1)
    hit = (call == truth).astype(float)
    out = {"n_fields": int(len(truth)), "places": int(post.shape[1]),
           "exact": float(hit.mean()), "se_cluster": clustered_se(hit, group),
           "within_one": float((np.abs(call - truth) <= 1).mean()),
           "errors": int((hit == 0).sum()),
           "bayes_error_predicted": float((1.0 - top).mean()),
           "bayes_error_counted": float(1.0 - hit.mean()),
           "log_loss": float(-np.log(np.maximum(post[np.arange(len(truth)), truth], 1e-300)).mean()),
           "selective": {}, "selective_099_by_called_region": {}}
    region_index = np.array(["CTL".index(lv[0]) for lv in levels])
    called_region = region_index[call + target_offset(n)]
    for r, name in enumerate(REGION_NAMES):
        a = (top >= 0.99) & (called_region == r)
        out["selective_099_by_called_region"][name] = {"n_answered": int(a.sum()), "errors": int((hit[a] == 0).sum())}
    groups = np.unique(group, return_inverse=True)[1]
    for t in THRESHOLDS:
        ans = top >= t
        out["selective"][repr(t)] = {
            "answered": float(ans.mean()), "n_answered": int(ans.sum()),
            "errors": int((hit[ans] == 0).sum()),
            "precision": float(hit[ans].mean()) if ans.any() else float("nan"),
            "precision_se": ratio_se(np.bincount(groups, weights=ans & (hit == 0)), np.bincount(groups, weights=ans))}
    size, member = credible_sets(post, CREDIBLE)
    out["credible"] = {"level": CREDIBLE, "mean_size": float(size.mean()),
                       "share_singleton": float((size == 1).mean()),
                       "coverage": float(member[np.arange(len(truth)), truth].mean())}
    if not detail:
        return out
    q = mapq(top)
    out["mapq"] = {"median": float(np.median(q)), "share_ge_20": float((q >= 20).mean()),
                   "share_ge_30": float((q >= 30).mean())}
    out["calibration"] = calibration(top, hit)
    out["by_start"] = {}
    for k in range(post.shape[1]):
        sel = truth == k
        out["by_start"][levels[k]] = {"exact": float(hit[sel].mean()) if sel.any() else float("nan"),
                                      "answered_099": float((top[sel] >= 0.99).mean()) if sel.any() else float("nan"),
                                      "precision_099": float(hit[sel & (top >= 0.99)].mean())
                                      if (sel & (top >= 0.99)).any() else float("nan")}
    if n % 2 == 1:
        h = n // 2
        out["by_centre"] = {levels[k + h]: out["by_start"][levels[k]] for k in range(post.shape[1])}
    out["landmarks"] = {}
    for name, (a, b) in LANDMARKS.items():
        if a not in levels or b not in levels:
            continue
        ia, ib = list(levels).index(a), list(levels).index(b)
        sel = (truth <= ia) & (truth + n - 1 >= ib) if name != "mid_thoracic" else \
            (truth >= ia) & (truth + n - 1 <= ib)
        if sel.any():
            out["landmarks"][name] = {"n_fields": int(sel.sum()), "exact": float(hit[sel].mean()),
                                      "answered_099": float((top[sel] >= 0.99).mean()),
                                      "errors": int((hit[sel] == 0).sum())}
    out["confusion_offsets"] = {str(d): int(c) for d, c in zip(*np.unique(call - truth, return_counts=True))}
    return out


# ---- the claims about the middle body ------------------------------------------------------------

def target_posterior(post: np.ndarray, n: int) -> np.ndarray:
    t = target_offset(n)
    out = np.zeros((post.shape[0], L))
    out[:, t:t + post.shape[1]] = post
    return out


def cut_decisions(tp: np.ndarray, level: float = CLAIM_LEVEL) -> Tuple[np.ndarray, np.ndarray]:
    below = 1.0 - np.cumsum(tp, axis=1)[:, :-1]
    say = np.where(below >= level, 1, np.where(below <= 1.0 - level, -1, 0))
    return say, below


def region_decisions(tp: np.ndarray, level: float = CLAIM_LEVEL) -> np.ndarray:
    mass = np.stack([tp[:, REGION_INDEX == r].sum(1) for r in range(3)], axis=1)
    return np.where(mass.max(1) >= level, mass.argmax(1), -1)


def shortest_intervals(tp: np.ndarray, level: float = CLAIM_LEVEL) -> Tuple[np.ndarray, np.ndarray]:
    cs = np.concatenate([np.zeros((tp.shape[0], 1)), np.cumsum(tp, axis=1)], axis=1)
    start = np.full(tp.shape[0], -1)
    width = np.zeros(tp.shape[0], int)
    for w in range(1, L + 1):
        mass = cs[:, w:] - cs[:, :-w]
        best = mass.argmax(1)
        ok = (width == 0) & (mass[np.arange(len(tp)), best] >= level - 1e-12)
        start[ok], width[ok] = best[ok], w
    return start, width


def open_cuts(n: int) -> List[int]:
    t = target_offset(n)
    return [c for c in range(1, L) if t < c < t + (L - n + 1)]


def claims(post: np.ndarray, truth: np.ndarray, n: int, detail: bool = True) -> dict:
    """What a field of n consecutive bodies lets one say about its middle body at 0.99 (the
    archive's exact.claims_summary)."""
    tp = target_posterior(post, n)
    lev = truth + target_offset(n)
    say, _ = cut_decisions(tp)
    out: dict = {"target": "body %d of %d" % (target_offset(n) + 1, n), "level": CLAIM_LEVEL, "cuts": {}}
    present = np.unique(lev)
    for c in open_cuts(n):
        truly_below = lev >= c
        dec = say[:, c - 1] != 0
        wrong = dec & ((say[:, c - 1] == 1) != truly_below)
        near = np.abs(lev - (c - 0.5)) <= 2.0
        nd, ne = int((dec & near).sum()), int((wrong & near).sum())
        row = {"decided": float(dec.mean()), "n_decided": int(dec.sum()), "errors": int(wrong.sum()),
               "precision": float(1.0 - wrong.sum() / dec.sum()) if dec.any() else float("nan"),
               "n_within_two": int(near.sum()), "n_decided_within_two": nd, "errors_within_two": ne,
               "decided_within_two": float(dec[near].mean()) if near.any() else float("nan"),
               "precision_within_two": float(1.0 - ne / nd) if nd else float("nan")}
        if detail:
            row["decided_by_level"] = {LEVELS[i]: float(dec[lev == i].mean()) for i in present}
        out["cuts"][CUT_NAMES[c - 1]] = row
    reg = region_decisions(tp)
    true_reg = REGION_INDEX[lev]
    dec = reg >= 0
    out["regions"] = {"decided": float(dec.mean()), "errors": int((dec & (reg != true_reg)).sum()),
                      "n_decided": int(dec.sum())}
    if detail:
        out["regions"]["decided_by_level"] = {LEVELS[i]: float(dec[lev == i].mean()) for i in present}
    a, w = shortest_intervals(tp)
    cover = (lev >= a) & (lev < a + w)
    out["interval"] = {"coverage": float(cover.mean()), "mean_width": float(w.mean()),
                       "share_width": {str(k): float((w == k).mean()) for k in (1, 2, 3)},
                       "share_width_le_5": float((w <= 5).mean())}
    if detail:
        out["interval"]["median_width_by_level"] = {LEVELS[i]: float(np.median(w[lev == i])) for i in present}
    return out


def compare(a, b, path: str = "", tol: float = 1e-9) -> List[str]:
    """Where two nested rate dictionaries differ past tol (NaN equal to NaN), as a list of paths."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s/%s: only in one" % (path, k))
            else:
                out.extend(compare(a[k], b[k], "%s/%s" % (path, k), tol))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append("%s: %d against %d entries" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(compare(x, y, "%s[%d]" % (path, i), tol))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not ((math.isnan(a) and math.isnan(b)) or abs(a - b) <= tol):
            out.append("%s: %r against %r" % (path, a, b))
    elif a != b:
        out.append("%s: %r against %r" % (path, a, b))
    return out
