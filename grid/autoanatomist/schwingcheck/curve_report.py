"""Step e's build-up study as tables and figures, from its record alone (curve.py writes it).

    python -m schwingcheck curve table --record records/curve-2026-10-28/curve.nc
    python -m schwingcheck curve figures --record records/curve-2026-10-28/curve.nc --outdir records/curve-2026-10-28/figures
    python -m schwingcheck curve check --record records/curve-2026-10-28/curve.nc

`table` prints the README's tables, each between the markers <!-- curve:NAME --> and
<!-- /curve:NAME -->, and `check` says whether the README holds each as `table` prints it, so that
every number the README gives for the study is the record's. `figures` draws in the package's
house format for line graphs (figures.py, the owner's default since 28 October 2026, taken from
this study's figure of naming as the measures are added): black ink, serif type, an axis on two
sides, no grid, no colour, the widths of the field told apart by line and marker as
identify_figures.py sets them; each figure is written as PDF with no date inside, PNG at 300 dpi,
the CSV of every number drawn and its caption, under sixty words, and FIGURES.md names the record
and the code by sha256. Every number is about synthetic columns drawn from Panjabi's tables, never
a patient.

A precision with no answered field wrong, whose standard error is 0 however few were answered, is
printed with its exact 95 per cent lower bound, rounded down (curve.precision_lower; on the data
axis on the count of the table that answered fewest, since its tables answer the same fields).
The data axis is read against the table as printed on the axis's own columns (curve's
people-printed arm), never against the nominal arm on all of its columns, and its rates carry
both standard errors, the one clustered by column and the one that counts the tables too. How the
times were taken, the calls, the batch, the threads and the machine, is read from the record's
attributes, not assumed, and what they do not give is named as not recorded, never printed in a
count's place; whether a NUTS run's setup holds a compile is read from the files the run added to
PyTensor's Numba cache.
"""
from __future__ import annotations

import json
import math
import os
import platform
import re
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import columns as C
from . import table as T
from .figures import INK, SERIF, WIDTH_STYLE, body_label, letter, save, sha256, style, write_csv

README = os.path.join(T.ROOT, "schwingcheck", "README.md")
TABLES = ("curve", "subsets", "arms", "data", "anomalous", "speed", "nuts", "floor")
WIDTHS = (1, 3, 9)
HEADLINE = 3                         # the width the one-width columns report, as the archive's figures do
ENGINE_NAME = {"numpy-trapezoid": "rule.py, trapezoid", "numpy-gauss-hermite": "rule.py, Gauss-Hermite",
               "pytensor-trapezoid": "compiled rule, trapezoid"}
ENGINE_STYLE = {"numpy-trapezoid": dict(linestyle="-", marker="o", markerfacecolor=INK),
                "numpy-gauss-hermite": dict(linestyle="--", marker="s", markerfacecolor="white"),
                "pytensor-trapezoid": dict(linestyle=":", marker="^", markerfacecolor="white")}
SUBSET_NAME = {"seven": "the seven (rung 0)", "lengths": "the lengths", "seven+areas": "the seven and the areas",
               "seven+angles": "the seven and the angles", "ap": "what an AP view reads",
               "lateral": "what a lateral view reads", "ap+lateral": "both views", "all": "all 32"}
FAMILY_NAME = {"pedicles": "the pedicles", "processes": "the processes", "facets": "the facets",
               "interfacet": "the interfacet distances", "body": "the rest of the body and the canal"}
FAMILIES = ("pedicles", "processes", "facets", "interfacet", "body")
PHENOTYPE_NAME = {"typical": "Typical", "four_lumbar": "Four lumbar", "six_lumbar": "Six lumbar",
                  "t13": "Thirteenth rib-bearing body", "lumbar_rib": "Rib on L1", "no_rib_t12": "No rib on T12"}
ANOMALOUS = ("four_lumbar", "six_lumbar", "t13", "lumbar_rib", "no_rib_t12")
PEOPLE = (12, 50, 200, 2000)
SPEED_MEASURES = (1, 7, 16, 32)
CAPTIONS = {
    "curve_accuracy":
        "Naming a field as measures are added in the greedy order, typical synthetic columns: A, share "
        "named exactly; B, share named at posterior 0.99; C, share of those right, where %s or more "
        "were named, dotted at 99 per cent. Crosses, the seven SPINEPS measures. By the bodies in view; "
        "%s columns.",
    "curve_speed":
        "Time to name one field%s, as measures are added: A, rule.py on the trapezoid's nodes, one "
        "field alone (median of %s), by bodies in view; B, three bodies, each engine with its table "
        "built once, alone (lines) and per field in a batch%s (points, median of %s).%s",
    "curve_data":
        "The rule's table re-estimated from P people, three bodies, on the same typical columns: A, "
        "share named exactly; B, share right of those named at 0.99, dotted at 99 per cent; the seven "
        "and all 32, the estimate as it is (nominal) or widened for a new person (predictive); thin "
        "lines, the table as printed on those columns.",
}


# ---- reading the record ---------------------------------------------------------------------

def rates_of(tree):
    return tree["rates"].to_dataset()


def value(ds, stat: str, arm: str, phenotype: str, subset: str, width: int) -> float:
    """One rate of the record, NaN where the record is older than the statistic."""
    if stat not in ds:
        return float("nan")
    return float(ds[stat].sel(arm=arm, phenotype=phenotype, subset=subset, width=width))


def pool_of(tree) -> List[dict]:
    return json.loads(tree.attrs["pool"])


def order_of(tree) -> List[str]:
    return json.loads(tree.attrs["order"])


def counts_of(tree) -> dict:
    return json.loads(tree.attrs["counts"])


def attr_json(tree, name: str) -> dict:
    """A JSON attribute of the record, empty where the record has none."""
    text = tree.attrs.get(name, "")
    return json.loads(text) if text else {}


# ---- formatting -----------------------------------------------------------------------------

PCT_MOST_PLACES = 6


def pct(x: float, places: int = 1) -> str:
    """A share as a percentage to the places given, with as many more as it takes, up to
    PCT_MOST_PLACES, for a share short of all not to read 100 nor one above none to read 0, so that
    100.0% and 100.00% both mean every field and 0.0% none."""
    if not np.isfinite(x):
        return "-"
    while True:
        s = "%.*f%%" % (places, 100.0 * x)
        if not 0.0 < x < 1.0 or float(s[:-1]) not in (0.0, 100.0) or places >= PCT_MOST_PLACES:
            return s
        places += 1


def pct_down(x: float, places: int = 2) -> str:
    """A lower bound as a percentage rounded down to the places given, so that it never reads above
    the bound: none wrong of 27,970 answered gives 99.9868%, at least 99.98%, not 99.99%."""
    if not np.isfinite(x):
        return "-"
    return "%.*f%%" % (places, math.floor(100.0 * x * 10 ** places) / 10 ** places)


def count(x: float) -> str:
    """A count with its thousands marked, as every table prints its counts."""
    return "{:,}".format(int(x)) if np.isfinite(x) else "-"


def ms(x: float) -> str:
    if not np.isfinite(x):
        return "-"
    return "%.2f" % x if x < 10 else "%.1f" % x if x < 100 else "%.0f" % x


def se_range(xs: Sequence[float]) -> str:
    xs = [100.0 * x for x in xs if np.isfinite(x)]
    if not xs:
        return "not recorded"
    lo, hi = min(xs), max(xs)
    return "%.2f" % hi if abs(hi - lo) < 0.005 else "%.2f to %.2f" % (lo, hi)


def points(x: float) -> str:
    """A difference of two shares in points, signed."""
    return "-" if not np.isfinite(x) else "%+.1f" % (100.0 * x)


def se_points(x: float) -> str:
    return "-" if not np.isfinite(x) else "%.2f" % (100.0 * x)


def precision_cell(ds, arm: str, phenotype: str, subset: str, width: int, ses: bool = False) -> str:
    """The precision at 0.99, with its exact 95 per cent lower bound beside it, rounded down, where
    no answered field is wrong, in place of a standard error of 0; with ses, its two standard errors
    in points otherwise, clustered by column and with the tables (the data axis)."""
    p = value(ds, "precision", arm, phenotype, subset, width)
    lower = value(ds, "precision_lower", arm, phenotype, subset, width)
    if np.isfinite(lower):
        return "%s (at least %s)" % (pct(p, 2), pct_down(lower, 2))
    if ses and np.isfinite(p):
        return "%s (%s / %s)" % (pct(p, 2), se_points(value(ds, "precision_se", arm, phenotype, subset, width)),
                                 se_points(value(ds, "precision_se_tables", arm, phenotype, subset, width)))
    return pct(p, 2)


BOUND_NOTE = ("Where no field named at 0.99 was wrong, the precision is followed by its exact two-sided 95 per cent "
              "lower bound (Clopper-Pearson, the answered fields counted as independent trials), rounded down, in "
              "place of a standard error of 0.")
DATA_BOUND_NOTE = (BOUND_NOTE + " Every table answers the same fields, so a row of several tables counts the "
                   "fields of the one that answered fewest, not each field once for every table that answered it.")


def bounded(ds, cells: Sequence[tuple]) -> bool:
    """Whether any of the cells (arm, phenotype, subset, width) prints a lower bound."""
    return any(np.isfinite(value(ds, "precision_lower", *c)) for c in cells)


def rows_md(header: Sequence[str], align: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(align) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


# ---- the tables -----------------------------------------------------------------------------

def table_curve(tree) -> List[str]:
    ds = rates_of(tree)
    kinds = {m["key"]: m["kind"] for m in pool_of(tree)}
    order = order_of(tree)
    rows, ses, precision_ses = [], [], []
    for k, key in enumerate(order, 1):
        sub = "prefix-%02d" % k
        cells = [str(k), "`%s`" % key, kinds[key]]
        cells += [pct(value(ds, "exact", "nominal", "typical", sub, n)) for n in WIDTHS]
        for n in (3, 9):
            cells += [pct(value(ds, "answered", "nominal", "typical", sub, n)),
                      precision_cell(ds, "nominal", "typical", sub, n)]
            if value(ds, "errors", "nominal", "typical", sub, n) > 0:
                precision_ses.append(value(ds, "precision_se", "nominal", "typical", sub, n))
        cells.append(pct(value(ds, "floored", "nominal", "typical", sub, 9)))
        rows.append(cells)
        ses += [value(ds, "exact_se", "nominal", "typical", sub, n) for n in WIDTHS]
    out = rows_md(["Measures", "Added", "Kind", "Named exactly, 1 body", "3 bodies", "9 bodies",
                   "Named at 0.99, 3 bodies", "Right of those", "Named at 0.99, 9 bodies", "Right of those",
                   "Fields with a value at the floor, 9 bodies"],
                  ["---:", "---", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"], rows)
    n = value(ds, "n_columns", "nominal", "typical", "prefix-01", 1)
    erred = ("where a field named at 0.99 was wrong, %s points" % se_range(precision_ses) if precision_ses
             else "no row had a field named at 0.99 wrong")
    out += ["", "%s typical columns; the standard errors of the shares named exactly, clustered by column, are %s points, "
            "and of the precision at 0.99, %s. %s" % (count(n), se_range(ses), erred, BOUND_NOTE)]
    return out


def members_of(tree, sub: str) -> frozenset:
    m = tree["subsets"].to_dataset()["member"].sel(subset=sub)
    return frozenset(np.asarray(m["measure"].values)[np.asarray(m.values, bool)].tolist())


def subset_order(tree) -> List[str]:
    """The named subsets in the table's order, less each rung of the ladder that is another row
    under its own name: the first rung is the seven and the pedicles, the last is all 32."""
    subs = tree["subsets"].to_dataset()["subset"].values.tolist()
    named = ["seven"] + ["seven+" + f for f in FAMILIES] + ["ladder-" + f for f in FAMILIES]
    named += ["lengths", "seven+areas", "seven+angles", "ap", "lateral", "ap+lateral", "all"]
    named = [s for s in named if s in subs]
    others = {members_of(tree, s) for s in named if not s.startswith("ladder-")}
    return [s for s in named if not (s.startswith("ladder-") and members_of(tree, s) in others)]


def joined(names: Sequence[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def subset_name(sub: str) -> str:
    if sub.startswith("seven+") and sub[6:] in FAMILY_NAME:
        return "the seven and %s" % FAMILY_NAME[sub[6:]]
    if sub.startswith("ladder-"):
        i = FAMILIES.index(sub[7:])
        return "the seven, " + joined([FAMILY_NAME[f] for f in FAMILIES[:i + 1]])
    return SUBSET_NAME[sub]


def table_subsets(tree) -> List[str]:
    ds = rates_of(tree)
    members = tree["subsets"].to_dataset()
    rows = []
    for sub in subset_order(tree):
        cells = [subset_name(sub), str(int(members["member"].sel(subset=sub).sum()))]
        cells += [pct(value(ds, "exact", "nominal", "typical", sub, n)) for n in WIDTHS]
        cells += [pct(value(ds, "answered", "nominal", "typical", sub, HEADLINE)),
                  precision_cell(ds, "nominal", "typical", sub, HEADLINE)]
        rows.append(cells)
    out = rows_md(["Measures scored", "Count", "Named exactly, 1 body", "3 bodies", "9 bodies",
                   "Named at 0.99, 3 bodies", "Right of those"],
                  ["---", "---:", "---:", "---:", "---:", "---:", "---:"], rows)
    if bounded(ds, [("nominal", "typical", sub, HEADLINE) for sub in subset_order(tree)]):
        out += ["", BOUND_NOTE]
    return out


def arm_names(ds) -> List[str]:
    return [a for a in ds["arm"].values.tolist()]


ARM_NAME = {"nominal": "As assumed", "errors-0.5": "Every error halved, in the columns and the rule",
            "errors-2": "Every error doubled, in the columns and the rule",
            "correlated": "Offsets correlated 0.4 between measures, the rule unaware"}


def table_arms(tree) -> List[str]:
    ds = rates_of(tree)
    rows, shown = [], []
    for arm in ("nominal", "errors-0.5", "errors-2", "correlated"):
        if arm not in arm_names(ds):
            continue
        cells = [ARM_NAME[arm]]
        for sub in ("seven", "prefix-32"):
            for n in (3, 9):
                cells += [pct(value(ds, "exact", arm, "typical", sub, n)), precision_cell(ds, arm, "typical", sub, n)]
                shown.append((arm, "typical", sub, n))
        rows.append(cells)
    out = rows_md(["Columns and rule", "Seven, named exactly, 3 bodies", "Right of those named at 0.99",
                   "Seven, 9 bodies", "Right at 0.99", "All 32, 3 bodies", "Right at 0.99", "All 32, 9 bodies",
                   "Right at 0.99"], ["---"] + ["---:"] * 8, rows)
    out += ["", "Each row is scored on columns of its own: the errors' rows on the first row's patients with every "
            "error scaled, the correlated row on columns drawn in one stream from seed 331. Its rule, which takes "
            "the measures as independent, does not know the correlation, so the row shows how that rule fares on "
            "correlated columns and whether its answers at 0.99 stay right; its difference from the first row is "
            "not what treating the measures as independent costs, which needs a rule that knows the correlation "
            "scored on the same columns, not built here."]
    if bounded(ds, shown):
        out += ["", BOUND_NOTE]
    return out


PRINTED = "people-printed"


def degrees_of_freedom(tree, people: Sequence[int]) -> str:
    """The table term's degrees of freedom at each number of people, from the record's settings."""
    settings = json.loads(tree.attrs["settings"])
    parts = []
    for i, p in enumerate(people):
        t = settings.get("people-%d-nominal" % p, {}).get("tables")
        if t is not None:
            parts.append("%d at %s%s" % (int(t) - 1, "{:,}".format(p), " people" if i == 0 else ""))
    return joined(parts) if parts else "not recorded"


def table_data(tree) -> List[str]:
    ds = rates_of(tree)
    arms = arm_names(ds)
    if not any(a.startswith("people-") for a in arms):
        return ["The data axis is not in this record."]
    settings = json.loads(tree.attrs["settings"])
    printed = PRINTED if PRINTED in arms else None

    def cells_of(arm: str) -> List[str]:
        out = []
        for sub in ("seven", "prefix-32"):
            x = value(ds, "exact", arm, "typical", sub, HEADLINE)
            ref = value(ds, "exact", printed, "typical", sub, HEADLINE) if printed else float("nan")
            out += ["%s (%s / %s)" % (pct(x), se_points(value(ds, "exact_se", arm, "typical", sub, HEADLINE)),
                                      se_points(value(ds, "exact_se_tables", arm, "typical", sub, HEADLINE))),
                    "-" if arm == printed else points(x - ref),
                    precision_cell(ds, arm, "typical", sub, HEADLINE, ses=True)]
        return out
    rows, shown = [], []
    if printed:
        rows.append(["as printed", "-", "1"] + cells_of(printed))
        shown += [(printed, "typical", sub, HEADLINE) for sub in ("seven", "prefix-32")]
    people = [p for p in PEOPLE if "people-%d-nominal" % p in arms]
    for p in people:
        for rule in ("nominal", "predictive"):
            arm = "people-%d-%s" % (p, rule)
            if arm not in arms:
                continue
            rows.append(["{:,}".format(p), rule, str(settings.get(arm, {}).get("tables", ""))] + cells_of(arm))
            shown += [(arm, "typical", sub, HEADLINE) for sub in ("seven", "prefix-32")]
    first = printed or next(a for a in arms if a.startswith("people-"))
    n = int(value(ds, "n_columns", first, "typical", "seven", HEADLINE))
    out = rows_md(["People", "Rule", "Tables", "Seven, named exactly, 3 bodies", "Against the table as printed, points",
                   "Right of those named at 0.99", "All 32, 3 bodies", "Against the table as printed, points",
                   "Right at 0.99"], ["---:", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:"], rows)
    against = ("and so is the table as printed, the first row, against which every other row is read; a difference "
               "is paired on the same fields, and its own standard error is not recorded" if printed else
               "and the table as printed is not scored on them in this record, so no row has a difference beside it")
    out += ["", "Each table is scored on the same %s typical columns, the first of the nominal arm's, %s." % (count(n), against),
            "In brackets, standard errors in points: clustered by column, the tables drawn held fixed / counting the "
            "variation between tables too (columns and tables crossed, the two-way estimate), on one degree of freedom "
            "fewer than the tables: %s; the table as printed is one fixed table, with no such term."
            % degrees_of_freedom(tree, people)]
    if bounded(ds, shown):
        out += ["", DATA_BOUND_NOTE]
    return out


ANOMALOUS_WIDTHS = (3, 5, 9)


def table_anomalous(tree) -> List[str]:
    ds = rates_of(tree)
    rows = []
    for ph in ("typical",) + ANOMALOUS:
        cells = [PHENOTYPE_NAME[ph]]
        for sub in ("seven", "prefix-32"):
            for n in ANOMALOUS_WIDTHS:
                cells.append("%s / %s" % (pct(value(ds, "exact", "nominal", ph, sub, n)),
                                          pct(value(ds, "within_one", "nominal", ph, sub, n))))
        rows.append(cells)
    out = rows_md(["Spine", "Seven, 3 bodies: exact / within one", "Seven, 5 bodies", "Seven, 9 bodies",
                   "All 32, 3 bodies", "All 32, 5 bodies", "All 32, 9 bodies"], ["---"] + ["---:"] * 6, rows)
    return out + ["", ANOMALOUS_NOTE] + [""] + table_anomalous_precision(ds)


ANOMALOUS_NOTE = (
    "A field is judged by its own column's names, so a T13 or an L6 is never named right. On a "
    "spine with a thirteenth rib-bearing body those names are the rib reading, which calls the "
    "thirteenth rib-bearing body T13 where the count from C2 calls it L1; with a rib on L1 or no rib on "
    "T12 they are the count from C2, under which the rib-bearing L1 stays L1 and the ribless T12 stays "
    "T12 where the rib reading calls them T13 and L1; on four- and six-lumbar spines the two agree. "
    "Within one level is read on a half-step scale on which a T13 sits half-way between T12 and L1 and an "
    "L6 one below L5, so on a T13 spine a T12 called L1, or an L1 called T12, counts as within one level "
    "though the two are two bodies apart.")


def columns_scored(ds) -> str:
    """The columns the anomalous tables score, the typical ones and each anomalous spine's, with
    any spine the record did not score named, its cells a dash."""
    def count(ph):
        return value(ds, "n_columns", "nominal", ph, "seven", HEADLINE)
    scored = [ph for ph in ANOMALOUS if np.isfinite(count(ph))]
    each = sorted({int(count(ph)) for ph in scored})
    typical = count("typical")
    text = "{:,} typical columns".format(int(typical)) if np.isfinite(typical) else "no typical columns"
    if each:
        text += " and %s columns of each anomalous spine%s" % (joined(["{:,}".format(c) for c in each]),
                                                               "" if len(scored) == len(ANOMALOUS) else " scored")
    missing = [PHENOTYPE_NAME[ph] for ph in ANOMALOUS if ph not in scored]
    if missing:
        text += " (not scored, a dash in every cell: %s)" % joined(missing)
    return text


def table_anomalous_precision(ds) -> List[str]:
    """Whether the answers at 0.99 stay right on each anomalous spine: the share of fields named at
    0.99 and the share of those right, judged by the column's own names as the table above is."""
    rows, shown, ses = [], [], []
    for ph in ("typical",) + ANOMALOUS:
        cells = [PHENOTYPE_NAME[ph]]
        for sub in ("seven", "prefix-32"):
            for n in ANOMALOUS_WIDTHS:
                cells.append("%s / %s" % (pct(value(ds, "answered", "nominal", ph, sub, n)),
                                          precision_cell(ds, "nominal", ph, sub, n)))
                shown.append(("nominal", ph, sub, n))
                if value(ds, "errors", "nominal", ph, sub, n) > 0:
                    ses.append(value(ds, "precision_se", "nominal", ph, sub, n))
        rows.append(cells)
    out = rows_md(["Spine", "Seven, 3 bodies: named at 0.99 / right of those", "Seven, 5 bodies", "Seven, 9 bodies",
                   "All 32, 3 bodies", "All 32, 5 bodies", "All 32, 9 bodies"], ["---"] + ["---:"] * 6, rows)
    out += ["", "The share of the fields named at a posterior of 0.99, and the share of those that are right, on %s; "
            "%s." % (columns_scored(ds), "the standard errors of the share right, clustered by column, where a field "
                     "named at 0.99 was wrong, are %s points" % se_range(ses) if ses else
                     "no cell had a field named at 0.99 wrong")]
    if bounded(ds, shown):
        out += ["", BOUND_NOTE]
    return out


NOT_TIMED = ["The times are not in this record yet: `python -m schwingcheck curve speed --record` writes them."]


def timed(ds) -> bool:
    return bool(np.isfinite(np.asarray(ds[list(ds.data_vars)[0]].values, float)).any())


def filled(how: dict, key: str, given: str, otherwise: str) -> str:
    """`given` with the record's value of `key` in it, a count with its thousands marked, or
    `otherwise` where the record gives none, so that a count the record lacks is never printed in
    a count's place: unrecorded says so in a sentence of its own."""
    v = how.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, str)) or v == "":
        return otherwise
    return given % ("{:,}".format(v) if isinstance(v, int) else v)


def unrecorded(how: dict, names: Sequence[tuple]) -> str:
    """A sentence naming each of `names`, (key, name), that the record does not give, or nothing
    where it gives them all."""
    missing = [name for key, name in names if not filled(how, key, "%s", "")]
    if not missing:
        return ""
    text = joined(missing)
    return "%s%s %s not recorded." % (text[0].upper(), text[1:], "is" if len(missing) == 1 else "are")


def one_thread(how: dict) -> Optional[bool]:
    """Whether the record finds every thread pool at one thread inside the limit; None where it
    records no pool."""
    found = how.get("threads")
    return all(p["threads"] == 1 for p in found) if found else None


def threads_note(how: dict) -> str:
    """What the record says of the threads inside the limit the times were taken in."""
    found = how.get("threads")
    if not found:
        return "The threads the times were taken on are not recorded."
    off = [p for p in found if p["threads"] != 1]
    if not off:
        return "Every thread pool was at one thread inside the limit (%s)." % ", ".join(p["library"] for p in found)
    return "Not at one thread inside the limit: %s." % ", ".join("%s at %d" % (p["library"], p["threads"]) for p in off)


def machine_note(how: dict) -> str:
    m, v = how.get("machine"), how.get("versions")
    if not m or not v:
        return "The machine and the versions that timed are not recorded."
    load = m.get("load_average")
    return ("Timed on %s with %s CPUs%s; Python %s, numpy %s, scipy %s, PyTensor %s, PyMC %s, Numba %s."
            % (m.get("platform", "not recorded"), m.get("cpu_count", "not recorded"),
               ", load average %s at the end" % " / ".join("%.2f" % x for x in load) if load else "",
               v.get("python"), v.get("numpy"), v.get("scipy"), v.get("pytensor"), v.get("pymc"), v.get("numba")))


SPEED_COUNTS = (("calls", "the number of single calls"), ("batch", "the batch's size"),
                ("batches", "the number of batch calls"), ("columns", "the number of columns"))


def speed_note(how: dict) -> str:
    """The speed table's note: how the times were taken, from the record's speed attribute."""
    first = ("Milliseconds to name one field, each engine's table built beforehand: alone, the median of %s / per "
             "field in a batch%s, the median of %s after one that warms them, on the fields of %s."
             % (filled(how, "calls", "%s calls", "its calls"), filled(how, "batch", " of %s", ""),
                filled(how, "batches", "%s such calls", "such calls"),
                filled(how, "columns", "%s scoring columns", "the first scoring columns")))
    return " ".join(s for s in (first, unrecorded(how, SPEED_COUNTS), threads_note(how), machine_note(how)) if s)


def speed_caption(how: dict) -> str:
    """The speed figure's caption, its counts and its threads read from the record's speed
    attribute as the table's note reads them, and what the record does not give named in a
    sentence of its own, in sixty words at most."""
    threads = one_thread(how)
    missing = ["the threads"] if threads is None else []
    missing += [name for key, name in (("calls", "single calls"), ("batch", "batch size"), ("batches", "batch calls"))
                if not filled(how, key, "%s", "")]
    return CAPTIONS["curve_speed"] % ({True: ", one thread", False: ", not single-threaded", None: ""}[threads],
                                      filled(how, "calls", "%s calls", "its calls"), filled(how, "batch", " of %s", ""),
                                      filled(how, "batches", "%s calls", "its calls"),
                                      " Not recorded: %s." % joined(missing) if missing else "")


def table_speed(tree) -> List[str]:
    sp = tree["speed"].to_dataset()
    if not timed(sp):
        return NOT_TIMED
    how = attr_json(tree, "speed")
    ks = [k for k in SPEED_MEASURES if k in sp["measures"].values.tolist()]
    rows = []
    for e in sp["engine"].values.tolist():
        for n in sp["width"].values.tolist():
            cells = [ENGINE_NAME.get(e, e), str(n)]
            for k in ks:
                a = float(sp["median_ms"].sel(engine=e, measures=k, width=n))
                b = float(sp["batch_ms"].sel(engine=e, measures=k, width=n))
                cells.append("%s / %s" % (ms(a), ms(b)))
            rows.append(cells)
    return rows_md(["Engine", "Bodies"] + ["%d measure%s" % (k, "" if k == 1 else "s") for k in ks],
                   ["---", "---:"] + ["---:"] * len(ks), rows) + ["", speed_note(how)]


NUTS_COUNTS = (("chains", "the number of chains"), ("draws", "the number of draws"),
               ("tune", "the number of tuning steps"), ("seed", "the seed"), ("width", "the bodies in a field"),
               ("columns", "the number of columns"), ("alone", "the field sampled alone"))


def cache_cell(r) -> str:
    """The files one NUTS run added to PyTensor's Numba cache, "-" where the record has none."""
    v = float(r["cache_files"]) if "cache_files" in r else float("nan")
    return "%d" % int(v) if np.isfinite(v) else "-"


def compiled_note(nu) -> str:
    """Which NUTS runs compiled some of their graph and which found it compiled already, by the
    files each added to PyTensor's Numba cache (curve.nuts_run's cache_files), as the record gives
    them, or, for a record older than that count, that the record does not say."""
    found = {"compiled": [], "already": [], "not recorded": []}
    for k in nu["measures"].values.tolist():
        for h in nu["how"].values.tolist():
            r = nu.sel(measures=k, how=h)
            if np.isfinite(float(r["fields"])):
                cell = cache_cell(r)
                found["not recorded" if cell == "-" else "compiled" if int(cell) > 0 else "already"].append(
                    "%d measures %s" % (k, h))
    if not found["compiled"] and not found["already"]:
        return "Whether each run compiled its graph or found it compiled already is not recorded."
    out = ("A run that added files to PyTensor's Numba cache (base_compiledir/numba) compiled some of its graph, "
           "and its setup holds that compile; one that added none found its graph compiled already, by an earlier "
           "run or process, and its setup is the shorter for it. Compiled: %s; compiled already: %s."
           % (joined(found["compiled"]) if found["compiled"] else "none",
              joined(found["already"]) if found["already"] else "none"))
    if found["not recorded"]:
        out += " The cache's files are not recorded for %s." % joined(found["not recorded"])
    return out


def table_nuts(tree) -> List[str]:
    nu = tree["nuts"].to_dataset()
    if not timed(nu):
        return NOT_TIMED
    if "how" not in nu.dims:
        return ["The NUTS numbers of this record are in an older layout: "
                "`python -m schwingcheck curve speed --record` takes them again."]
    how = attr_json(tree, "nuts")
    ks = nu["measures"].values.tolist()
    places = nu["place"].values.tolist()
    rows = []
    for k in ks:
        for h in nu["how"].values.tolist():
            r = nu.sel(measures=k, how=h)
            if not np.isfinite(float(r["fields"])):
                continue
            gap = np.asarray(r["gap"].values, float)
            worst = places[int(np.nanargmax(gap))] if np.isfinite(gap).any() else "-"
            rows.append([str(k), h if h == "together" else "%s, at %s" % (h, worst), "%d" % int(r["fields"]),
                         "%.2f" % float(r["build_s"]), "%.1f" % float(r["setup_s"]), "%.2f" % float(r["sample_s"]),
                         "%.2f" % float(r["posterior_s"]), "%.1e at %s" % (float(r["max_gap"]), worst),
                         "%.2f" % float(r["max_rhat"]), "%d" % int(r["divergences"]), cache_cell(r)])
    out = rows_md(["Measures", "Sampled", "Fields", "Build, s a call", "Setup, s a call", "NUTS's loop, s a field",
                   "Posterior, s a field", "Largest gap from the exact posterior", "Largest R-hat", "Divergences",
                   "Files added to the Numba cache"],
                  ["---:", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:", "---:"], rows)
    together = nu.sel(how="together")
    per = []
    for f, place in enumerate(places):
        cells = [place]
        for k in ks:
            g, r = float(together["gap"].sel(measures=k)[f]), float(together["rhat"].sel(measures=k)[f])
            cells.append("-" if not np.isfinite(g) else "%.1e (%.2f)" % (g, r))
        per.append(cells)
    out += [""] + rows_md(["Place"] + ["%d measures: gap (R-hat)" % k for k in ks], ["---"] + ["---:"] * len(ks), per)
    first = ("NUTS on the naming model, %s of %s after %s, %son one field%s at each place, the i-th place's from the "
             "i-th %s, sampled together in one model, and on %s alone."
             % (filled(how, "chains", "%s chains", "chains"), filled(how, "draws", "%s draws", "draws"),
                filled(how, "tune", "%s tuning steps", "tuning steps"), filled(how, "seed", "seed %s, ", ""),
                filled(how, "width", " of %s bodies", ""), filled(how, "columns", "of %s scoring columns", "scoring column"),
                filled(how, "alone", "the field at %s", "one of them")))
    rest = ("The setup is a call's, whatever its fields: compiling the model's log density and gradient, which every "
            "new set of fields pays again, since the observed values are constants of the compiled graph, and which a "
            "compiled graph already on disk shortens. The loop is NUTS's own, tuning and draws; the posterior is the "
            "second call of the average over the draws, the first having compiled it. The gap is the largest "
            "difference over places between NUTS's posterior and the exact rule's, below for each field sampled "
            "together.")
    out += ["", " ".join(s for s in (first, unrecorded(how, NUTS_COUNTS), rest, compiled_note(nu), threads_note(how))
                         if s)]
    return out


FLOOR_ARMS = ("nominal", "errors-0.5", "errors-2", "correlated")
FLOOR_NOTE = ("A value at the floor is one the generator drew below %g, in its measure's own units, and set to %g "
              "(columns.FLOOR). The rule's likelihood has no floor, so at such a value the rule is not the "
              "generator's posterior. The values counted are those of the measures that scale with the size, at every "
              "level of every column of the arm and spine; Columns touched counts the columns that hold at least one such "
              "value, and Most at gives the three measures and levels that hold the most, by count, the first by name "
              "among equal counts.")


def floor_rows(keys: Sequence[str]) -> List[str]:
    """The floor's rows in the order the other tables give them: the typical columns of each arm in
    the arms' table's order, then the nominal arm's anomalous spines in the anomalous table's, and
    any other after them by name."""
    rank = {"%s/typical" % arm: i for i, arm in enumerate(FLOOR_ARMS)}
    rank.update({"nominal/%s" % ph: len(FLOOR_ARMS) + i for i, ph in enumerate(ANOMALOUS)})
    return sorted(keys, key=lambda k: (rank.get(k, len(rank)), k))


def most_at(where: Dict[str, int], n: int = 3) -> str:
    """The n measures and levels that hold the most values at the floor, the most first and by name
    among equals, as columns.floor_hits orders them; the record keeps them as JSON sorted by name,
    so the order is taken again here."""
    top = sorted(where.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    return ", ".join("`%s` %d" % kv for kv in top) or "none"


def table_floor(tree) -> List[str]:
    if "floor" not in tree.attrs:
        return ["The floor's counts are not in this record, which is older than they are."]
    fl = json.loads(tree.attrs["floor"])
    rows = []
    for key in floor_rows(list(fl)):
        arm, ph = key.split("/")
        f = fl[key]
        rows.append([ARM_NAME.get(arm, arm), PHENOTYPE_NAME[ph], "{:,}".format(f["values"]), "{:,}".format(f["of"]),
                     "{:,}".format(f["columns"]), most_at(f["where"])])
    return rows_md(["Columns", "Spine", "Values at the floor", "Of", "Columns touched", "Most at"],
                   ["---", "---", "---:", "---:", "---:", "---"], rows) + ["", FLOOR_NOTE % (C.FLOOR, C.FLOOR)]


MAKERS = {"curve": table_curve, "subsets": table_subsets, "arms": table_arms, "data": table_data,
          "anomalous": table_anomalous, "speed": table_speed, "nuts": table_nuts, "floor": table_floor}


def block(tree, name: str) -> str:
    return "\n".join(["<!-- curve:%s -->" % name] + MAKERS[name](tree) + ["<!-- /curve:%s -->" % name])


def tables(tree) -> str:
    return "\n\n".join(block(tree, name) for name in TABLES)


def readme_blocks(text: str) -> Dict[str, str]:
    out = {}
    for m in re.finditer(r"<!-- curve:([a-z]+) -->\n.*?\n<!-- /curve:\1 -->", text, re.S):
        out[m.group(1)] = m.group(0)
    return out


def check_readme(tree, readme: Optional[str] = None) -> List[str]:
    """What differs between the README's tables and the record's: one line per table missing,
    stale or written twice; the package's README unless another is named."""
    with open(readme or README, encoding="ascii") as fh:
        text = fh.read()
    have = readme_blocks(text)
    stale = []
    for name in TABLES:
        want = block(tree, name)
        if text.count("<!-- curve:%s -->" % name) > 1:
            stale.append("table %s: written more than once" % name)
        elif name not in have:
            stale.append("table %s: not in the README" % name)
        elif have[name] != want:
            stale.append("table %s: differs from the record's (python -m schwingcheck curve table)" % name)
    return stale


# ---- the figures ----------------------------------------------------------------------------

PRECISION_DRAWN = 1000      # the fields named at 0.99 that a share right must rest on to be drawn


def accuracy_point(ds, stat: str, sub: str, n: int) -> dict:
    """One point of the accuracy figure, the nominal arm's typical columns: the record's share in
    per cent, the fields it rests on (those named at 0.99 for the share right, every field
    otherwise) and whether it is drawn. A share right resting on fewer than PRECISION_DRAWN fields
    is not drawn: on an axis from 99 to 100 per cent its 100 per cent from a handful of fields,
    one field at two measures and one body, would read as a result."""
    fields = value(ds, "n_answered" if stat == "precision" else "n_fields", "nominal", "typical", sub, n)
    drawn = stat != "precision" or fields >= PRECISION_DRAWN
    return {"percent": 100 * value(ds, stat, "nominal", "typical", sub, n),
            "fields": int(fields) if np.isfinite(fields) else "", "drawn": "yes" if drawn else "no"}


def fig_accuracy(tree, outdir: str) -> List[str]:
    plt = style()
    ds = rates_of(tree)
    ks = list(range(1, len(order_of(tree)) + 1))
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5), constrained_layout=True)
    rows = []
    for ax, stat, title in zip(axes, ("exact", "answered", "precision"),
                               ("Named exactly", "Named at 0.99", "Right of those named")):
        for n in WIDTHS:
            points = [dict(accuracy_point(ds, stat, "prefix-%02d" % k, n), panel=title, bodies=n, measures=k,
                           subset="prefix-%02d" % k) for k in ks]
            seven = dict(accuracy_point(ds, stat, "seven", n), panel=title, bodies=n, measures=7, subset="seven")
            ys = [p["percent"] if p["drawn"] == "yes" else float("nan") for p in points]
            ax.plot(ks, ys, color=INK, label=body_label(n), markersize=2.6, **WIDTH_STYLE[n])
            if seven["drawn"] == "yes":
                ax.plot([7], [seven["percent"]], linestyle="none", marker="x", color=INK, markersize=5)
            rows += points + [seven]
        ax.set_xlabel("Measures")
        ax.set_xlim(0, ks[-1] + 1)
        letter(ax, "ABC"["exact answered precision".split().index(stat)], title)
        if stat == "precision":
            ax.axhline(99.0, color=INK, linewidth=0.5, linestyle=":")
    axes[0].set_ylabel("Per cent of fields")
    axes[1].set_ylabel("Per cent of fields")
    axes[2].set_ylabel("Per cent right")
    axes[0].plot([], [], linestyle="none", marker="x", color=INK, markersize=5, label="the seven")
    axes[0].legend(loc="lower right")
    name = "curve_accuracy"
    caption = CAPTIONS[name] % ("{:,}".format(PRECISION_DRAWN),
                                "{:,}".format(int(value(ds, "n_columns", "nominal", "typical", "prefix-01", 1))))
    order = ("panel", "bodies", "measures", "subset", "percent", "fields", "drawn")
    return save(fig, outdir, name, caption) + [write_csv(outdir, name, [{k: r[k] for k in order} for r in rows])]


def fig_speed(tree, outdir: str) -> List[str]:
    plt = style()
    from matplotlib.ticker import FuncFormatter
    sp = tree["speed"].to_dataset()
    ks = sp["measures"].values.tolist()
    fig, (a, b) = plt.subplots(1, 2, figsize=(6.4, 2.6), constrained_layout=True)
    rows = []
    for n in sp["width"].values.tolist():
        ys = [float(sp["median_ms"].sel(engine="numpy-trapezoid", measures=k, width=n)) for k in ks]
        a.plot(ks, ys, color=INK, label=body_label(n), markersize=2.6, **WIDTH_STYLE.get(n, {}))
        rows += [{"panel": "A", "engine": "numpy-trapezoid", "bodies": n, "measures": k, "how": "alone", "ms": y}
                 for k, y in zip(ks, ys)]
    for e in sp["engine"].values.tolist():
        ys = [float(sp["median_ms"].sel(engine=e, measures=k, width=HEADLINE)) for k in ks]
        zs = [float(sp["batch_ms"].sel(engine=e, measures=k, width=HEADLINE)) for k in ks]
        st = dict(ENGINE_STYLE[e])
        b.plot(ks, ys, color=INK, label=ENGINE_NAME[e], markersize=2.6, **st)
        b.plot(ks, zs, color=INK, linestyle="none", marker=st["marker"], markerfacecolor=st["markerfacecolor"], markersize=2.6)
        rows += [{"panel": "B", "engine": e, "bodies": HEADLINE, "measures": k, "how": "alone", "ms": y} for k, y in zip(ks, ys)]
        rows += [{"panel": "B", "engine": e, "bodies": HEADLINE, "measures": k, "how": "in a batch", "ms": z} for k, z in zip(ks, zs)]
    for ax in (a, b):
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "%g" % v))      # 0.1, 1, 10, not powers of ten
        ax.set_xlabel("Measures")
        ax.set_ylabel("Milliseconds a field")
    letter(a, "A", "rule.py, one field at a time")
    letter(b, "B", "Three bodies, each engine")
    a.legend(loc="upper left")
    b.legend(loc="lower right")
    name = "curve_speed"
    return save(fig, outdir, name, speed_caption(attr_json(tree, "speed"))) + [write_csv(outdir, name, rows)]


def fig_data(tree, outdir: str) -> List[str]:
    plt = style()
    ds = rates_of(tree)
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.6), layout="constrained")
    rows = []
    styles = {("seven", "nominal"): dict(linestyle="--", marker="s", markerfacecolor="white"),
              ("seven", "predictive"): dict(linestyle=":", marker="^", markerfacecolor="white"),
              ("prefix-32", "nominal"): dict(linestyle="-", marker="o", markerfacecolor=INK),
              ("prefix-32", "predictive"): dict(linestyle="-.", marker="D", markerfacecolor=INK, markersize=3)}
    people = [p for p in PEOPLE if "people-%d-nominal" % p in arm_names(ds)]
    if PRINTED in arm_names(ds):
        for sub, st in (("seven", dict(linestyle=(0, (6, 2)), linewidth=0.6)), ("prefix-32", dict(linestyle="-", linewidth=0.6))):
            label = "%s, as printed" % ("Seven" if sub == "seven" else "All 32")
            for ax, stat in ((a, "exact"), (b, "precision")):
                y = 100 * value(ds, stat, PRINTED, "typical", sub, HEADLINE)
                ax.axhline(y, color=INK, label=label, **st)
                rows.append({"panel": "A" if stat == "exact" else "B", "subset": sub, "rule": "printed", "people": "",
                             "percent": y})
    for (sub, rule), st in styles.items():
        label = "%s, %s" % ("Seven" if sub == "seven" else "All 32", rule)
        for ax, stat in ((a, "exact"), (b, "precision")):
            ys = [100 * value(ds, stat, "people-%d-%s" % (p, rule), "typical", sub, HEADLINE) for p in people]
            ax.plot(people, ys, color=INK, label=label, **st)
            rows += [{"panel": "A" if stat == "exact" else "B", "subset": sub, "rule": rule, "people": p, "percent": y}
                     for p, y in zip(people, ys)]
    for ax in (a, b):
        ax.set_xscale("log")
        ax.set_xticks(people)
        ax.set_xticklabels(["{:,}".format(p) for p in people])
        ax.set_xlabel("People the table is estimated from")
    a.set_ylabel("Per cent named exactly")
    b.set_ylabel("Per cent right")
    b.axhline(99.0, color=INK, linewidth=0.5, linestyle=":")
    letter(a, "A", "Named exactly")
    letter(b, "B", "Right of those named at 0.99")
    fig.legend(*a.get_legend_handles_labels(), loc="outside right center")
    name = "curve_data"
    return save(fig, outdir, name, CAPTIONS[name]) + [write_csv(outdir, name, rows)]


def write_figures_md(outdir: str, record: str, written: List[str]) -> str:
    import matplotlib
    here = os.path.dirname(os.path.abspath(__file__))
    lines = ["# The build-up study's figures", "",
             "Built with `python -m schwingcheck curve figures --record %s --outdir %s`."
             % (os.path.relpath(record, T.ROOT), os.path.relpath(outdir, T.ROOT)), "",
             "- Record: `%s`, sha256 %s." % (os.path.relpath(record, T.ROOT), sha256(record))]
    for name in ("figures.py", "curve_report.py", "curve.py"):
        lines.append("- Code: `schwingcheck/%s`, sha256 %s." % (name, sha256(os.path.join(here, name))))
    lines += ["- Python %s, numpy %s, matplotlib %s; serif type %s, embedded in the PDF."
              % (platform.python_version(), np.__version__, matplotlib.__version__, SERIF[0]),
              "- The PDFs carry no creation date, so a rebuild with the same versions gives the same files; the CSVs "
              "beside them hold every number drawn.", "",
              "| Figure | Files | Caption |", "|---|---|---|"]
    names = list(dict.fromkeys(os.path.basename(p).split(".")[0] for p in written))
    for name in names:
        files = sorted(f for f in os.listdir(outdir) if f.split(".")[0] == name)
        with open(os.path.join(outdir, name + ".caption.txt"), encoding="ascii") as fh:
            caption = fh.read().strip().replace("|", "/")
        lines.append("| %s | %s | %s |" % (name, ", ".join("`%s`" % f for f in files), caption))
    path = os.path.join(outdir, "FIGURES.md")
    with open(path, "w", encoding="ascii", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


def draw_figures(tree, outdir: str, record: Optional[str] = None) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    written = fig_accuracy(tree, outdir)
    if timed(tree["speed"].to_dataset()):
        written += fig_speed(tree, outdir)
    if any(a.startswith("people-") for a in arm_names(rates_of(tree))):
        written += fig_data(tree, outdir)
    if record:
        written.append(write_figures_md(outdir, record, written))
    return written
