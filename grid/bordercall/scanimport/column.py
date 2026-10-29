"""One imported study as a column: its bodies top down, what was measured on each, and the facts
the tiers and the scores are read from; and the files a directory of imports holds.

    <out>/columns/<study>.json   the column, whole (the record every other file is written from)
    <out>/bodies.csv             one row per body and measure, every study of the directory
    <out>/fields/<study>.csv     the study as one field in the format `python -m schwingcheck name`
                                 reads: a column `body`, a column `offset` (the body's place in the
                                 study's own count, so a body missing between two seen ones leaves
                                 a gap), one column per measure in millimetres, blank where it was
                                 not taken, and '#' lines naming the study, its levels and the scale
                                 its values carry, which only `python -m scanimport name` reads
                                 (schwingcheck skips every '#' line)
    <out>/studies.csv            one row per study: the facts and the tier
    <out>/MANIFEST.json          what made the directory: the command, the code's commit, the
                                 Python and library versions the run used, the inputs' sha256
                                 (DIGESTS says how a folder's is taken), the counts

A body's name is the one its labels give it, and the study says whether those labels were
counted from C2 (`countable`): only a countable study's names are a truth anything is scored
against (the owner's rule of 2026-10-26: "I ONLY TRUST FULL SPINE C2 to PELVIS CTS!").
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from . import CERVICAL, LUMBAR, MEASURES, NOT_MEASURED, PLANES, ROOT, THORACIC

FORMAT = "bordercall-column/1"


@dataclass
class Body:
    level: str                                   # the name its labels give it, or "?"
    values: Dict[str, float] = field(default_factory=dict)
    methods: Dict[str, str] = field(default_factory=dict)
    flags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Column:
    study: Dict[str, object]
    bodies: List[Body]

    @property
    def levels(self) -> List[str]:
        return [b.level for b in self.bodies]

    def values(self, measures: List[str]) -> List[List[float]]:
        return [[b.values.get(m, math.nan) for m in measures] for b in self.bodies]

    def to_json(self) -> dict:
        bodies = []
        for b in self.bodies:
            d = asdict(b)
            d["values"] = {k: _clean(v) for k, v in b.values.items()}
            bodies.append(d)
        return {"format": FORMAT, "study": self.study, "bodies": bodies}

    @staticmethod
    def from_json(d: dict) -> "Column":
        if d.get("format") != FORMAT:
            raise ValueError("not a %s record: %r" % (FORMAT, d.get("format")))
        bodies = [Body(level=b["level"], values={k: (math.nan if v is None else float(v)) for k, v in b["values"].items()},
                       methods=dict(b.get("methods", {})), flags=dict(b.get("flags", {}))) for b in d["bodies"]]
        return Column(study=dict(d["study"]), bodies=bodies)


def own_sequence(levels: List[str]) -> List[str]:
    """The names a column holding these levels runs through, top down: seven cervical, twelve
    thoracic and T13 where the column has one, five lumbar, L6 where it has one and four where it
    shows L4 above the sacrum with no L5 (the case facts_from_levels calls four_lumbar), and the
    sacrum."""
    thor = THORACIC[:13] if "T13" in levels else THORACIC[:12]
    if "L6" in levels:
        lum = LUMBAR[:6]
    elif "L4" in levels and "sacrum" in levels and "L5" not in levels:
        lum = LUMBAR[:4]
    else:
        lum = LUMBAR[:5]
    return CERVICAL + thor + lum + ["sacrum"]


def offsets_of(levels: List[str]) -> Optional[List[int]]:
    """Each body's place in its column's own count, from the first body; None when a body is
    unnamed or out of order, since then no gap can be told from no gap."""
    seq = own_sequence(levels)
    if any(lv not in seq for lv in levels):
        return None
    pos = [seq.index(lv) for lv in levels]
    if any(b <= a for a, b in zip(pos, pos[1:])):
        return None
    return [p - pos[0] for p in pos]


def facts_from_levels(levels: List[str], expresses: Dict[str, bool]) -> Dict[str, object]:
    """What the labels alone say about the study: whether it shows C2 and the sacrum, whether its
    names run from C2 with no body missing (so they are a count from C2), and its phenotype as far
    as its scheme can express one: an anomaly its labels name, or typical only when the count runs
    from C2 to the sacrum."""
    has_c2, has_sacrum = "C2" in levels, "sacrum" in levels
    seq = own_sequence(levels)
    named = [lv for lv in levels if lv in seq]
    run_from_c2 = False
    if has_c2 and named:
        top, bottom = seq.index("C2"), max(seq.index(lv) for lv in named)
        run_from_c2 = all(seq[i] in levels for i in range(top, bottom + 1))
    n_lumbar = sum(1 for lv in levels if lv.startswith("L"))
    if "T13" in levels:
        phen = "t13"
    elif "L6" in levels:
        phen = "six_lumbar"
    elif has_sacrum and "L4" in levels and "L5" not in levels:
        phen = "four_lumbar"
    elif has_sacrum and "L5" in levels and run_from_c2:
        phen = "typical"
    else:
        phen = "unknown"            # a column not counted from C2 may hide a T13 above what it shows
    if phen == "typical" and not (expresses.get("L6", False) and expresses.get("T13", False)):
        phen = "typical_as_far_as_the_scheme_says"
    return {"has_c2": has_c2, "has_sacrum": has_sacrum, "countable": bool(run_from_c2),
            "count_basis": "labels run from C2 with no body missing" if run_from_c2 else
            ("C2 shown but a body is missing below it" if has_c2 else "no C2: the names are not a count from C2"),
            "n_lumbar": n_lumbar, "phenotype": phen, "levels": levels}


# ---- the files ----------------------------------------------------------------------------------

# How every input's digest is taken, the package's one rule, named in each manifest so a digest can
# be taken again the same way: a file's is the sha256 of its bytes; a folder's is the sha256 of one
# line per file under it, at any depth, "<path relative to the folder> <the file's sha256>\n", the
# lines sorted, so it changes with any file's bytes, name or place and with a file added or removed.
DIGESTS = ("sha256 of a file's bytes; of a folder, the sha256 of one line per file under it, its path relative "
           "to the folder, a space and its sha256, the lines sorted and each ended by a newline")


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def folder_files(path: str) -> List[str]:
    """Every file under a folder, at any depth, as paths relative to it, sorted."""
    return sorted(os.path.relpath(os.path.join(r, f), path) for r, _, fs in os.walk(path) for f in fs)


def sha256_of(path: str) -> str:
    """A file's or a folder's digest, by DIGESTS."""
    if not os.path.isdir(path):
        return file_sha256(path)
    lines = "".join("%s %s\n" % (rel, file_sha256(os.path.join(path, rel))) for rel in folder_files(path))
    return hashlib.sha256(lines.encode()).hexdigest()


def digests(path: str) -> Dict[str, str]:
    """An input's entry in a manifest: a file under its path, a folder under its path with its count
    of files, each with its digest (sha256_of)."""
    if not os.path.isdir(path):
        return {path: sha256_of(path)}
    return {"%s/ (%d files)" % (path.rstrip("/"), len(folder_files(path))): sha256_of(path)}


# The libraries whose versions a run records where it imported them, by module and by the
# distribution importlib.metadata knows them as: the mask-free mode's chords hold bit for bit only on
# the same numpy, scipy and BLAS build (intensity.py), and a pydicom decoder or Pillow changes what
# a compressed or colour file reads as.
LIBRARIES = (("numpy", "numpy"), ("scipy", "scipy"), ("nibabel", "nibabel"), ("pydicom", "pydicom"),
             ("PIL", "Pillow"))


def versions_of() -> Dict[str, object]:
    """The Python and the version of each of LIBRARIES the run imported, with numpy's BLAS where
    numpy reports it."""
    import platform
    import sys
    from importlib import metadata
    out: Dict[str, object] = {"python": platform.python_version()}
    for module, dist in LIBRARIES:
        if module in sys.modules:
            try:
                out[dist] = metadata.version(dist)
            except metadata.PackageNotFoundError:
                out[dist] = getattr(sys.modules[module], "__version__", None)
    blas = blas_of()
    if blas:
        out["blas"] = blas
    return out


def blas_of() -> Optional[str]:
    """numpy's BLAS as its build configuration names it (name and version), or None where numpy
    is not imported or does not say."""
    import sys
    np = sys.modules.get("numpy")
    try:
        deps = np.show_config(mode="dicts")["Build Dependencies"]["blas"]
        return " ".join(str(deps[k]) for k in ("name", "version") if deps.get(k))
    except Exception:                         # an older numpy has no dicts mode; a newer may move the key
        return None


def commit_of() -> Dict[str, object]:
    try:
        head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", ROOT, "status", "--porcelain", "--", "scanimport", "archive/bordercall"],
                                    capture_output=True, text=True, check=True).stdout.strip())
        return {"commit": head, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def write_column(col: Column, out: str) -> str:
    os.makedirs(os.path.join(out, "columns"), exist_ok=True)
    os.makedirs(os.path.join(out, "fields"), exist_ok=True)
    sid = str(col.study["study_id"])
    path = os.path.join(out, "columns", sid + ".json")
    with open(path, "w", newline="\n") as fh:
        json.dump(col.to_json(), fh, indent=1, sort_keys=True, allow_nan=False)
        fh.write("\n")
    write_field(col, os.path.join(out, "fields", sid + ".csv"))
    return path


def _clean(v: float) -> Optional[float]:
    return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else round(float(v), 3)


def field_bodies(col: Column) -> List[Body]:
    """The bodies a field file holds: never C1, C2 or the sacrum, which carry no measure; the named
    bodies alone where some are named, since an unnamed body among them has no place to be
    compared at; and every body, top down, where none is named."""
    bodies = [b for b in col.bodies if b.level not in NOT_MEASURED]
    if any(b.level != "?" for b in bodies):
        bodies = [b for b in bodies if b.level != "?"]
    return bodies


def write_field(col: Column, path: str) -> None:
    """The study as one field in the format bridge.read_field and `python -m schwingcheck name`
    read, headed by the scale its values carry, so a field `python -m scanimport name` names from
    its file is named as its column would be. schwingcheck skips the '#' lines and names every
    field with its scale taken as known, at the generator's spread."""
    bodies = field_bodies(col)
    offs = offsets_of([b.level for b in bodies]) if all(b.level != "?" for b in bodies) else None
    s = col.study
    with open(path, "w", newline="") as fh:
        fh.write("# study %s\n" % s["study_id"])
        fh.write("# levels %s\n" % " ".join(col.levels))
        fh.write("# countable %s\n" % bool(s.get("countable")))
        fh.write("# scale_known %s\n" % bool(s.get("scale_known", True)))
        fh.write("# scale_log_mean %r\n" % float(s.get("scale_log_mean") or 0.0))
        fh.write("# scale_log_sd %r\n" % float(s.get("scale_log_sd") or 0.0))
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["body", "offset", "level"] + MEASURES)
        for i, b in enumerate(bodies):
            v = [_clean(b.values.get(m, math.nan)) for m in MEASURES]
            w.writerow([i, offs[i] if offs else "", b.level] + ["" if x is None else x for x in v])


def read_columns(directory: str) -> List[Column]:
    cdir = os.path.join(directory, "columns")
    out = []
    for name in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        if name.endswith(".json"):
            with open(os.path.join(cdir, name)) as fh:
                out.append(Column.from_json(json.load(fh)))
    return out


STUDY_FIELDS = ["study_id", "subject_id", "source", "modality", "views", "annotation", "made_by", "scheme",
                "has_c2", "has_sacrum", "countable", "phenotype", "n_bodies", "n_lumbar", "scale_log_mean",
                "scale_log_sd", "grade", "tier", "tier_reason"]


def write_tables(directory: str, columns: List[Column]) -> None:
    """bodies.csv and studies.csv from every column of the directory. bodies.csv has a row for each
    measure a body has a value or a reason for, its own or, for a body not measured at all (C1, C2
    or the sacrum, a mask-free body bounded by one disc or left out for metal), the body's reason
    (flags["all"]), so every body is in it with why it was not measured."""
    with open(os.path.join(directory, "bodies.csv"), "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["study_id", "body", "level", "measure", "value_mm", "plane", "method", "flag"])
        for col in columns:
            for i, b in enumerate(col.bodies):
                for m in MEASURES:
                    v = _clean(b.values.get(m, math.nan))
                    why = b.flags.get(m) or ("" if v is not None else b.flags.get("all", ""))
                    if v is None and not why:
                        continue
                    w.writerow([col.study["study_id"], i, b.level, m, "" if v is None else v,
                                col.study.get("plane_of", {}).get(m, "/".join(PLANES[m]) if col.study.get("modality") == "ct" else ""),
                                b.methods.get(m, ""), why])
    with open(os.path.join(directory, "studies.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=STUDY_FIELDS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for col in columns:
            row = dict(col.study)
            row["n_bodies"] = len(col.bodies)
            row["views"] = "+".join(col.study.get("views", [])) if isinstance(col.study.get("views"), list) else col.study.get("views", "")
            w.writerow(row)


def write_run(directory: str, command: List[str], extra: Optional[dict] = None) -> None:
    """A run record for a directory a command wrote tables to without importing (tiers, compare,
    score): RUNS.json, one entry per run, so nothing in it is unaccounted for."""
    path = os.path.join(directory, "RUNS.json")
    runs = []
    if os.path.exists(path):
        with open(path) as fh:
            runs = json.load(fh).get("runs", [])
    runs.append({"command": command, **commit_of(), "versions": versions_of(), **(extra or {})})
    with open(path, "w", newline="\n") as fh:
        json.dump({"format": "bordercall-runs/1", "runs": runs}, fh, indent=1, sort_keys=True)
        fh.write("\n")


def write_manifest(directory: str, command: List[str], inputs: Dict[str, str], extra: Optional[dict] = None) -> None:
    path = os.path.join(directory, "MANIFEST.json")
    prior = {}
    if os.path.exists(path):
        with open(path) as fh:
            prior = json.load(fh)
    runs = prior.get("runs", [])
    runs.append({"command": command, "inputs": inputs, **commit_of(), "versions": versions_of(), **(extra or {})})
    cols = read_columns(directory)
    with open(path, "w", newline="\n") as fh:
        json.dump({"format": "bordercall-imports/1", "digests": DIGESTS, "runs": runs, "studies": len(cols),
                   "bodies": sum(len(c.bodies) for c in cols)}, fh, indent=1, sort_keys=True)
        fh.write("\n")
