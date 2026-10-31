"""The census of the measures: what each one tells a lone body about its level, from every table in hand.

    python -m schwingcheck.census run --series research_notes/paper-tables/data/series.csv \
        --vocabulary research_notes/paper-tables/tools/vocabulary.csv [--fields 100] [--processes 1]
    python -m schwingcheck.census run --table levels.csv [--correlation correlation.csv] --source gold3
    python -m schwingcheck.census table [--table ranking|order|papers|unranked]
    python -m schwingcheck.census check

The owner's ask of 29 October 2026, 15:09 UTC: "a census of the morphometrics information ranked in
order of how much it helps each level be identified, ensured they are separated by orthogonal
information", and at 15:18 UTC over "all ... unique measures from the clinical reread thread not just
panjabi". One definition and one code path, agreed with the morphometrics thread the same hour, so
that Panjabi's table, the 39 other papers' series and the gold tier 3 CT table are read alike:

- The information a set of measures S from one source gives about a lone body at level L is
  I_L(S) = E[log p(L | x, S)] - log p(L), the expectation over bodies drawn at L by the generator's
  law for that source (the table's mean and spread at L, the patient's size log-normal with the
  rule's spread, each measure scaled by its own power of the size and read with its own error),
  the posterior the exact rule's (rule.py) over the levels the source prints the measures at, a
  uniform prior over them, the size integrated out on the rule's nodes. It is in nats: log K is the
  most a source printed at K levels can give, when the body is named for certain.
- A measure's standalone rank at a level is I_L of the measure alone. Its place in the order is
  greedy: among the source's measures printed at one set of levels, the first is the one whose I
  summed over the levels is largest, and each next one adds the largest conditional gain,
  I_L(S + m) - I_L(S), summed over the levels; the conditional gain per level is what the measure
  adds given everything before it, so the order separates the information the measures carry.
- A measure whose conditional gain, summed over the levels, is under a tenth of its standalone
  information repeats something before it: it is listed under the earlier measure it shares most
  with, the pair's redundancy being I(m) + I(m') - I({m, m'}). Where a correlation table is given
  (the gold tier 3 rows, Pearson within each level), pairs whose |r| reaches 0.7 at the median
  level are listed as sharing too, measured rather than inferred.

Each source is one population measured one way, as the owner's rule of 28 October 2026 says, so no
information is ever computed across sources: Panjabi's four papers are one source (the same twelve
spines), each of the other papers' (cohort, technique, sex, group) series is one, and the gold
tier 3 table is one. A measure printed at only some of the levels gives its information over those
levels alone, which is a smaller question than the whole column: its I is read against its own log
K. What a measure's presence says (a rib facet is thoracic) is not counted, since the generator
draws the measure only where it is printed. The errors are the rule's stated assumptions
(measures.py): 1 mm for a length, sqrt(pi A / 2) mm^2 for an area, 3 degrees for an angle, and
0.04 for a ratio (RATIO_ERROR), which scales with no power of the size; a table that carries its
own error column (the gold tier 3 schema) is read with it. Every number is synthetic truth: the
generator's bodies drawn from each table, never a patient.

The series of the other papers are read from the clinical reread's series.csv (research_notes/
paper-tables/data/series.csv): one source per (paper, cohort, technique, sex, group), the values
the paper measured itself (source_of_values "this paper"; a quoted value, a figure's example and
the pig cohorts are left out), a disc's row (L4-L5) counted to the body above it (L4), rows at C2,
S1, L6 or T13 left out since the census runs over C3 to L5, and a measure's kind read from its
units (mm, mm2, deg, ratio). The vocabulary (tools/vocabulary.csv) gives every key of the reread,
so the census lists what it could not rank and why.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS, SIZE_POWER
from . import chain_study as CS
from . import curve as CV
from . import measures as MS
from . import rule as R
from .mnemonics import MEASURES

ROOT = CS.ROOT
README = CS.README
RECORD_DIR = os.path.join(ROOT, "records", "census-2026-10-29")
RECORD = os.path.join(RECORD_DIR, "census.json")
FIELDS = 100                       # bodies drawn per level and source
SEED = 1029
RATIO_ERROR = 0.04                 # a ratio's measurement error, the morphometrics thread's bound, no power of the size
KIND_POWER = dict(SIZE_POWER, ratio=0)
UNIT_KIND = {"mm": "length", "mm2": "area", "deg": "angle", "ratio": "ratio"}
REPEAT_SHARE = 0.1                 # a conditional gain under this share of the standalone repeats something before it
SHARED_R = 0.7                     # |r| at the median level from which a pair is listed as sharing
LEFT_OUT_COHORTS = re.compile(r"^(cited_|fig|example_)|porcine|^vanderhouwen")
LEVEL_INDEX = {lv: i for i, lv in enumerate(LEVELS)}


@dataclass(frozen=True)
class Series:
    """One measure of one source: its kind, error and table rows at the levels it is printed at."""
    key: str
    kind: str
    error: float
    levels: Tuple[str, ...]
    mean: Tuple[float, ...]
    sd: Tuple[float, ...]
    n: Tuple[Optional[int], ...]

    @property
    def power(self) -> int:
        return KIND_POWER[self.kind]


@dataclass
class Source:
    id: str
    paper: str
    cohort: str = ""
    technique: str = ""
    sex: str = ""
    group: str = ""
    measures: List[Series] = field(default_factory=list)
    correlation: Dict[Tuple[str, str], float] = field(default_factory=dict)    # median |r| over levels


def error_for(kind: str, means: Sequence[float]) -> float:
    """The rule's stated error for a measure of this kind (measures.py's), a ratio's RATIO_ERROR."""
    if kind == "ratio":
        return RATIO_ERROR
    rows = [MS.Row(level="", mean=float(m), sd=1.0, n=1, cells=()) for m in means]
    return float(MS.error_of(kind, rows))


# ---- the sources ----------------------------------------------------------------------------

def panjabi_source() -> Tuple[Source, List[dict]]:
    """Panjabi's four papers as one source, every measure of the long table that has rows, whole
    or as the mean of a pair, over the levels it is printed at; and the measures left out, each
    with its reason."""
    reg = MS.registry()
    src = Source(id="panjabi", paper="Panjabi 1991, 1992, 1993", cohort="twelve fresh autopsy spines",
                 technique="morphometer on the dissected vertebrae")
    out = []
    for name in MEASURES:
        key = MS._pool_key(name, reg)
        m = reg[key] if key else None
        if m is None or not m.rows:
            out.append({"key": name, "source": "panjabi", "reason": "printed as a mean with no spread"})
            continue
        rows = [r for r in m.rows if r.level in LEVEL_INDEX]
        rows.sort(key=lambda r: LEVEL_INDEX[r.level])
        src.measures.append(Series(name, m.kind, float(m.error), tuple(r.level for r in rows),
                                   tuple(r.mean for r in rows), tuple(r.sd for r in rows), tuple(r.n for r in rows)))
    return src, out


def read_csv(path: str) -> List[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def body_level(level: str) -> Optional[str]:
    """The body a row counts to: itself, or the upper body of a disc (L4-L5 is L4); None outside C3 to L5."""
    level = level.strip()
    if "-" in level:
        level = level.split("-")[0].strip()
    return level if level in LEVEL_INDEX else None


def series_sources(path: str) -> Tuple[List[Source], List[dict]]:
    """The other papers' series as sources, one per (paper, cohort, technique, sex, group); and the
    keys that gave no series to rank, each with its reason."""
    rows = read_csv(path)
    by: Dict[tuple, Dict[str, Dict[str, list]]] = {}
    left: Dict[str, str] = {}
    for r in rows:
        key = r["key"].strip()
        kind = UNIT_KIND.get(r["units"].strip())
        if kind is None:
            left.setdefault(key, "not a length, area, angle or ratio (%s)" % r["units"].strip())
            continue
        if r.get("source_of_values", "this paper").strip() not in ("", "this paper"):
            left.setdefault(key, "values quoted from another paper")
            continue
        if LEFT_OUT_COHORTS.search(r["cohort"].strip()):
            left.setdefault(key, "a quoted value, a figure's example or a pig cohort")
            continue
        lv = body_level(r["level"])
        if lv is None:
            left.setdefault(key, "printed outside C3 to L5 only")
            continue
        if r["sd"].strip() in ("", "nan") or r["mean"].strip() in ("", "nan"):
            left.setdefault(key, "printed as a mean with no spread")
            continue
        sd = float(r["sd"])
        if not sd > 0:
            left.setdefault(key, "printed with a spread of zero")
            continue
        sid = (r["paper"].strip(), r["cohort"].strip(), r["technique"].strip(), r["sex"].strip(), r["group"].strip())
        cell = by.setdefault(sid, {}).setdefault(key, {}).setdefault(lv, {"mean": [], "sd": [], "n": [], "kind": kind})
        cell["mean"].append(float(r["mean"]))
        cell["sd"].append(sd)
        cell["n"].append(int(float(r["n"])) if r["n"].strip() not in ("", "nan") else None)
    sources = []
    ranked = set()
    for sid, measures in sorted(by.items()):
        src = Source(id=" | ".join(x for x in sid if x), paper=sid[0], cohort=sid[1], technique=sid[2], sex=sid[3], group=sid[4])
        for key, cells in sorted(measures.items()):
            levels = sorted(cells, key=lambda lv: LEVEL_INDEX[lv])
            if len(levels) < 2:
                left.setdefault(key, "printed at one level only, which names nothing")
                continue
            kind = cells[levels[0]]["kind"]
            means = tuple(float(np.mean(cells[lv]["mean"])) for lv in levels)     # the sides' mean where both are printed
            sds = tuple(float(np.mean(cells[lv]["sd"])) for lv in levels)
            ns = tuple(max((n for n in cells[lv]["n"] if n is not None), default=None) for lv in levels)
            src.measures.append(Series(key, kind, error_for(kind, means), tuple(levels), means, sds, ns))
            ranked.add(key)
        if src.measures:
            sources.append(src)
    out = [{"key": k, "source": "papers", "reason": v} for k, v in sorted(left.items()) if k not in ranked]
    return sources, out


def table_source(path: str, source_id: str, correlation: Optional[str] = None) -> Source:
    """A table in the schema agreed with the morphometrics thread: level, measure, kind, n, mean,
    sd, error; and its correlation table, level, measure_a, measure_b, n, r, as the median |r|
    over the levels of each pair."""
    by: Dict[str, Dict[str, dict]] = {}
    for r in read_csv(path):
        lv = body_level(r["level"])
        if lv is None or r["sd"].strip() in ("", "nan") or not float(r["sd"]) > 0:
            continue
        by.setdefault(r["measure"].strip(), {})[lv] = {"kind": r["kind"].strip(), "mean": float(r["mean"]), "sd": float(r["sd"]),
                                                      "n": int(float(r["n"])) if r.get("n", "").strip() else None,
                                                      "error": float(r["error"]) if r.get("error", "").strip() else None}
    src = Source(id=source_id, paper=source_id)
    for key, cells in sorted(by.items()):
        levels = sorted(cells, key=lambda lv: LEVEL_INDEX[lv])
        if len(levels) < 2:
            continue
        kind = cells[levels[0]]["kind"]
        if kind not in KIND_POWER:
            raise ValueError("%s has kind %r; the census takes length, area, angle or ratio" % (key, kind))
        means = tuple(cells[lv]["mean"] for lv in levels)
        errors = [cells[lv]["error"] for lv in levels if cells[lv]["error"] is not None]
        error = float(np.median(errors)) if errors else error_for(kind, means)
        src.measures.append(Series(key, kind, error, tuple(levels), means, tuple(cells[lv]["sd"] for lv in levels),
                                   tuple(cells[lv]["n"] for lv in levels)))
    if correlation:
        pairs: Dict[Tuple[str, str], list] = {}
        for r in read_csv(correlation):
            a, b = sorted((r["measure_a"].strip(), r["measure_b"].strip()))
            if a != b and r["r"].strip() not in ("", "nan"):
                pairs.setdefault((a, b), []).append(abs(float(r["r"])))
        src.correlation = {k: float(np.median(v)) for k, v in pairs.items()}
    return src


# ---- the information ------------------------------------------------------------------------

def draw(measures: Sequence[Series], n_per_level: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    """n_per_level bodies at each level the measures share, by the generator's law: X (fields,
    measures, 1) and the index of each body's level."""
    levels = measures[0].levels
    rng = np.random.default_rng(seed)
    K, M = len(levels), len(measures)
    truth = np.repeat(np.arange(K), n_per_level)
    s = np.exp(rng.normal(0.0, R.SYNTH["scale_sd"], len(truth)))
    X = np.empty((len(truth), M, 1))
    for j, m in enumerate(measures):
        mu, sd = np.asarray(m.mean)[truth], np.asarray(m.sd)[truth]
        X[:, j, 0] = s ** m.power * (mu + sd * rng.normal(0.0, 1.0, len(truth))) + m.error * rng.normal(0.0, 1.0, len(truth))
    return X, truth


def level_stats(logev: np.ndarray, truth: np.ndarray, K: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """From log p(field | level) under a uniform prior: at each level, the information in nats
    (the mean log posterior at the truth plus log K), its standard error and the share named exactly."""
    post = R.posterior(logev)
    logp = np.log(np.maximum(post[np.arange(len(truth)), truth], 1e-300))
    top = post.argmax(1) == truth
    info, se, exact = np.zeros(K), np.zeros(K), np.zeros(K)
    for k in range(K):
        at = truth == k
        info[k] = logp[at].mean() + math.log(K)
        se[k] = logp[at].std(ddof=1) / math.sqrt(at.sum()) if at.sum() > 1 else float("nan")
        exact[k] = top[at].mean()
    return info, se, exact


def loglik_table(X: np.ndarray, measures: Sequence[Series], nodes, chunk: int = 400) -> np.ndarray:
    """The per-measure log likelihood of every body at every level and node, (fields, levels,
    measures, nodes), as float32 to hold a whole group at once."""
    sizes, _ = nodes
    mu = np.array([m.mean for m in measures])
    sd = np.array([m.sd for m in measures])
    noise = np.array([m.error for m in measures])
    power = np.array([m.power for m in measures], float)
    F, K, M, J = X.shape[0], mu.shape[1], len(measures), len(sizes)
    LL = np.empty((F, K, M, J), np.float32)
    for f0 in range(0, F, chunk):
        LL[f0:f0 + chunk] = R.loglik(X[f0:f0 + chunk], (0,), mu, sd, R.SYNTH, sizes=sizes, noise=noise, power=power)
    return LL


def evidence(LL: np.ndarray, logw: np.ndarray, idx: Sequence[int], acc: Optional[np.ndarray] = None) -> np.ndarray:
    """log p(field | level) over the measures idx, the size integrated out, with acc the sum of
    the log likelihoods already chosen, (fields, levels, nodes)."""
    part = LL[:, :, list(idx), :].astype(np.float64).sum(2) if idx else 0.0
    if acc is not None:
        part = part + acc
    return R.logsumexp(part + logw, 2)


def census_group(measures: Sequence[Series], n_per_level: int, seed: int, nodes, correlation: Dict[Tuple[str, str], float]) -> dict:
    """The standalone information of each measure of one group (one source, one set of levels) and
    the greedy order with its conditional gains and what repeats what."""
    levels = measures[0].levels
    K, M = len(levels), len(measures)
    X, truth = draw(measures, n_per_level, seed)
    LL = loglik_table(X, measures, nodes)
    logw = nodes[1]
    stand = []
    for j in range(M):
        info, se, exact = level_stats(evidence(LL, logw, [j]), truth, K)
        stand.append({"info": info, "se": se, "exact": exact})
    order: List[dict] = []
    chosen: List[int] = []
    acc = None
    cum = np.zeros(K)
    remaining = list(range(M))
    while remaining:
        best = None
        for j in remaining:
            info, se, exact = level_stats(evidence(LL, logw, [j], acc), truth, K)
            gain = float((info - cum).sum())
            if best is None or gain > best[0]:
                best = (gain, j, info, exact)
        gain, j, info, exact = best
        entry = {"key": measures[j].key, "rank": len(chosen) + 1, "conditional": (info - cum).tolist(),
                 "cumulative": info.tolist(), "cumulative_exact": exact.tolist(),
                 "standalone_sum": float(stand[j]["info"].sum()), "conditional_sum": gain, "repeats": None, "redundancy": None}
        if chosen and gain < REPEAT_SHARE * stand[j]["info"].sum():
            pairs = []
            for i in chosen:
                pair_info, _, _ = level_stats(evidence(LL, logw, [i, j]), truth, K)
                pairs.append((float(stand[i]["info"].sum() + stand[j]["info"].sum() - pair_info.sum()), measures[i].key))
            entry["redundancy"], entry["repeats"] = max(pairs)
        order.append(entry)
        chosen.append(j)
        acc = LL[:, :, chosen, :].astype(np.float64).sum(2)
        cum = info
        remaining.remove(j)
    shared = [{"a": a, "b": b, "r": r} for (a, b), r in sorted(correlation.items())
              if r >= SHARED_R and a in {m.key for m in measures} and b in {m.key for m in measures}]
    return {"levels": list(levels), "fields_per_level": n_per_level, "seed": seed,
            "measures": [{"key": m.key, "kind": m.kind, "error": m.error, "power": m.power, "n": list(m.n),
                          "mean": list(m.mean), "sd": list(m.sd), "standalone": s["info"].tolist(),
                          "standalone_se": s["se"].tolist(), "standalone_exact": s["exact"].tolist()}
                         for m, s in zip(measures, stand)],
            "order": order, "shared_by_correlation": shared}


def groups_of(src: Source) -> List[List[Series]]:
    """The source's measures grouped by the set of levels they are printed at, since information
    is computed over one set of levels at a time."""
    by: Dict[Tuple[str, ...], List[Series]] = {}
    for m in src.measures:
        by.setdefault(m.levels, []).append(m)
    return [by[k] for k in sorted(by, key=lambda k: (-len(k), LEVEL_INDEX[k[0]]))]


def census_source(src: Source, n_per_level: int, seed: int, nodes) -> dict:
    groups = []
    for g, measures in enumerate(groups_of(src)):
        groups.append(census_group(measures, n_per_level, seed + 7919 * g, nodes, src.correlation))
    return {"id": src.id, "paper": src.paper, "cohort": src.cohort, "technique": src.technique, "sex": src.sex,
            "group": src.group, "n_measures": len(src.measures), "groups": groups}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(series: Optional[str] = None, vocabulary: Optional[str] = None, table: Optional[str] = None,
        correlation: Optional[str] = None, source_id: str = "table", n_per_level: int = FIELDS,
        seed: int = SEED, log=print) -> dict:
    made_by = CV.code_state()
    nodes = R.quadrature(R.SYNTH["scale_sd"])
    t0 = time.time()
    sources: List[Source] = []
    unranked: List[dict] = []
    inputs = {}
    if table is None:
        pan, left = panjabi_source()
        sources.append(pan)
        unranked += left
        if series:
            others, left = series_sources(series)
            sources += others
            unranked += left
            inputs["series"] = {"path": os.path.relpath(series, ROOT), "sha256": sha256(series)}
    else:
        sources.append(table_source(table, source_id, correlation))
        inputs["table"] = {"path": os.path.relpath(table, ROOT), "sha256": sha256(table)}
        if correlation:
            inputs["correlation"] = {"path": os.path.relpath(correlation, ROOT), "sha256": sha256(correlation)}
    vocab = []
    if vocabulary:
        vocab = [{"key": r["key"], "kind": r["kind"], "panjabi": r["panjabi"] == "yes"} for r in read_csv(vocabulary)]
        inputs["vocabulary"] = {"path": os.path.relpath(vocabulary, ROOT), "sha256": sha256(vocabulary)}
        ranked = {m.key for s in sources for m in s.measures}
        named = ranked | {u["key"] for u in unranked}
        for v in vocab:
            if v["key"] not in named:
                reason = "named in the reread, no paper prints a table of it" if v["kind"] in KIND_POWER else "not a measure of a vertebra (%s)" % v["kind"]
                unranked.append({"key": v["key"], "source": "vocabulary", "reason": reason})
    out_sources = []
    for i, src in enumerate(sources):
        out_sources.append(census_source(src, n_per_level, seed + 104729 * i, nodes))
        log("census: %d of %d sources, %s, %d measures, %.0f s" % (i + 1, len(sources), src.id, len(src.measures), time.time() - t0))
    ranked_keys = sorted({m["key"] for s in out_sources for g in s["groups"] for m in g["measures"]})
    unranked = [u for u in unranked if u["key"] not in ranked_keys]
    cmd = "python -m schwingcheck.census run --fields %d" % n_per_level
    if series:
        cmd += " --series %s" % os.path.relpath(series, ROOT)
    if vocabulary:
        cmd += " --vocabulary %s" % os.path.relpath(vocabulary, ROOT)
    if table:
        cmd += " --table %s --source %s" % (os.path.relpath(table, ROOT), source_id)
    if correlation:
        cmd += " --correlation %s" % os.path.relpath(correlation, ROOT)
    return {"command": cmd, "fields_per_level": n_per_level, "seed": seed, "levels": list(LEVELS),
            "scale_sd": R.SYNTH["scale_sd"], "nodes": "Gauss-Hermite %d" % len(nodes[0]), "ratio_error": RATIO_ERROR,
            "repeat_share": REPEAT_SHARE, "shared_r": SHARED_R, "inputs": inputs, "vocabulary": vocab,
            "sources": out_sources, "unranked": sorted(unranked, key=lambda u: u["key"]),
            "seconds": time.time() - t0, "machine": CV.machine(), "versions": CV.versions(), **CS.made(made_by)}


# ---- the tables -----------------------------------------------------------------------------

def load(path: str = RECORD) -> dict:
    with open(path) as f:
        return json.load(f)


def standalone_rows(record: dict) -> List[dict]:
    """One row per (source, measure): the standalone information at each level it is printed at."""
    out = []
    for s in record["sources"]:
        for g in s["groups"]:
            for m in g["measures"]:
                out.append({"source": s["id"], "paper": s["paper"], "key": m["key"], "kind": m["kind"],
                            "levels": g["levels"], "info": dict(zip(g["levels"], m["standalone"])),
                            "exact": dict(zip(g["levels"], m["standalone_exact"])), "n_levels": len(g["levels"])})
    return out


def paper_label(source_id: str) -> str:
    return source_id.split(" | ")[0]


def ranking_table(record: dict, top: int = 5) -> str:
    """At each level, the measures that tell most alone, over every source: key, source and nats,
    the source's log K beside it where it is printed at fewer than 22 levels."""
    rows = standalone_rows(record)
    lines = ["| Level | " + " | ".join("%d" % (i + 1) for i in range(top)) + " |",
             "|---|" + "---|" * top]
    for lv in record["levels"]:
        at = sorted((r for r in rows if lv in r["info"]), key=lambda r: -r["info"][lv])
        cells = []
        for r in at[:top]:
            extra = "" if r["n_levels"] == len(record["levels"]) else ", of %.2f" % math.log(r["n_levels"])
            cells.append("%s, %s, %.2f%s" % (r["key"], paper_label(r["source"]), r["info"][lv], extra))
        lines.append("| %s | %s |" % (lv, " | ".join(cells)))
    return "\n".join(lines) + "\n"


def region_sum(values: Sequence[float], levels: Sequence[str], prefix: str) -> float:
    return float(sum(v for v, lv in zip(values, levels) if lv.startswith(prefix)))


def order_table(record: dict) -> str:
    """Panjabi's greedy order over the 32 printed at every level: each measure's standalone
    information summed over the levels, its conditional gain, the gain by region, and what it
    repeats."""
    pan = next(s for s in record["sources"] if s["id"] == "panjabi")
    g = next(g for g in pan["groups"] if len(g["levels"]) == len(record["levels"]))
    lines = ["| # | Measure | Alone, nats | Adds, nats | Adds C | Adds T | Adds L | Repeats |", "|---|---|---|---|---|---|---|---|"]
    for e in g["order"]:
        rep = "%s (%.2f)" % (e["repeats"], e["redundancy"]) if e["repeats"] else ""
        lines.append("| %d | %s | %.2f | %.2f | %.2f | %.2f | %.2f | %s |" % (
            e["rank"], e["key"], e["standalone_sum"], e["conditional_sum"],
            region_sum(e["conditional"], g["levels"], "C"), region_sum(e["conditional"], g["levels"], "T"),
            region_sum(e["conditional"], g["levels"], "L"), rep))
    return "\n".join(lines) + "\n"


def papers_table(record: dict) -> str:
    """Every measure the other papers print with a spread, Panjabi's or not: how many sources, the
    levels covered, and the best standalone information as a mean over its levels, with its source."""
    rows = [r for r in standalone_rows(record) if r["source"] != "panjabi"]
    pan = {r["key"] for r in standalone_rows(record) if r["source"] == "panjabi"}
    by: Dict[str, List[dict]] = {}
    for r in rows:
        by.setdefault(r["key"], []).append(r)
    lines = ["| Measure | In Panjabi | Sources | Levels | Best mean nats (source, levels) |", "|---|---|---|---|---|"]
    for key in sorted(by, key=lambda k: -max(np.mean(list(r["info"].values())) for r in by[k])):
        rs = by[key]
        best = max(rs, key=lambda r: np.mean(list(r["info"].values())))
        levels = sorted({lv for r in rs for lv in r["levels"]}, key=lambda lv: LEVEL_INDEX[lv])
        lines.append("| %s | %s | %d | %s to %s (%d) | %.2f of %.2f (%s, %d) |" % (
            key, "yes" if key in pan else "no", len(rs), levels[0], levels[-1], len(levels),
            float(np.mean(list(best["info"].values()))), math.log(best["n_levels"]), paper_label(best["source"]), best["n_levels"]))
    return "\n".join(lines) + "\n"


def unranked_table(record: dict) -> str:
    lines = ["| Key | Why it is not ranked |", "|---|---|"]
    for u in record["unranked"]:
        lines.append("| %s | %s |" % (u["key"], u["reason"]))
    return "\n".join(lines) + "\n"


TABLES = {"ranking": ranking_table, "order": order_table, "papers": papers_table, "unranked": unranked_table}


def tables(path: str = RECORD) -> Dict[str, str]:
    record = load(path)
    return {"census:%s" % k: f(record) for k, f in TABLES.items()}


def check(readme: str = README, path: str = RECORD) -> List[str]:
    with open(readme, encoding="utf-8") as f:
        have = CS.readme_blocks(f.read(), "census")
    return CS.compare_blocks(have, tables(path))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m schwingcheck.census")
    ap.add_argument("what", choices=("run", "table", "check"))
    ap.add_argument("--fields", type=int, default=FIELDS, help="bodies drawn per level and source")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--series", help="the clinical reread's series.csv")
    ap.add_argument("--vocabulary", help="the clinical reread's vocabulary.csv, to list what is not ranked")
    ap.add_argument("--table", help="a table in the gold tier 3 schema: level, measure, kind, n, mean, sd, error")
    ap.add_argument("--correlation", help="its correlation table: level, measure_a, measure_b, n, r")
    ap.add_argument("--source", default="table", help="the name of the table's source")
    ap.add_argument("--out", default=RECORD)
    ap.add_argument("--which", choices=tuple(TABLES), default="ranking")
    a = ap.parse_args(argv)
    if a.what == "run":
        CS.write(run(a.series, a.vocabulary, a.table, a.correlation, a.source, a.fields, a.seed), a.out)
    elif a.what == "table":
        print(tables(a.out)["census:%s" % a.which], end="")
    else:
        problems = check(path=a.out)
        for p in problems:
            print(p)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
