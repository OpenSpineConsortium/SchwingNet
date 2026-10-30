"""The checked table of the four Panjabi papers: one long CSV, loaded as an xarray Dataset, and
the twelve specimens they were measured on.

    python -m schwingcheck table write     # data/panjabi_long.csv and data/panjabi_specimens.csv
    python -m schwingcheck table check     # the committed CSVs are what write would write

One row per value: the measure (mnemonics.py), its side, the level, the paper's mnemonic,
mean or sem, the value and its units, the kind (length, area or angle), the planes that can
read it, the number of specimens, the paper, the table and the provenance cell the value was
read from. Every row comes from the provenance record of item P step b, which holds what two
independent readers saw in the image of each cell, so one source feeds this table, the
archive's panjabi_full_spine.csv and every rule built here. The thoracic body table (Table 3,
printed page 892), which the first scan lacked, is read like every other table since 27
October 2026, from the one page of the owner's second scan (provenance/README.md).

The Dataset has dimensions (level, measure, side): `mean`, `sem`, `sd` (sem times the square
root of n, the population SD the generator and the rule use), `n` and `cell`, NaN where the
papers print nothing, with the kind, the units, the planes and the definition as coordinates
along `measure` and the mnemonic along (measure, side).

The specimens are the thoracic paper's Table 1: twelve fresh autopsy spines from C2 to L5, each
with its age, sex, weight, height and cause of death. The cervical, lumbar and facets papers
measured the same twelve spines, as the cervical paper says and the other two imply, and print
only their summary (SPECIMEN_SUMMARIES below). No
paper prints a measurement of one specimen, only each level's mean and standard error over the
twelve, so these covariates describe the population the table comes from and estimate no
coefficient: the PyMC model of step d conditions the size prior on height and leaves the effects
of weight and age, and any pooling of populations, to data with a measurement per patient
(TODO.md, item 5).
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import math
import os
from typing import Dict, Sequence, Tuple

import numpy as np

from . import LEVELS_C2, SIDES, UNITS
from .mnemonics import BY_MNEMONIC, DIMENSION_TABLES, MEASURE_INFO, MEASURES, MIRRORED, SPECIMENS

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROVENANCE_DIR = os.path.join(ROOT, "archive", "bordercall", "reference", "provenance")
PROVENANCE_CSV = os.path.join(PROVENANCE_DIR, "provenance.csv")
LONG_CSV = os.path.join(HERE, "data", "panjabi_long.csv")
SPECIMENS_CSV = os.path.join(HERE, "data", "panjabi_specimens.csv")

FIELDS = ["measure", "side", "level", "mnemonic", "statistic", "value", "units", "kind", "planes",
          "n", "paper", "table", "cell"]

# the thoracic paper's Table 1, one row per specimen: its column label in the paper, the name
# here, and how the printed string is read
SPECIMEN_TABLE = "thoracic-t1"
SPECIMEN_COLUMNS = [("Specimen No.", "specimen", str), ("Age", "age_years", int), ("Sex", "sex", str),
                    ("Weight (kg)", "weight_kg", int), ("Height (cm)", "height_cm", int),
                    ("Cause of death", "cause_of_death", str)]
SPECIMEN_FIELDS = [name for _, name, _ in SPECIMEN_COLUMNS] + \
    ["%s_cell" % name for _, name, _ in SPECIMEN_COLUMNS] + ["paper", "table"]
# What the other three papers print about the twelve spines in their Methods (cervical page 861,
# lumbar 299, facets 1298 and 1299): (paper, printed page, statistic, covariate, value). The
# cervical paper gives its specimens' details as the initial study's; the lumbar and facets papers
# refer to that study for the methods and print the same summary to the decimal, so they describe
# the same twelve, as the facets paper's 276 vertebrae, twelve spines of 23 levels, say too. The
# three summaries, the same 12 numbers in each paper, were read from the page images by eye, twice,
# at 100 and 200 dpi, for step c, and then by the two independent prose passes of step b, whose
# record, the provenance folder's prose.csv, tests/test_schwingcheck_table.py holds this list to
# (the first three papers have no text layer, and the facets paper's OCR layer is not read). Each
# of the three gives the weight's range as 54-85 kg, while Table 1's heaviest specimen weighs
# 84 kg; the same test holds every other statement to Table 1 and that one as the papers' own
# contradiction (SPECIMEN_CONTRADICTIONS).
_SUMMARY = (("mean", "age_years", 46.3), ("min", "age_years", 19), ("max", "age_years", 59),
            ("mean", "weight_kg", 67.8), ("min", "weight_kg", 54), ("max", "weight_kg", 85),
            ("mean", "height_cm", 167.8), ("min", "height_cm", 157), ("max", "height_cm", 178),
            ("count", "male", 8), ("count", "female", 4))
SPECIMEN_SUMMARIES = [("cervical", 861, "count", "specimens", 12), ("lumbar", 299, "count", "specimens", 12),
                      ("facets", 1298, "count", "specimens", 12)] + \
    [(paper, page, stat, cov, value) for paper, page in (("cervical", 861), ("lumbar", 299), ("facets", 1299))
     for stat, cov, value in _SUMMARY]
SPECIMEN_CONTRADICTIONS = [(paper, page, "max", "weight_kg", 85) for paper, page in
                           (("cervical", 861), ("lumbar", 299), ("facets", 1299))]


def read_csv(path: str) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _row(m, level, statistic, value, units, paper, table, cell) -> dict:
    return {"measure": m.measure, "side": m.side, "level": level, "mnemonic": m.mnemonic,
            "statistic": statistic, "value": value, "units": units, "kind": m.kind,
            "planes": " ".join(m.planes), "n": str(SPECIMENS), "paper": paper, "table": table,
            "cell": cell}


def rows_from_provenance(prov: Sequence[dict]) -> list:
    """The long table's rows: every present-study mean and standard error of the dimension
    tables, each from its cell."""
    out = []
    for r in prov:
        if r["table"] not in DIMENSION_TABLES or r["study"] != "present":
            continue
        if r["statistic"] not in ("mean", "sem") or r["value"] == "":
            continue
        m = BY_MNEMONIC.get(r["measure"])
        if m is None:
            raise KeyError("provenance names a mnemonic mnemonics.py does not: %r in %s" % (r["measure"], r["table"]))
        if r["level"] not in LEVELS_C2:
            raise ValueError("provenance row %s is at a level outside C2-L5: %r" % (r["id"], r["level"]))
        if r["kind"] != m.kind:
            raise ValueError("provenance calls %s a %s, mnemonics.py a %s" % (r["id"], r["kind"], m.kind))
        if r["pass1"] != r["pass2"] or r["agree"] != "yes":
            raise ValueError("the two readings of %s disagree: %r, %r" % (r["id"], r["pass1"], r["pass2"]))
        out.append(_row(m, r["level"], r["statistic"], r["value"], r["units"], r["paper"], r["table"], r["id"]))
    order = {lv: i for i, lv in enumerate(LEVELS_C2)}
    out.sort(key=lambda r: (MEASURES.index(r["measure"]), SIDES.index(r["side"]), order[r["level"]], r["statistic"]))
    seen = set()
    for r in out:
        key = (r["measure"], r["side"], r["level"], r["statistic"])
        if key in seen:
            raise ValueError("two rows for %s" % (key,))
        seen.add(key)
    return out


LONG_HEADER = ("# Panjabi's quantitative three-dimensional anatomy, cervical (1991), thoracic (1991),\n"
               "# lumbar (1992) and articular facets (1993): every present-study mean and standard\n"
               "# error of the dimension tables, written by `python -m schwingcheck table write` from\n"
               "# archive/bordercall/reference/provenance/provenance.csv (two readings by eye of every\n"
               "# cell). Do not edit by hand.\n")
SPECIMENS_HEADER = ("# The twelve fresh autopsy spines, C2 to L5, of Panjabi's four papers: the thoracic\n"
                    "# paper's Table 1 (printed page 889), written by `python -m schwingcheck table write`\n"
                    "# from archive/bordercall/reference/provenance/provenance.csv (two readings by eye of\n"
                    "# every cell). The papers print no measurement of one specimen. Do not edit by hand.\n")


def specimens_from_provenance(prov: Sequence[dict]) -> list:
    """One row per specimen of the thoracic paper's Table 1, in the paper's order, every value
    with the cell it was read from."""
    by_label = {label: (name, read) for label, name, read in SPECIMEN_COLUMNS}
    rows: Dict[str, dict] = {}
    for r in prov:
        if r["table"] != SPECIMEN_TABLE:
            continue
        if r["col_label"] not in by_label:
            raise KeyError("Table 1 has a column the package does not read: %r" % r["col_label"])
        if r["pass1"] != r["pass2"] or r["agree"] != "yes":
            raise ValueError("the two readings of %s disagree: %r, %r" % (r["id"], r["pass1"], r["pass2"]))
        name, read = by_label[r["col_label"]]
        row = rows.setdefault(r["row"], {"paper": r["paper"], "table": r["table"]})
        if name in row:
            raise ValueError("two cells for %s of row %s" % (name, r["row"]))
        read(r["printed"])                       # a number that does not read as one fails here
        row[name] = r["printed"]
        row["%s_cell" % name] = r["id"]
    out = [rows[k] for k in sorted(rows, key=int)]
    for row in out:
        missing = [f for f in SPECIMEN_FIELDS if f not in row]
        if missing:
            raise ValueError("specimen %s lacks %s" % (row.get("specimen"), ", ".join(missing)))
    return out


def _text(header: str, fields: Sequence[str], rows: Sequence[dict]) -> str:
    """The exact text of a written CSV: the comment header, the column line and the rows, LF."""
    buf = io.StringIO()
    buf.write(header)
    w = csv.DictWriter(buf, fieldnames=list(fields), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _long_text() -> Tuple[str, int]:
    rows = rows_from_provenance(read_csv(PROVENANCE_CSV))
    return _text(LONG_HEADER, FIELDS, rows), len(rows)


def _specimens_text() -> Tuple[str, int]:
    rows = specimens_from_provenance(read_csv(PROVENANCE_CSV))
    return _text(SPECIMENS_HEADER, SPECIMEN_FIELDS, rows), len(rows)


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(text)


def write_long_csv(path: str = LONG_CSV) -> int:
    text, n = _long_text()
    _write(path, text)
    return n


def write_specimens_csv(path: str = SPECIMENS_CSV) -> int:
    text, n = _specimens_text()
    _write(path, text)
    return n


def _differences(path: str, want: str, shown: int = 10) -> list:
    """Every line by which the committed file differs from the text write would write, the
    comment header, the column line and its order, the line endings and the last newline
    included: none when the two are the same to the byte. The first problem counts the lines
    removed and added; the first `shown` of them are quoted and the rest only counted."""
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            have = fh.read()
    except FileNotFoundError:
        return ["%s does not exist; write would write %d lines" % (os.path.relpath(path, ROOT), want.count("\n"))]
    if have == want:
        return []
    diff = [d for d in difflib.unified_diff(have.splitlines(keepends=True), want.splitlines(keepends=True), n=0)
            if d[:1] in "-+" and not d.startswith(("---", "+++"))]
    removed = sum(d.startswith("-") for d in diff)
    problems = ["%d committed lines differ from what write would write: %d to remove, %d to add"
                % (removed, removed, len(diff) - removed)]
    problems += ["%s %r" % ("committed" if d.startswith("-") else "write gives", d[1:]) for d in diff[:shown]]
    if len(diff) > shown:
        problems.append("and %d more lines" % (len(diff) - shown))
    return problems


def check_long_csv(path: str = LONG_CSV) -> list:
    """How the committed long CSV differs from what write would write now, to the byte."""
    return _differences(path, _long_text()[0])


def check_specimens_csv(path: str = SPECIMENS_CSV) -> list:
    """How the committed specimens CSV differs from what write would write now, to the byte."""
    return _differences(path, _specimens_text()[0])


def read_long_csv(path: str = LONG_CSV) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(line for line in fh if not line.startswith("#")))


def load(path: str = LONG_CSV):
    """The table as an xarray Dataset with dimensions (level, measure, side)."""
    import xarray as xr
    rows = read_long_csv(path)
    measures = [m for m in MEASURES if any(r["measure"] == m for r in rows)]
    shape = (len(LEVELS_C2), len(measures), len(SIDES))
    mean = np.full(shape, np.nan)
    sem = np.full(shape, np.nan)
    n = np.full(shape, np.nan)
    cell = np.full(shape, "", dtype=object)
    mnemonic = np.full((len(measures), len(SIDES)), "", dtype=object)
    for r in rows:
        i, j, k = LEVELS_C2.index(r["level"]), measures.index(r["measure"]), SIDES.index(r["side"])
        target = mean if r["statistic"] == "mean" else sem
        target[i, j, k] = float(r["value"])
        n[i, j, k] = float(r["n"])
        mnemonic[j, k] = r["mnemonic"]
        if r["statistic"] == "mean":
            cell[i, j, k] = r["cell"]
    info = [MEASURE_INFO[m] for m in measures]
    ds = xr.Dataset(
        {"mean": (("level", "measure", "side"), mean),
         "sem": (("level", "measure", "side"), sem),
         "sd": (("level", "measure", "side"), sem * np.sqrt(n)),
         "n": (("level", "measure", "side"), n),
         "cell": (("level", "measure", "side"), cell.astype(str))},
        coords={"level": LEVELS_C2, "measure": measures, "side": SIDES,
                "kind": ("measure", [m.kind for m in info]),
                "units": ("measure", [UNITS[m.kind] for m in info]),
                "planes": ("measure", [" ".join(m.planes) for m in info]),
                "definition": ("measure", [m.definition for m in info]),
                "mnemonic": (("measure", "side"), mnemonic.astype(str))},
        attrs={"source": os.path.relpath(path, ROOT), "sha256": sha256(path), "specimens": SPECIMENS,
               "sd": "sem * sqrt(n), the population SD"})
    return ds


def read_specimens_csv(path: str = SPECIMENS_CSV) -> list:
    return read_long_csv(path)


SPECIMENS_NOTE = ("Panjabi prints no measurement of one specimen, only each level's mean and standard error "
                  "over the twelve, so no coefficient of height, weight, age or sex can be estimated from the "
                  "papers alone. These covariates describe the population the table comes from: the size prior "
                  "of step d is conditioned on height, the effects of weight (on the discs and the facets) and "
                  "of age (on the facets) wait for data with a measurement per patient (TODO.md, item 5), and "
                  "any pooling of populations from several studies adjusts for them.")


def load_specimens(path: str = SPECIMENS_CSV):
    """The twelve specimens as an xarray Dataset with dimension `specimen`: age_years, sex,
    weight_kg, height_cm, cause_of_death and each value's provenance cell."""
    import xarray as xr
    rows = read_specimens_csv(path)
    ids = [r["specimen"] for r in rows]
    data = {}
    for _, name, read in SPECIMEN_COLUMNS[1:]:
        values = [read(r[name]) for r in rows]
        data[name] = ("specimen", np.array(values, float) if read is int else np.array(values, dtype=str))
        data["%s_cell" % name] = ("specimen", np.array([r["%s_cell" % name] for r in rows], dtype=str))
    return xr.Dataset(data, coords={"specimen": ids},
                      attrs={"source": os.path.relpath(path, ROOT), "sha256": sha256(path),
                             "paper": "thoracic", "table": "Table 1. Spine Specimen Data, printed page 889",
                             "also_measured_in": "the cervical (1991), lumbar (1992) and facets (1993) papers, "
                                                 "whose methods describe the same twelve spines",
                             "note": SPECIMENS_NOTE})


def reference(ds, selections: Sequence[Tuple[str, str]], levels: Sequence[str]) -> Dict[str, Dict[str, tuple]]:
    """{name: {level: (mean, population SD)}} for the rule and the generator, in the archive's
    shape. A selection is (measure, side); the side `mean` is the mean of right and left, of the
    means and of the standard errors alike, as the archive's pedicle and pedicle_h were built, the
    right's mean negated first for a mirrored pair (mnemonics.MIRRORED)."""
    out = {}
    for measure, side in selections:
        name = selection_name(measure, side)
        out[name] = {}
        for lv in levels:
            if side == "mean":
                r, l_ = ds["mean"].sel(level=lv, measure=measure, side="right").item(), \
                    ds["mean"].sel(level=lv, measure=measure, side="left").item()
                sr, sl = ds["sem"].sel(level=lv, measure=measure, side="right").item(), \
                    ds["sem"].sel(level=lv, measure=measure, side="left").item()
                nn = ds["n"].sel(level=lv, measure=measure, side="right").item()
                mu, sd = (mirror(measure) * r + l_) / 2.0, (sr + sl) / 2.0 * math.sqrt(nn)
            else:
                mu = ds["mean"].sel(level=lv, measure=measure, side=side).item()
                sd = ds["sd"].sel(level=lv, measure=measure, side=side).item()
            if not (np.isfinite(mu) and np.isfinite(sd)):
                raise ValueError("the table has no %s (%s) at %s" % (measure, side, lv))
            out[name][lv] = (float(mu), float(sd))
    return out


def mirror(measure: str) -> float:
    """-1 for a pair whose right side is printed with the opposite sign to the left, 1 for any
    other: the factor on the right's mean in the mean of the two."""
    return -1.0 if measure in MIRRORED else 1.0


def selection_name(measure: str, side: str) -> str:
    return measure if side == "whole" else "%s:%s" % (measure, side)


def arrays(ref: Dict[str, Dict[str, tuple]], names: Sequence[str], levels: Sequence[str]) -> Tuple[np.ndarray, np.ndarray]:
    """The means and population SDs as (measures, levels) arrays."""
    mu = np.array([[ref[nm][lv][0] for lv in levels] for nm in names], float)
    sd = np.array([[ref[nm][lv][1] for lv in levels] for nm in names], float)
    return mu, sd
