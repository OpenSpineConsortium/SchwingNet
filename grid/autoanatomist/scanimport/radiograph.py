"""A radiograph's corner annotation to a column: the chords four corners give, in millimetres.

    python -m scanimport ingest-xr --xr lateral.json --xr ap.json --study f0001 --source aasce \
        --out imports/aasce

The annotation is SchwingNet's X-ray format, "schwingnet-spine-xr/1" (SchwingNet
docs/research/xr-annotation-format.md): one JSON per image, four corners per body in the order
superior-left, superior-right, inferior-right, inferior-left as the image is shown head up,
each with its visibility, and the body's level as one of the 27 names. Four corners give, by
view:

- AP: the superior and inferior end-plate lines, EPWu and EPWl (corner 1 to 2, corner 4 to 3).
- lateral: the same lines as depths, EPDu and EPDl, and the posterior height VBHp, from the
  superior to the inferior corner of the posterior side, which needs to know which side of the
  image is anterior: the image's `anterior` field ("left" or "right"), or --anterior. With
  neither, VBHp is not taken and the flag says so; the depths need no side.

The canal is not in four corners. A body may carry, beside its corners, an optional `chords`
object naming a measure and two points, for any measure the corners do not give and the view
shows: {"canal_w": [[x1, y1], [x2, y2]]} for the interpedicular distance on an AP or
{"canal_ap": [...]} for the depth of the canal on a lateral (the posterior body wall to the
spinolaminar line), and likewise tp_span on an AP and spinous_length on a lateral, which are kept
in the record only (the package's EXTRA). A chord the corners give, or one on a view that does
not show it, is not read and its flag says so. This is the one addition to version 1 the importer
reads, and an annotation without it loses nothing.

A corner that is null or marked not visible gives no chord, never a guessed one. C1, C2 and the
sacrum are named and kept, never measured, as on a CT: the rule's column runs from C3 to L5. A
body named "?" keeps its place in its view, top down by the mean height of its corners on the
image as shown head up, with its chords and no name. A level named twice on one view is a
mistake the importer cannot settle, so both bodies are kept as "?" and the study says why.

MILLIMETRES, AND THE MAGNIFICATION. A film's pixel is a length at the detector, `pixel_mm`; the
body sits nearer the source, so its shadow is magnified by m = source-to-image distance over
source-to-object distance: against CT or MRI, vertebral bodies on lateral digital films were
magnified 1.06 to 1.63, more than the nominal 1.1 to 1.2 (Ravi and Rampersaud 2009, the report's
row D7). A chord in millimetres is pixels times pixel_mm over m. m is rarely recorded, so it
enters the rule as what it is, a scale on every chord at once, which the rule already integrates
over as the patient's size (archive/bordercall/exact.py): the chords are divided by a nominal m0
and the study carries the spread of log m, which bridge.py adds to the size spread. The defaults,
m0 = 1.26, midway between that study's cervical and lumbar means of 1.21 and 1.31, and a spread of
0.10 in log m (m from 1.03 to 1.54 within two spreads), are a choice stated and sourced in
readers.py (DEFAULT_MAGNIFICATION) and recorded in every study, to be replaced by the image's own
geometry where its header has it (`--magnification`, `--magnification-sd`). An image with no
pixel_mm has no millimetres at all: its chords stay in pixels, the study says its scale is
unknown, and the rule names it from the chords' proportions alone (bridge.py, a flat prior on the
scale). A pixel_mm that is not a positive length (zero, negative or not a number) is refused,
never read as a scale. Each view's pixel is recorded as its annotation states it
(pixel_mm_stated) and as its chords were scaled, at the detector and at the patient
(pixel_mm_at_detector, pixel_mm_at_patient), since film.py may take the scale from the image's
own header instead of the annotation. An annotation that states no modality (absent, null or
blank) is read as film, this module's own choice.

Two views of one study (an AP and a lateral of the same patient on one day) are merged by level
into one column, each measure from the view that shows it, each view in its own scale; where the
views' magnifications are uncertain by different amounts, the study carries the larger spread. Views that disagree on whether they
have a pixel size cannot share one scale and are refused, and so are two views that both lack
one, since each image's pixel is a unit of its own.

Who drew the corners is the caller's statement (`--annotation`), never inferred; a reader id the
format marks as a model's ("model:<run id>") beside a statement of human is refused.
"""
from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import LEVELS, MEASURES, NOT_MEASURED, PLANES, SEVEN
from .column import Body, Column, facts_from_levels
from .readers import (DEFAULT_MAGNIFICATION, DEFAULT_MAGNIFICATION_LOG_SD, LEAST_LOG_SD, LEAST_MAGNIFICATION,
                      STATED_LOG_SD, caller_value)

FORMAT = "schwingnet-spine-xr/1"
NAMES = set(LEVELS) | {"?"}
VIEWS = ("ap", "pa", "lateral")
# The magnification an annotation's pixel_mm is divided by where none is given, and the spread of
# its log: the reader's default, so a film scaled by its annotation and one scaled by its header
# share one, chosen and sourced in readers.py; a stated factor shares STATED_LOG_SD the same way.
M0, M_LOG_SD = DEFAULT_MAGNIFICATION, DEFAULT_MAGNIFICATION_LOG_SD
FROM_CORNERS = ("endplate", "endplate_lower", "endplate_depth", "endplate_lower_depth", "h_post")


def read(path: str) -> dict:
    with open(path) as fh:
        d = json.load(fh)
    if d.get("format") != FORMAT:
        raise SystemExit("%s is not a %s annotation (format %r)" % (path, FORMAT, d.get("format")))
    return d


def view_of(image: dict) -> str:
    """ap or lateral; a PA film shows what an AP does."""
    v = str(image.get("view", "")).lower()
    if v not in VIEWS:
        raise SystemExit("the image's view is %r; the importer reads ap, pa or lateral" % v)
    return "ap" if v == "pa" else v


def corner(body: dict, i: int) -> Optional[np.ndarray]:
    """Corner i of a body when it is given and visible, else None."""
    cs = body.get("corners") or []
    vis = body.get("visible") or [True] * 4
    if i >= len(cs) or cs[i] is None or (i < len(vis) and vis[i] is False):
        return None
    return np.asarray(cs[i], float)


def span(a: Optional[np.ndarray], b: Optional[np.ndarray]) -> float:
    return float(np.linalg.norm(b - a)) if a is not None and b is not None else math.nan


def corner_chords(body: dict, view: str, anterior: Optional[str]) -> Tuple[Dict[str, float], Dict[str, str]]:
    """The chords one body's corners and its optional `chords` give on a view, in pixels, and
    why any was not taken."""
    sl, sr, ir, il = (corner(body, i) for i in range(4))
    vals: Dict[str, float] = {}
    flags: Dict[str, str] = {}
    if view == "ap":
        vals["endplate"], vals["endplate_lower"] = span(sl, sr), span(il, ir)
    else:
        vals["endplate_depth"], vals["endplate_lower_depth"] = span(sl, sr), span(il, ir)
        if anterior == "left":
            vals["h_post"] = span(sr, ir)
        elif anterior == "right":
            vals["h_post"] = span(sl, il)
        else:
            vals["h_post"] = math.nan
            flags["h_post"] = "which side is anterior is not recorded (the image's anterior field, or --anterior)"
    for name, pts in (body.get("chords") or {}).items():
        if name not in MEASURES or name in FROM_CORNERS or view not in PLANES[name]:
            flags[name] = "a %s chord on a %s view is not read (corners give the body's chords)" % (name, view)
            continue
        if pts is None or len(pts) != 2 or any(p is None for p in pts):
            continue
        vals[name] = span(np.asarray(pts[0], float), np.asarray(pts[1], float))
    for k, v in vals.items():
        if not np.isfinite(v):
            flags.setdefault(k, "a corner is missing or hidden")
    return vals, flags


def annotation_of(reader: dict) -> str:
    """machine for a reader id the format marks as a model's ("model:<run id>"), else unknown:
    whether a person drew the corners is the caller's statement, never read from the file."""
    return "machine" if str(reader.get("id", "")).startswith("model:") else "unknown"


def mean_height(body: dict) -> float:
    """The mean image row of a body's given corners, for its order on the view; NaN with none."""
    ys = [c[1] for c in (corner(body, i) for i in range(4)) if c is not None]
    return float(np.mean(ys)) if ys else math.nan


def view_bodies(doc: dict, view: str) -> Tuple[List[Tuple[str, dict]], List[str]]:
    """One view's bodies top down, each with the level it may be keyed by: its name, or "?" for
    an unnamed body, a body with a name outside the 27 and both bodies of a level named twice."""
    bodies = list(doc.get("bodies", []))
    problems = []
    names = []
    for i, b in enumerate(bodies):
        level = str(b.get("level", "?"))
        if level not in NAMES:
            problems.append("body %d of the %s view is named %r, not one of the 27 names; read as ?" % (i, view, level))
            level = "?"
        names.append(level)
    for lv in sorted({n for n in names if n != "?" and names.count(n) > 1}):
        problems.append("%s is named %d times on the %s view; those bodies are read as ?" % (lv, names.count(lv), view))
        names = ["?" if n == lv else n for n in names]
    order = sorted(range(len(bodies)), key=lambda i: (math.isnan(mean_height(bodies[i])), mean_height(bodies[i]), i))
    return [(names[i], bodies[i]) for i in order], problems


def modality_of(image: dict) -> str:
    """The image's modality as its annotation states it, without the spaces around it, or film
    where it states none (the field absent, null or blank). The format names no default; film is
    this module's own choice, the one it has always read an absent field as."""
    said = str(image.get("modality") or "").strip()
    return said or "film"


def stated_pixel(image: dict) -> Optional[float]:
    """The annotation's pixel_mm as a length, or None where it gives none. A pixel_mm that is not
    a positive finite number is refused: zero would put every chord at 0 mm and a negative one
    below it, each with the scale called known."""
    pixel = image.get("pixel_mm")
    if pixel is None:
        return None
    try:
        value = float(pixel)
    except (TypeError, ValueError):
        value = math.nan
    if not (math.isfinite(value) and value > 0):
        raise SystemExit("the annotation's pixel_mm is %r; it must be a positive length in millimetres, or null where "
                         "the scale is unknown" % (pixel,))
    return value


def doc_scale(doc: dict, magnification: Optional[float] = None, magnification_sd: Optional[float] = None) -> dict:
    """An annotation's own scale: its pixel_mm, a length at the detector, over the stated
    magnification or the default; or unknown where it gives no pixel_mm. A stated magnification
    carries the spread a header's stated factor does (readers.STATED_LOG_SD), so one fact gets one
    spread whichever route states it, unless --magnification-sd gives another. The caller's values
    are held to the bounds a header's are (readers.caller_value): a magnification of 1 or more, a
    spread of 0 or more, each a finite number."""
    magnification = caller_value(magnification, "--magnification", LEAST_MAGNIFICATION, inclusive=True)
    magnification_sd = caller_value(magnification_sd, "--magnification-sd", LEAST_LOG_SD, inclusive=True)
    pixel = stated_pixel(doc["image"])
    if pixel is None:
        return {"pixel_mm": None, "pixel_mm_at_detector": None, "magnification": None, "log_sd": None,
                "basis": "unknown: the annotation gives no pixel_mm"}
    stated = magnification is not None
    m0 = magnification if stated else M0
    msd = magnification_sd if magnification_sd is not None else (STATED_LOG_SD if stated else M_LOG_SD)
    return {"pixel_mm": float(pixel) / m0, "pixel_mm_at_detector": float(pixel), "magnification": m0, "log_sd": msd,
            "basis": "the annotation's pixel_mm over %s magnification %.3f" % ("the stated" if stated else "the default", m0)}


def ingest(paths: Sequence[str], study_id: str, source: str, annotation: str, subject_id: Optional[str] = None,
           anterior: Optional[str] = None, magnification: Optional[float] = None,
           magnification_sd: Optional[float] = None) -> Column:
    docs = [read(p) for p in paths]
    return ingest_docs(docs, [doc_scale(d, magnification, magnification_sd) for d in docs], study_id, source,
                       annotation, subject_id, anterior)


def ingest_docs(docs: Sequence[dict], scales: Sequence[dict], study_id: str, source: str, annotation: str,
                subject_id: Optional[str] = None, anterior: Optional[str] = None,
                extra: Optional[dict] = None) -> Column:
    """Annotations of the views of one study, each with its own scale (`doc_scale`, or the image's
    header through film.py), to one column."""
    views, known = check_views(docs, scales, annotation)
    col_bodies, problems = merge_views(docs, views, scales, known, anterior)
    study = study_record(docs, views, scales, known, col_bodies, problems, annotation)
    study.update({"study_id": study_id, "subject_id": subject_id or study_id, "source": source})
    study.update(extra or {})
    study.update(facts_from_levels([b.level for b in col_bodies], study["expresses"]))
    return Column(study=study, bodies=col_bodies)


def check_views(docs: Sequence[dict], scales: Sequence[dict], annotation: str) -> Tuple[List[str], bool]:
    """Each annotation's view, and whether the views have a pixel size, after refusing what one
    column cannot hold: two annotations of one view, views that disagree on having a pixel size,
    several views with none, and a statement of human beside a model's reader id."""
    if annotation not in ("human", "machine"):
        raise SystemExit("--annotation must say who drew the corners: human or machine")
    views = [view_of(d["image"]) for d in docs]
    if len(set(views)) != len(views):
        raise SystemExit("two annotations of the same view (%s); one per view per study" % ", ".join(views))
    scaled = [sc.get("pixel_mm") is not None for sc in scales]
    if len(set(scaled)) > 1:
        raise SystemExit("one view has a pixel size and another has none; they cannot share one scale")
    if len(docs) > 1 and not any(scaled):
        raise SystemExit("no view has a pixel size, and each image's pixel is a unit of its own; "
                         "give pixel_mm or ingest each view as a study of its own")
    readers = [d.get("reader", {}) for d in docs]
    if annotation == "human" and any(annotation_of(r) == "machine" for r in readers):
        raise SystemExit("--annotation human, but a reader id says a model drew the corners (%s)"
                         % ", ".join(str(r.get("id")) for r in readers))
    return views, scaled[0]


def merge_views(docs: Sequence[dict], views: Sequence[str], scales: Sequence[dict], known: bool,
                anterior: Optional[str]) -> Tuple[List[Body], List[str]]:
    """The views' bodies merged by level, each measure from the view that shows it in that view's
    scale (or in pixels where the scale is unknown): the named bodies in the order of the levels,
    then each view's unnamed ones; with the problems the views' names raised."""
    order: List[str] = []
    bodies: Dict[str, Body] = {}
    problems: List[str] = []
    for d, view, sc in zip(docs, views, scales):
        side = anterior or d["image"].get("anterior")
        mm = float(sc["pixel_mm"]) if known else 1.0
        listed, found = view_bodies(d, view)
        problems += found
        for i, (level, b) in enumerate(listed):
            key = level if level != "?" else "?%s%d" % (view, i)
            if key not in bodies:
                bodies[key] = Body(level=level)
                order.append(key)
            add_view(bodies[key], b, view, side, mm)
    named = sorted((k for k in order if not k.startswith("?")), key=LEVELS.index)
    keys = named + [k for k in order if k.startswith("?")] if named else order
    return [bodies[k] for k in keys], problems


def add_view(body: Body, drawn: dict, view: str, side: Optional[str], mm: float) -> None:
    """One view's chords of one body into its merged record, at mm per pixel; a body the rule's
    column leaves out is named and kept with the reason, never measured."""
    if body.level in NOT_MEASURED:
        body.flags["all"] = "named, not measured: %s" % (
            "the sacrum carries no row" if body.level == "sacrum" else "the rule's column starts at C3")
        return
    vals, flags = corner_chords(drawn, view, side)
    for m, v in vals.items():
        body.values[m] = v * mm if np.isfinite(v) else math.nan
        body.methods[m] = "%s view, %s" % (view, "corners" if m in FROM_CORNERS else "chord points")
    body.flags.update(flags)


def study_record(docs: Sequence[dict], views: Sequence[str], scales: Sequence[dict], known: bool,
                 col_bodies: Sequence[Body], problems: List[str], annotation: str) -> dict:
    """What the study's record says of its views, its readers and its scale, before its ids and
    the facts its levels give."""
    readers = [d.get("reader", {}) for d in docs]
    calls = [d.get("column", {}) for d in docs if d.get("column")]
    expresses = {"L6": True, "T13": True, "ribs": any(c.get("ribs") for c in calls)}
    magnifications = sorted({sc.get("magnification") for sc in scales if sc.get("magnification") is not None})
    return {"modality": modality_of(docs[0]["image"]), "views": list(views), "annotation": annotation,
            "made_by": ",".join(sorted({str(r.get("id", "")) for r in readers})), "scheme": FORMAT,
            "expresses": expresses,
            # each view's pixel as its annotation states it, beside the pixel its chords were scaled by
            # (at the patient) and the detector's pixel that came from: on film.py's route the image's
            # own header can set the scale over the annotation's pixel_mm
            "pixel_mm_stated": [d["image"].get("pixel_mm") for d in docs],
            "pixel_mm_at_detector": [sc.get("pixel_mm_at_detector") for sc in scales],
            "pixel_mm_at_patient": [sc.get("pixel_mm") for sc in scales],
            "magnification": (magnifications[0] if len(magnifications) == 1 else magnifications) if known else None,
            "scale_known": bool(known), "scale_basis": [sc.get("basis") for sc in scales],
            "scale_log_mean": 0.0, "scale_log_sd": max(float(sc["log_sd"]) for sc in scales) if known else None,
            "reader_call": [c.get("call") for c in calls], "problems": problems,
            "plane_of": {m: "/".join(PLANES[m]) for m in MEASURES},
            "measured": sorted(m for m in SEVEN if any(np.isfinite(b.values.get(m, math.nan)) for b in col_bodies))}


def ingest_one(path: str, **kw) -> Column:
    return ingest([path], **kw)
