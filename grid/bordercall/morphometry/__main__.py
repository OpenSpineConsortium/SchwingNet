"""The command line: measure one mask, run a folder of masks, compare the rows with the papers'
means, check the phantom, and thin a fine mask's slices to see what thick slices do.

    python -m morphometry measure --labels 0001.nii.gz --scheme enhance --study 0001 --out rows.csv
    python -m morphometry run --masks DIR --scheme enhance --out DIR --workers 3 [--max-slice 1.25] [--lines]
    python -m morphometry compare --rows DIR/rows.csv --series series.csv --out DIR/compare.csv
    python -m morphometry phantom
    python -m morphometry thicken --labels 0004.nii.gz --scheme enhance --study 0004 --to 2.5 --out thick.csv
    python -m morphometry bench --slice 2.5
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from scanimport import geometry as G
from scanimport import volume as V

from . import measure as M

FIELDS = ["study", "level", "key", "value", "note"]
# the lines file: one row per line morphoview.lines draws, its two ends in the world's millimetres
# of the mask's affine and what each end is (morphoview.lines.ENDS), and one row more for each
# further segment a line carries (the wedge's lower plate, Eisenstein's apex-to-apex line), named
# in part, with no value of its own. The ends, the construction's value and its drawn length are
# written whole, so a reader can hold a length to its ends; measured is the row's value as the
# rows write it, to four places
LINE_FIELDS = ["study", "level", "key", "part", "rule", "panel", "value", "measured", "drawn", "status",
               "a_end", "ax", "ay", "az", "b_end", "bx", "by", "bz"]
# the frames file: each measured vertebra's frame, its origin and its three axes in the same world,
# written whole; which axis its z lies along (axis_of); and the column's line its z was turned from
FRAME_FIELDS = ["study", "level", "ox", "oy", "oz", "exx", "exy", "exz", "eyx", "eyy", "eyz", "ezx", "ezy", "ezz",
                "axis", "cx", "cy", "cz"]
# the paper-tables vocabulary's key -> ours, where the two name one measure. Panjabi's end-plate
# wedge (endplate_wedge) is the sum of the two plates' inclinations, with its own sign, and is
# not our wedge, the angle between the plates.
ALIASES = {"pedicle_incl_sag": "pedicle_angle_transverse", "pedicle_incl_trans": "pedicle_angle_sagittal"}
# a paper's own definition, where it names the extreme it read, routes its key to ours: Eisenstein
# took the canal's depth where it is least and its width where the pedicles are furthest apart
ROUTES = [("canal_ap", re.compile(r"\b(least|narrowest)\b|Eisenstein", re.I), "canal_ap_min"),
          ("canal_w", re.compile(r"\b(greatest|widest)\b", re.I), "interpedicular_max")]
# rows a population of living or dead adult people is not: another species, children, a group
# chosen by its size, a disease, or one person shown as an example
NOT_ADULT_PEOPLE = [("another species", re.compile(r"porcine", re.I)),
                    ("children", re.compile(r"^(first|second) decade$|^decade 10$|^age \d|^0-1\.5$|^1\.5-12$|^13-1[79]$", re.I)),
                    ("chosen by size", re.compile(r"largest|smallest|adjusted for|body height|body weight", re.I)),
                    ("a disease", re.compile(r"stenosis|^ds$|marfan|degenerative|dlss", re.I)),
                    ("an example", re.compile(r"example|figure", re.I))]
POOLED = ("pooled", "all", "not stated")
SOURCES = ("morphometry", "scanimport")
LINES_SOURCE = os.path.join("morphoview", "lines.py")


def number(v: object) -> object:
    """A float to four places, as every value in the rows is written; not a number as empty."""
    if isinstance(v, float):
        return ("%.4f" % v) if math.isfinite(v) else ""
    return v


def whole(v: object) -> str:
    """A float as Python writes it back to the bit; not a number as empty."""
    x = float(v)
    return repr(x) if math.isfinite(x) else ""


def write_rows(rows: Iterable[Dict[str, object]], path: str, fields: List[str] = FIELDS) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: number(x) for k, x in r.items()})


def write_atomic(rows: Iterable[Dict[str, object]], path: str, fields: List[str] = FIELDS) -> None:
    tmp = path + ".part"
    write_rows(rows, tmp, fields)
    os.replace(tmp, path)


def head_foot_axis(affine: np.ndarray) -> int:
    """The voxel axis nearest the world's head-foot direction."""
    A = np.asarray(affine, float)[:3, :3]
    return int(np.argmax(np.abs(A[2]) / np.linalg.norm(A, axis=0)))


def spacings(labels: str) -> Tuple[float, float]:
    """(the spacing along the head-foot axis, the coarsest of the three), from the header alone.
    The coarsest is not the slices' spacing on a scan cut at 0.7 mm with 0.98 mm pixels."""
    import nibabel as nib
    img = nib.load(labels)
    zooms = img.header.get_zooms()[:3]
    return float(zooms[head_foot_axis(img.affine)]), float(max(zooms))


def code_stamp(lines: bool = False) -> str:
    """The sha256 of the code that writes a study's files, every source file of morphometry and
    scanimport but their tests, and with the lines morphoview/lines.py too, so that files another
    version of the code wrote are written again. A run with the lines has a stamp of its own, so
    a study measured without them is measured again when they are asked for."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = hashlib.sha256()
    for pkg in SOURCES:
        folder = os.path.join(here, pkg)
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py"):
                h.update(name.encode() + b"\0" + read_bytes(os.path.join(folder, name)))
    if lines:
        h.update(LINES_SOURCE.encode() + b"\0" + read_bytes(os.path.join(here, LINES_SOURCE)))
    return h.hexdigest()[:16]


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def study_rows(study: str, path: str, stamp: str) -> List[Dict[str, object]]:
    hf, coarsest = spacings(path)
    return [{"study": study, "level": "study", "key": "slice_mm", "value": hf, "note": ""},
            {"study": study, "level": "study", "key": "coarsest_mm", "value": coarsest, "note": ""},
            {"study": study, "level": "study", "key": "code", "value": "", "note": stamp}]


def cmd_measure(a) -> None:
    rows = M.measure_file(a.labels, a.scheme, a.study)
    rows += study_rows(a.study, a.labels, code_stamp())
    write_rows(rows, a.out)


def line_rows(study: str, ln, ends: Dict[str, Tuple[str, str]], part_ends: Dict[str, Tuple[str, str]]
              ) -> List[Dict[str, object]]:
    """A line as its row, and a row for each further segment it carries; `ends` and `part_ends`
    say what each end is, by the line's key and by the part's name."""
    def row(part: str, a: np.ndarray, b: np.ndarray, value: object, measured: object,
            names: Tuple[str, str]) -> Dict[str, object]:
        return {"study": study, "level": ln.level, "key": ln.key, "part": part, "rule": ln.rule, "panel": ln.panel,
                "value": value, "measured": measured, "drawn": whole(np.linalg.norm(b - a)), "status": ln.status,
                "a_end": names[0], "ax": whole(a[0]), "ay": whole(a[1]), "az": whole(a[2]),
                "b_end": names[1], "bx": whole(b[0]), "by": whole(b[1]), "bz": whole(b[2])}
    out = [row("", ln.a, ln.b, whole(ln.value), float(ln.measured), ends.get(ln.key, ("", "")))]
    out += [row(name, a, b, "", "", part_ends.get(name, ("", ""))) for name, (a, b) in ln.extra.items()]
    return out


def axis_of(v) -> str:
    """Which axis the vertebra's frame has its z along (anatomy.own_axis): the end-plates'
    bisector, which the column's line within SETTLED_DEG of it stands for; one end-plate's normal,
    where one alone faces a neighbour; or the column's line through the neighbours, kept where no
    end-plate faces one, where the axis read lies more than AXIS_TURN_MAX_DEG off the line or where
    turning loses the canal, and on a vertebra the measure could not read at all."""
    if "all" in v.flags or "axis" in v.flags:
        return "column line"
    return "one plate" if "axis_one_plate" in v.flags else "bisector"


def frame_row(study: str, level: str, v) -> Dict[str, object]:
    f = v.frame
    r: Dict[str, object] = {"study": study, "level": level}
    for name, vec in (("o", f.origin), ("ex", f.ex), ("ey", f.ey), ("ez", f.ez)):
        for axis, x in zip("xyz", vec):
            r[name + axis] = whole(x)
    r["axis"] = axis_of(v)
    column = v.column_ez if v.column_ez is not None else f.ez
    for axis, x in zip("xyz", column):
        r["c" + axis] = whole(x)
    return r


def study_lines(study: str, kept: dict) -> Tuple[List[Dict[str, object]], List[Dict[str, object]],
                                                  List[Dict[str, object]]]:
    """The lines of the measures morphoview.lines draws, every one of scanimport's seven chords
    among them, on the vertebrae measure_volume built and checked against the values it wrote
    (morphoview.lines.checked), the vertebrae's frames, and a flag row naming the builder for
    each builder whose lines could not be drawn, so that a failure of the drawing loses no row of
    the measuring and no line of the other builders."""
    from morphoview import lines as LN
    lines, frames, flags = [], [], []
    verts = kept.get("verts", {})

    def build(level: str, name: str, make) -> None:
        try:
            for ln in make():
                lines.extend(line_rows(study, ln, LN.ENDS, LN.PART_ENDS))
        except Exception as e:                  # one builder's failure must not lose the others' lines
            flags.append({"study": study, "level": level, "key": "flag:lines", "value": "",
                          "note": "%s: %s: %s" % (name, type(e).__name__, e)})

    for lv, v in verts.items():
        frames.append(frame_row(study, lv, v))
        vals = kept["values"][lv]
        for name, draw in LN.vertebra_builders(v, kept["peds"][lv], vals):
            build(lv, name, lambda: LN.checked(draw(), vals))
    for (a, b), vals in kept.get("discs", {}).items():
        build("%s-%s" % (a, b), "discs", lambda: LN.checked(LN.discs(verts[a], verts[b]), vals))
    return lines, frames, flags


def side_paths(out: str) -> Tuple[str, str]:
    """A study's lines and frames files beside its rows: DIR/rows/ID.csv gives DIR/lines/ID.csv
    and DIR/frames/ID.csv."""
    rows_dir, name = os.path.split(out)
    top = os.path.dirname(rows_dir)
    return os.path.join(top, "lines", name), os.path.join(top, "frames", name)


def one_study(job: Tuple) -> Tuple[str, float, str]:
    """Measure one study and write its rows, and with the lines its lines and frames first, so
    that a rows file of this code's stamp says its lines and frames were written with it."""
    path, scheme, study, out, stamp = job[:5]
    with_lines = len(job) > 5 and bool(job[5])
    t0 = time.time()
    kept: dict = {}
    try:
        rows = M.measure_file(path, scheme, study, keep=kept if with_lines else None)
        note = ""
    except KeyboardInterrupt:
        raise
    except BaseException as e:                  # one broken mask, SystemExit included, must not stop the run
        rows, note, kept = [], "%s: %s" % (type(e).__name__, e), {}
        rows.append({"study": study, "level": "study", "key": "flag:error", "value": "", "note": note})
    if with_lines:
        lines, frames, flags = study_lines(study, kept)
        rows += flags
        lines_path, frames_path = side_paths(out)
        write_atomic(lines, lines_path, LINE_FIELDS)
        write_atomic(frames, frames_path, FRAME_FIELDS)
    rows += study_rows(study, path, stamp)
    rows.append({"study": study, "level": "study", "key": "seconds", "value": time.time() - t0, "note": ""})
    write_atomic(rows, out)
    return study, time.time() - t0, note


def stamped(out: str, stamp: str) -> bool:
    """Whether a study's CSV is there and was written by the code of this stamp, error or not."""
    if not os.path.exists(out):
        return False
    with open(out, newline="") as fh:
        return any(r["key"] == "code" and r["note"] == stamp for r in csv.DictReader(fh))


def current(out: str, stamp: str, with_lines: bool = False) -> bool:
    """Whether a study's CSV was written by this code and holds no error, and with the lines
    whether its lines and frames are there too, so it need not be measured again."""
    if not os.path.exists(out) or (with_lines and not all(os.path.exists(p) for p in side_paths(out))):
        return False
    with open(out, newline="") as fh:
        rows = list(csv.DictReader(fh))
    return (any(r["key"] == "code" and r["note"] == stamp for r in rows)
            and not any(r["key"] == "flag:error" for r in rows))


def cmd_run(a) -> None:
    """Every mask under --masks whose coarsest spacing is at most --max-slice, one CSV per study
    under --out/rows/, so a run cut short resumes where it stopped; rows.csv joins the studies
    of this run's list at the end, and only those. With --lines each study's lines and frames go
    under --out/lines/ and --out/frames/ and are joined as lines.csv and frames.csv, of the
    studies this run's code wrote alone: a lines file carries no stamp of its own, and a run a
    dead worker cut short leaves some studies' files from older code, which rows.csv tells apart
    by each study's code row and the lines could not."""
    folders = ("rows", "lines", "frames") if a.lines else ("rows",)
    for name in folders:
        os.makedirs(os.path.join(a.out, name), exist_ok=True)
    if a.lines:
        from morphoview import lines as _  # noqa: F401  fail here, before a study is measured
    stamp = code_stamp(a.lines)
    chosen, jobs = [], []
    for name in sorted(os.listdir(a.masks)):
        if not name.endswith((".nii.gz", ".nii")):
            continue
        study = name.split(".")[0]
        if a.studies and study not in a.studies.split(","):
            continue
        path = os.path.join(a.masks, name)
        if a.max_slice and spacings(path)[1] > a.max_slice:
            continue
        out = os.path.join(a.out, "rows", study + ".csv")
        chosen.append(out)
        if not current(out, stamp, a.lines):
            jobs.append((path, a.scheme, study, out, stamp, a.lines))
    if a.limit:
        jobs = jobs[:a.limit]
        chosen = [c for c in chosen if current(c, stamp, a.lines)] + [j[3] for j in jobs]
    print("%d studies chosen, %d to measure, code %s" % (len(chosen), len(jobs), stamp), flush=True)
    try:
        with ProcessPoolExecutor(a.workers) as pool:
            futures = [pool.submit(one_study, j) for j in jobs]
            for k, f in enumerate(as_completed(futures), 1):
                study, secs, note = f.result()
                print("%d/%d %s %.0f s %s" % (k, len(jobs), study, secs, note), flush=True)
    except BrokenProcessPool as e:              # a worker killed, for memory or otherwise
        print("a worker died (%s): run again to measure what is left" % e, flush=True)
    join_rows([c for c in chosen if os.path.exists(c)], os.path.join(a.out, "rows.csv"))
    if a.lines:
        written = [side_paths(c) for c in chosen if stamped(c, stamp)]
        join_rows([p for p, _ in written if os.path.exists(p)], os.path.join(a.out, "lines.csv"), LINE_FIELDS)
        join_rows([p for _, p in written if os.path.exists(p)], os.path.join(a.out, "frames.csv"), FRAME_FIELDS)


def join_rows(paths: List[str], path: str, fields: List[str] = FIELDS) -> None:
    """The files' rows under one header, written whole or not at all, so a job killed while it
    joins leaves the last whole join and never a cut one."""
    tmp = path + ".part"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for name in sorted(paths):
            with open(name, newline="") as g:
                for row in list(csv.reader(g))[1:]:
                    w.writerow(row)
    os.replace(tmp, path)


# ---- the comparison with the papers -------------------------------------------------------------

def our_values(rows_csv: str, max_slice: Optional[float]) -> Dict[Tuple[str, str], List[float]]:
    """{(our key, level): values} over the studies whose every spacing is thin enough."""
    rows = list(csv.DictReader(open(rows_csv, newline="")))
    coarsest = {r["study"]: float(r["value"]) for r in rows if r["key"] == "coarsest_mm" and r["value"]}
    out: Dict[Tuple[str, str], List[float]] = defaultdict(list)
    for r in rows:
        if r["key"].startswith("flag") or not r["value"] or r["level"] in ("study",):
            continue
        if max_slice and coarsest.get(r["study"], 99.0) > max_slice:
            continue
        try:
            v = float(r["value"])
        except ValueError:
            continue
        if math.isfinite(v):
            out[(r["key"], r["level"])].append(v)
    return out


def our_key(s: Dict[str, str]) -> str:
    """Which of our keys a paper's row is compared with: its own definition's route, else the
    vocabulary's alias, else the same key."""
    for key, pattern, ours in ROUTES:
        if s["key"] == key and pattern.search(s["definition"] + " " + s["paper"]):
            return ours
    return ALIASES.get(s["key"], s["key"])


def why_left_out(s: Dict[str, str]) -> str:
    """Why a paper's row is not a population of adult people, or empty."""
    text = (s["group"] + " " + s["cohort"]).strip()
    for why, pattern in NOT_ADULT_PEOPLE:
        if pattern.search(s["group"]) or (why == "another species" and pattern.search(text)):
            return why
    return ""


def summary_rows(out: List[Dict[str, object]]) -> Tuple[List[Dict[str, object]], Counter]:
    """The rows the summary takes: populations of adult people, one row per paper, cohort, group,
    level, key and side, the pooled sexes where the paper gives them, and both sides where it
    gives them; with the count of rows left out by reason."""
    dropped: Counter = Counter()
    keep = []
    for r in out:
        if r["left_out"]:
            dropped[r["left_out"]] += 1
        else:
            keep.append(r)
    cell = lambda r: (r["paper"], r["cohort"], r["group"], r["level"], r["key"])
    pooled = {cell(r) for r in keep if r["sex"] in POOLED}
    both = {cell(r) for r in keep if r["side"] in ("", "both", "averaged", "mean of sides")}
    chosen, seen = [], set()
    for r in keep:
        c = cell(r)
        if c in pooled and r["sex"] not in POOLED:
            dropped["a sex where the paper pools them"] += 1
        elif c in both and r["side"] in ("left", "right", "mixed"):
            dropped["one side where the paper gives both"] += 1
        elif (c, r["sex"]) in seen:
            dropped["a second row of the same cell"] += 1
        else:
            seen.add((c, r["sex"]))
            chosen.append(r)
    return chosen, dropped


def cmd_compare(a) -> None:
    """One row per (measure, level, paper's row): our mean and spread beside the paper's, the
    difference and the difference in the paper's standard deviations. The paper's technique is
    carried so that a caliper on dry bone is never read as a CT on living people."""
    ours = our_values(a.rows, a.max_slice)
    series = list(csv.DictReader(open(a.series, newline="")))
    out = []
    for s in series:
        mine = our_key(s)
        vals = ours.get((mine, s["level"]))
        if not vals or not s["mean"]:
            continue
        lit_mean = float(s["mean"])
        lit_sd = float(s["sd"]) if s["sd"] else float("nan")
        m, sd = float(np.mean(vals)), float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan")
        out.append({"key": s["key"], "ours_key": mine, "level": s["level"], "ours_n": len(vals),
                    "ours_mean": round(m, 3), "ours_sd": round(sd, 3), "paper": s["paper"], "cohort": s["cohort"],
                    "technique": s["technique"], "sex": s["sex"], "group": s["group"], "side": s["side"],
                    "left_out": why_left_out(s), "paper_mean": lit_mean, "paper_sd": s["sd"],
                    "paper_n": s["n"], "diff": round(m - lit_mean, 3),
                    "diff_in_paper_sd": round((m - lit_mean) / lit_sd, 3) if lit_sd and math.isfinite(lit_sd) and lit_sd > 0 else ""})
    with open(a.out, "w", newline="") as f:
        if out:
            w = csv.DictWriter(f, fieldnames=list(out[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(out)
    summary(out)


def summary(out: List[Dict[str, object]]) -> None:
    """Per measure: how many of the papers' rows (summary_rows), and the median difference in
    the papers' standard deviations; then how many rows were left out, and why."""
    chosen, dropped = summary_rows(out)
    by = defaultdict(list)
    for r in chosen:
        if r["diff_in_paper_sd"] != "":
            by[r["key"] if r["key"] == r["ours_key"] else "%s as %s" % (r["key"], r["ours_key"])].append(
                float(r["diff_in_paper_sd"]))
    for k in sorted(by, key=lambda k: -len(by[k])):
        z = np.array(by[k])
        print("%-40s rows %4d  median z %+.2f  |z|<1 %3.0f%%" % (k, len(z), np.median(z), 100 * np.mean(np.abs(z) < 1)))
    for why, n in dropped.most_common():
        print("left out: %4d rows, %s" % (n, why))


# ---- the phantom and thinned slices -------------------------------------------------------------

def cmd_phantom(a) -> None:
    from .tests import phantom as P
    levels = ["L2", "L3", "L4"]
    placed = P.straight(levels)
    lab, aff = P.draw(placed, spacing=tuple(a.spacing))
    rows = M.measure_volume(lab, G.VoxelGrid(aff, lab.shape), {P.LEVEL_IDS[lv]: lv for lv in levels}, "phantom",
                            pelvis=False)
    truth = P.truth(placed[1].v)
    truth.update(P.canal_profile(placed[1].v))
    for r in rows:
        if r["level"] == "L3" and r["key"] in truth and isinstance(r["value"], float):
            print("%-26s %9.2f  truth %9.2f" % (r["key"], r["value"], truth[r["key"]]))


def thinned(vol: np.ndarray, affine: np.ndarray, to_mm: float) -> Tuple[np.ndarray, np.ndarray, int, float]:
    """Every k-th slice along the head-foot axis, so the slices are about to_mm apart, as a
    scanner reconstructing thicker slices from the same patient would place them; with k and
    the spacing it gives. The coarsest axis is not the slices' on a scan cut at 0.7 mm with
    0.98 mm pixels, and Python's round takes 2.5 to 2, so 1 mm slices thinned to 2.5 came out
    2 mm apart."""
    zooms = np.linalg.norm(np.asarray(affine, float)[:3, :3], axis=0)
    ax = head_foot_axis(affine)
    k = max(1, int(math.floor(to_mm / zooms[ax] + 0.5)))
    sl = [slice(None)] * 3
    sl[ax] = slice(0, None, k)
    aff = np.array(affine, float)
    aff[:3, ax] *= k
    return vol[tuple(sl)], aff, k, float(k * zooms[ax])


def cmd_thicken(a) -> None:
    vol, grid, names, problems, _ = V.read_labels(a.labels, a.scheme)
    pelvis = a.scheme == "enhance"
    base = {(r["level"], r["key"]): r["value"] for r in M.measure_volume(vol, grid, names, a.study, pelvis=pelvis)
            if isinstance(r["value"], float)}
    rows = []
    for to in a.to:
        tv, taff, k, got_mm = thinned(vol, grid.affine, to)
        got = M.measure_volume(tv, G.VoxelGrid(taff, tv.shape), names, a.study, pelvis=pelvis)
        for r in got:
            if isinstance(r["value"], float) and (r["level"], r["key"]) in base:
                b = base[(r["level"], r["key"])]
                rows.append({"study": a.study, "level": r["level"], "key": r["key"], "value": r["value"] - b,
                             "note": "every %d slices (%.2f mm, asked %.2f) minus the original" % (k, got_mm, to)})
    write_rows(rows, a.out)


def cmd_bench(a) -> None:
    """The errors of the heights, discs and end-plate inclinations on the straight phantom over
    tilts of the column from 0 to 25 degrees and two turns of the grid, at one slice thickness:
    per measure the mean error, its standard deviation, the largest and how many were read."""
    from .tests import phantom as P
    v, levels = P.Vert(), ["L2", "L3", "L4"]
    t = P.truth(v)
    truth = {k: t[k] for k in ("h_ant", "h_mid", "h_post_inset", "endplate_incl", "endplate_lower_incl")}
    truth.update({k: P.Joint().gap for k in ("disc_h_ant", "disc_h_mid", "disc_h_post")})
    errs: Dict[str, List[float]] = {k: [] for k in truth}
    for tilt in np.arange(0.0, 26.0, 2.5):
        for turn in (0.0, 11.0):
            placed = P.straight(levels, v, tilt=((1.0, 0.2, 0.0), float(tilt)))
            lab, aff = P.draw(placed, spacing=(a.pixel, a.pixel, a.slice), grid_turn=((0.0, 0.0, 1.0), turn))
            rows = M.measure_volume(lab, G.VoxelGrid(aff, lab.shape), {P.LEVEL_IDS[lv]: lv for lv in levels},
                                    "bench", pelvis=False)
            for r in rows:
                if r["level"] in ("L3", "L2-L3", "L3-L4") and r["key"] in truth and isinstance(r["value"], float):
                    errs[r["key"]].append(r["value"] - truth[r["key"]])
    for k, e in errs.items():
        e = np.array([x for x in e if math.isfinite(x)])
        if len(e):
            print("%-22s mean %+.2f  sd %.2f  largest %.2f  n %d" % (k, e.mean(), e.std(), np.abs(e).max(), len(e)))


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(prog="python -m morphometry", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--labels", required=True)
    m.add_argument("--scheme", default="enhance")
    m.add_argument("--study", required=True)
    m.add_argument("--out", required=True)
    r = sub.add_parser("run")
    r.add_argument("--masks", required=True)
    r.add_argument("--scheme", default="enhance")
    r.add_argument("--out", required=True)
    r.add_argument("--workers", type=int, default=2)
    r.add_argument("--max-slice", type=float, default=None)
    r.add_argument("--studies", default="")
    r.add_argument("--limit", type=int, default=0)
    r.add_argument("--lines", action="store_true",
                   help="also write the lines of the measures morphoview.lines draws and each vertebra's frame")
    c = sub.add_parser("compare")
    c.add_argument("--rows", required=True)
    c.add_argument("--series", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--max-slice", type=float, default=None)
    ph = sub.add_parser("phantom")
    ph.add_argument("--spacing", type=float, nargs=3, default=[0.8, 0.8, 1.0])
    t = sub.add_parser("thicken")
    t.add_argument("--labels", required=True)
    t.add_argument("--scheme", default="enhance")
    t.add_argument("--study", required=True)
    t.add_argument("--to", type=float, nargs="+", default=[2.5, 5.0])
    t.add_argument("--out", required=True)
    b = sub.add_parser("bench")
    b.add_argument("--slice", type=float, default=2.5)
    b.add_argument("--pixel", type=float, default=0.86)
    a = p.parse_args(argv)
    {"measure": cmd_measure, "run": cmd_run, "compare": cmd_compare, "phantom": cmd_phantom,
     "thicken": cmd_thicken, "bench": cmd_bench}[a.cmd](a)


if __name__ == "__main__":
    main()
