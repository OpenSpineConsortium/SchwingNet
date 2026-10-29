"""A radiograph or fluoroscopy frame, with what was drawn on it, to a column: corners in
SchwingNet's X-ray format, FleXray's masks, or both, measured in millimetres from the image's own
header.

    python -m scanimport ingest-image --image lat.dcm --corners lat.json --study f1 --source x \
        --annotation human --out imports/x
    python -m scanimport ingest-image --image ap.png --corners ap.json --flexray out/ap_probabilities.npy \
        --study f1 --source x --annotation human --out imports/x

The image itself is read by readers.py (one DICOM radiograph, CR, DX, XA, RF, a CT localizer or
a secondary capture; a PNG, JPEG, TIFF or BMP), which gives its size, its sha256 and its scale:
the pixel's length at the patient and the spread of its log, from the DICOM header in the order
the standard's attributes allow, never from a picture file's print resolution. Its pixels are
never decoded, since nothing here reads them.

A film is measured from what was drawn on it, never from its intensities alone. Training-free
designs that read the intensities of a radiograph or a lateral DXA scan do exist
(research_notes/Vertebra measures without masks/radiograph_classical_methods.md, sections 3 and
4): three expired Siemens patents (US 6,608,916, 6,608,917 and 7,010,151) find the spine's axis,
its boundaries and end-plate lines spanning the column on digital radiographs with no training
(the third assumes the first and last end-plates' ranges known), so the ends of those lines
approximate the plates' corners, an inference here that the patents do not state; Lunar's US
5,228,068 places six morphometry points per vertebra on a lateral DXA scan, with no operator input
or training described; and Benjelloun et al. 2011 find the 2N corners between two clicks with
Harris corners and a geometric search. But none of them publishes an accuracy: the patents give
none, and Benjelloun's corners only start a trained active shape model, whose result is the one
measured. The training-free methods that do publish numbers locate only the spine (its orientation
and position) or, seeded, give Cobb angles; none reports a corner or end-plate point error in
millimetres. Every millimetre-level corner result in the research read comes from a model trained
on annotated images (a shape or appearance model, or random forests), often started from seeds. A
chord read by a method whose error nobody has measured would carry that unmeasured error into the
rule, so an image with neither corners nor masks of the bodies is refused.

CORNERS. The annotation (radiograph.py) must be of this image: where it states the image's sha256
(compared as hexadecimal, in either case), width or height, each must match the file, or the pair
is refused; --view and --modality, where given, must match what it states, and fill in what it
leaves out. Who drew the corners is the caller's statement (--annotation, human or machine),
required whenever corners are given and refused as human beside a reader id the format marks as a
model's, before FleXray names anything. The scale is the image's own where it has one (readers.py:
the DICOM header's, with the caller's --pixel-mm in place of the header's pixel length, or of a
picture's missing one), else the annotation's pixel_mm (a length at the detector, over the stated
or default magnification), else unknown; an annotation's pixel_mm that is not a positive length is
refused. Where the annotation states pixel_mm beside the image's own scale, the image's is used,
and the two are compared at the detector: a disagreement of more than one per cent is recorded as
a problem, and so is a scale that gives the pixel only at the patient (a Pixel Spacing calibrated
against a fiducial or for geometry, with no Imager Pixel Spacing beside it), against which the
annotation's cannot be compared. The reader's word that the image's scale is unknown is kept only
where no scale is found at all.

FLEXRAY. FleXray (Butoi VI et al., "FleXray: Universal Clinical X-ray Segmentation", 2026; code
MIT, weights CC BY-NC 4.0) writes, per image, channel-first arrays of 61 channels on a 256 by 256
canvas: the image zero-padded to a square at its centre and resized (its docs/inference.md and
preprocessing.py). One channel per vertebra from C1 to L5 and the sacrum; no L6 and no T13 (the
MOOSE dataset spec drops native labels outside its protocol, "such as vertebra_l6", to
background; that T13 was trained as background too is the research note's inference,
masks_corners_magnification.md, section 5). A canvas point (u, v), in canvas pixels from the canvas's
corner, is the image's point x = u side / 256 - pad_left, y = v side / 256 - pad_top, with
side = max(height, width), pad_left = (side - width) // 2 and pad_top = (side - height) // 2.
Its masks are thresholded at 0.5 (FleXray's default); probabilities are resampled by linear
interpolation onto a grid UPSAMPLE times finer before the same threshold, so an edge falls between
canvas pixels; logits are turned into probabilities first. Each vertebra channel's largest
connected part is that vertebra.

FleXray's vertebra channels are read here as whole vertebrae, arch and processes with the body.
That is this module's reading, which the research notes do not confirm: they give the channels'
names (vertebra_c1 to vertebra_l5) and the MOOSE-profile renders it was trained on, not what the
CT masks those renders were projected from held. It is the safe reading: on an AP the transverse
processes would widen such a mask beyond the body, and on a lateral the arch and spinous process
lengthen it behind the body, so no body chord is read from it whichever it holds. What it gives
is each body's level: a body of the corner annotation takes
the level whose mask covers the most of its quadrilateral, if that covers at least a quarter of it
(the rule SchwingNet's FleXray benchmark scored, docs/research/flexray-audit-companion.md). An
annotation's own name is kept, and a disagreement is recorded as a problem. A body the annotation
leaves unnamed ("?") takes FleXray's level only where that keeps to the reader's names, and stays
"?" with the reason recorded where it does not:

- FleXray names no body at all once it contradicts a name the reader gave. It has no L6 or T13
  channel (L6 dropped to background by the MOOSE spec, T13 by the note's inference, as above), so
  on a column with a transitional vertebra its count can be shifted by one against the reader's,
  and the classical-methods note above records shifted matches along
  the repeating column as a failure of automatic vertebra finding (its section 5, Zamora et al.
  2003, of a template); a shifted call on one body makes its calls on the others suspect too.
- A FleXray name never repeats a name the reader gave another body: radiograph.view_bodies reads
  both bodies of a level named twice as "?", so the reader's own name would be lost.
- A FleXray name never breaks the image's top-down order (the corners' mean row, as view_bodies
  orders a view) against a body the reader named once, nor against another body FleXray names;
  two of FleXray's names that repeat or cross each other leave both bodies "?". The column lists
  named bodies in the order of the levels, so a name out of order on the image would move a
  body's chords to another place in the column.
- A body FleXray makes no call on stays "?" with its reason too: a corner missing or hidden, so its
  quadrilateral is not known, no level's mask covering a quarter of it (with the largest share
  any covers), or no vertebra in FleXray's arrays at all.

Since a model then named levels, the study's annotation is "machine", whatever drew the corners, so
a model's names never raise a tier; who drew the corners is kept beside it (corners_drawn_by).

The channels are named by a label_names.json, given or beside the arrays (FleXray writes one per
output folder), else they are FleXray's own 61 in its order; either way the file read is named in
the study and hashed in the manifest. A vertebra's channel must be spelled as FleXray spells it
(vertebra_c1 to vertebra_l5, and sacrum): arrays none of whose channels is so named are refused,
since nothing could be named or found from them, never read as a spine with no vertebrae.

Masks of the bodies alone, from another model or a FleXray retrained with body labels, with their
channels named in FleXray's spelling, are read with mask_content="body": each body's corners are
then the quadrilateral of largest area with its vertices on the mask's outline (Franchini R et
al., 3rd IMEKO TC13 Symposium, Lecce, 2014, pp. 28-31, who place the four corners on an active
shape model's contour "by maximizing the area formed by the corresponding quadrilateral": corner
errors 0.82 to 2.15 mm against a radiologist), taken
over the vertices of the outline's convex hull, every quadrilateral of them, so the answer is the
exact maximum and fixed. Its four vertices are ordered as the format orders corners, superior-left,
superior-right, inferior-right, inferior-left as the image is shown head up, the head's direction
at each body taken from its neighbours' centres (from the level above's centre to the level
below's), or the image's own up where it has no named neighbour.
"""
from __future__ import annotations

import itertools
import json
import math
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import ndimage
from scipy.spatial import ConvexHull
from scipy.special import expit

from . import LEVELS
from . import radiograph as XR
from . import readers as RD
from .column import Column

CANVAS = 256
THRESHOLD = 0.5
# This module's own choice, which no source gives: probabilities are resampled onto a grid this many
# times finer than the canvas before the threshold, so an edge is placed to a quarter of a canvas
# pixel rather than a whole one.
UPSAMPLE = 4
# This module's own choice, which no source gives: a largest part smaller than this many canvas
# pixels is taken as a speck the threshold left, not a vertebra.
MIN_CANVAS_PIXELS = 12
COVERAGE = 0.25                       # the share of a body's quadrilateral a mask must cover to name it
# This module's own choice, the same as readers.SPACING_AGREEMENT: two pixel lengths within one per
# cent of each other are one value written to different precision.
PIXEL_AGREEMENT = 0.01
# readers.py words every problem it records for an image with no length per pixel with this phrase
# (read_picture, read_dicom_projection); such a problem is moot once the annotation gives the scale.
SCALE_UNKNOWN = "scale is unknown"

# FleXray's 61 channels, in its model label file's order (src/fxr/configs/models/all_structures_flexray_v4.yml)
FLEXRAY_LABELS = (["background", "skull", "scapulae", "clavicles", "humeri", "phalanges", "metacarpals", "carpals",
                   "radii", "ulnae", "tibiae", "femurs", "patellae", "fibulae", "metatarsals", "tarsals", "toes"]
                  + ["rib_%d" % i for i in range(1, 13)] + ["sternum"]
                  + ["vertebra_c%d" % i for i in range(1, 8)] + ["vertebra_t%d" % i for i in range(1, 13)]
                  + ["vertebra_l%d" % i for i in range(1, 6)]
                  + ["hips", "sacrum", "kidneys", "liver", "spleen", "lungs", "heart"])
VERTEBRA_LABELS = {"vertebra_%s" % lv.lower(): lv for lv in LEVELS if lv not in ("T13", "L6", "sacrum")}
VERTEBRA_LABELS["sacrum"] = "sacrum"


# ---- the image and its annotation -------------------------------------------------------------------

def check_pair(doc: dict, image: RD.Projection, path: str) -> None:
    """Refuse an annotation that says it is of another image. A sha256 is hexadecimal, so its case
    carries nothing (PowerShell's Get-FileHash prints it in capitals)."""
    said = doc.get("image", {})
    sha = str(said.get("sha256") or "").strip().lower()
    if sha and sha != image.sha256.lower():
        raise SystemExit("%s is of the image with sha256 %s, not of this one (%s)" % (path, sha, image.sha256))
    for key, real in (("width", image.width), ("height", image.height)):
        if said.get(key) not in (None, "") and int(said[key]) != real:
            raise SystemExit("%s says the image is %s %s pixels, but it is %d" % (path, key, said[key], real))


def check_view(doc: dict, view: Optional[str]) -> None:
    """The caller's --view against the annotation's, as --modality is held: a view the annotation
    leaves out (absent, null or blank) is written into it, and one that differs is refused."""
    if view is None:
        return
    if not str(doc["image"].get("view") or "").strip():
        doc["image"]["view"] = view
    elif XR.view_of(doc["image"]) != XR.view_of({"view": view}):
        raise SystemExit("--view %s, but the annotation says %s" % (view, doc["image"].get("view")))


def check_modality(doc: dict, modality: Optional[str], path: str) -> None:
    """The caller's --modality against the annotation's, as --view is held: a modality the
    annotation leaves out (absent, null or blank, spaces counting as blank, as
    radiograph.modality_of reads it) is written into it, and one that differs is refused, so an
    image the caller says is a DRR is never tiered as the real X-ray an annotation's silence would
    default to."""
    if modality is None:
        return
    said = str(doc["image"].get("modality") or "").strip()
    if not said:
        doc["image"]["modality"] = modality
    elif said.lower() != str(modality).strip().lower():
        raise SystemExit("--modality %s, but %s says the image's modality is %s" % (modality, path, said))


def check_statement(doc: dict, annotation: Optional[str]) -> None:
    """Who drew the corners, the caller's statement, held to radiograph.ingest_docs's rule before
    FleXray names anything: once it has, the study's annotation is machine whatever was said, and
    a missing or contradicted statement would pass unseen."""
    if annotation not in ("human", "machine"):
        raise SystemExit("--annotation must say who drew the corners: human or machine")
    reader = doc.get("reader", {})
    if annotation == "human" and XR.annotation_of(reader) == "machine":
        raise SystemExit("--annotation human, but a reader id says a model drew the corners (%s)" % reader.get("id"))


def read_annotation(path: str, image: RD.Projection, view: Optional[str], modality: Optional[str],
                    annotation: Optional[str]) -> dict:
    """The corners' annotation, held to the image and to what the caller says of both."""
    doc = XR.read(path)
    check_pair(doc, image, path)
    check_view(doc, view)
    check_modality(doc, modality, path)
    check_statement(doc, annotation)
    return doc


def scale_of(image: RD.Projection, doc: Optional[dict], problems: List[str]) -> dict:
    """The image's own scale where it has one (the caller's --pixel-mm or the header's), else the
    annotation's, else unknown; an annotation's pixel_mm beside the image's own scale is compared
    with it (`compare_pixel`)."""
    stated = XR.stated_pixel(doc["image"]) if doc is not None else None
    if image.scale.get("pixel_mm") is None:
        return XR.doc_scale(doc) if stated is not None else image.scale
    if stated is not None:
        compare_pixel(stated, image.scale, problems)
    return image.scale


def compare_pixel(stated: float, scale: dict, problems: List[str]) -> None:
    """The annotation's pixel_mm, a length at the detector, against the detector's pixel the
    image's scale gives. A scale that gives the pixel only at the patient, with no detector's pixel
    beside it (or a reader that leaves the key out), cannot be compared, and that is said too: the
    annotation's value is then neither confirmed nor used."""
    detector = scale.get("pixel_mm_at_detector")
    if not detector:
        problems.append("the annotation's pixel_mm %.4f cannot be compared with the image's scale, which gives no pixel "
                        "at the detector (%s); the image's scale is used" % (stated, scale.get("basis")))
    elif abs(stated - float(detector)) > PIXEL_AGREEMENT * float(detector):
        problems.append("the annotation's pixel_mm %.4f differs from the image's %.4f at the detector (%s); the image's "
                        "scale is used" % (stated, float(detector), scale.get("basis")))


def image_problems(image: RD.Projection, scale: dict) -> List[str]:
    """The reader's problems, its word that the scale is unknown kept only where no scale was found:
    an annotation's pixel_mm gives a scale the image itself lacks. Where none was found and the
    reader did not say so, it is said here, so the study always says why its chords are in pixels."""
    unknown = scale.get("pixel_mm") is None
    kept = [p for p in image.problems if unknown or SCALE_UNKNOWN not in p]
    if unknown and not any(SCALE_UNKNOWN in p for p in kept):
        kept.append("no pixel size in the image, the annotation or --pixel-mm: the chords stay in pixels and the "
                    "%s" % SCALE_UNKNOWN)
    return kept


# ---- FleXray's arrays -------------------------------------------------------------------------------

def read_flexray(path: str, names_path: Optional[str] = None) -> Tuple[np.ndarray, List[str], str]:
    """FleXray's masks, probabilities or logits (C, 256, 256), as probabilities, with the channels'
    names and which of the three the file held."""
    arr = np.load(path, allow_pickle=False)
    if arr.ndim == 4 and arr.shape[0] == 1:
        arr = arr[0]
    if arr.ndim != 3 or arr.shape[1:] != (CANVAS, CANVAS):
        raise SystemExit("%s holds an array of shape %s; FleXray writes (channels, %d, %d)" % (path, arr.shape, CANVAS, CANVAS))
    if arr.dtype == np.bool_ or np.issubdtype(arr.dtype, np.integer):
        kind, prob = "masks", (arr > 0).astype(np.float64)
    elif float(arr.min()) >= 0.0 and float(arr.max()) <= 1.0:
        kind, prob = "probabilities", arr.astype(np.float64)
    else:
        kind, prob = "logits", expit(arr.astype(np.float64))
    names = channel_names(path, names_path, arr.shape[0])
    return prob, names, kind


def names_file(path: str, names_path: Optional[str] = None) -> Optional[str]:
    """The label_names.json that names the channels of the arrays at `path`: the one given, which
    must exist, else the one beside the arrays where there is one, else None (FleXray's own 61).
    The command line hashes what this returns, since the names decide every level."""
    if names_path is not None:
        if not os.path.isfile(names_path):
            raise SystemExit("%s, given to name FleXray's channels, is not a file" % names_path)
        return names_path
    beside = os.path.join(os.path.dirname(path), "label_names.json")
    return beside if os.path.isfile(beside) else None


def channel_names(path: str, names_path: Optional[str], channels: int) -> List[str]:
    """label_names.json, given or beside the arrays (a list, or an object holding one), else
    FleXray's 61."""
    names_path = names_file(path, names_path)
    if names_path is not None:
        with open(names_path) as fh:
            got = json.load(fh)
        if isinstance(got, dict):
            got = got.get("label_names") or got.get("labels") or got.get("names") or [got[k] for k in sorted(got, key=int)]
        names = [str(n) for n in got]
    elif channels == len(FLEXRAY_LABELS):
        names = list(FLEXRAY_LABELS)
    else:
        raise SystemExit("%s has %d channels and no label_names.json names them" % (path, channels))
    if len(names) != channels:
        raise SystemExit("%d channel names for %d channels" % (len(names), channels))
    return names


def to_image(uv: np.ndarray, height: int, width: int) -> np.ndarray:
    """Canvas points (u across, v down, in canvas pixels from its corner) to the image's pixels."""
    side = max(height, width)
    pad = np.array([(side - width) // 2, (side - height) // 2], float)
    return uv * (side / CANVAS) - pad


def to_canvas(xy: np.ndarray, height: int, width: int) -> np.ndarray:
    side = max(height, width)
    pad = np.array([(side - width) // 2, (side - height) // 2], float)
    return (xy + pad) * (CANVAS / side)


def fine_mask(prob: np.ndarray, kind: str) -> Tuple[np.ndarray, int]:
    """A channel thresholded at 0.5 on a grid UPSAMPLE times finer (probabilities), or as given
    (masks), with the grid's factor."""
    if kind == "masks":
        return prob > THRESHOLD, 1
    n = CANVAS * UPSAMPLE
    c = (np.arange(n) + 0.5) / UPSAMPLE - 0.5                  # the fine pixels' centres, in canvas index units
    rr, cc = np.meshgrid(c, c, indexing="ij")
    p = ndimage.map_coordinates(prob, [rr.ravel(), cc.ravel()], order=1, mode="nearest").reshape(n, n)
    return p > THRESHOLD, UPSAMPLE


def largest_part(mask: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
    if n <= 1:
        return mask
    return lab == int(np.argmax(np.bincount(lab.ravel())[1:])) + 1


def require_vertebra_channels(names: Sequence[str], path: str) -> None:
    """Refuse arrays none of whose channels is a vertebra's as FleXray spells them: read on, they
    would give a column with no bodies and no word of why."""
    if not any(n in VERTEBRA_LABELS for n in names):
        raise SystemExit("none of the %d channel names of %s is a vertebra's as FleXray spells them (vertebra_c1 to "
                         "vertebra_l5, and sacrum), so no body can be named or found from them; name the channels so in "
                         "a label_names.json (the names read begin %s)" % (len(names), path, ", ".join(names[:6])))


def vertebrae(prob: np.ndarray, names: Sequence[str], kind: str) -> Dict[str, Tuple[np.ndarray, int]]:
    """Each vertebra channel's largest part on the fine grid, by level."""
    out = {}
    for ch, name in enumerate(names):
        level = VERTEBRA_LABELS.get(name)
        if level is None:
            continue
        mask, f = fine_mask(prob[ch], kind)
        mask = largest_part(mask)
        if mask.sum() / float(f * f) >= MIN_CANVAS_PIXELS:
            out[level] = (mask, f)
    return out


# ---- naming the corner bodies ---------------------------------------------------------------------

def quad_mask(corners_canvas: np.ndarray, f: int) -> np.ndarray:
    """The fine pixels whose centres fall inside a convex quadrilateral given in canvas units."""
    n = CANVAS * f
    lo = np.clip(np.floor(corners_canvas.min(0) * f).astype(int), 0, n - 1)
    hi = np.clip(np.ceil(corners_canvas.max(0) * f).astype(int) + 1, 0, n)
    out = np.zeros((n, n), bool)
    xs, ys = (np.arange(lo[0], hi[0]) + 0.5) / f, (np.arange(lo[1], hi[1]) + 0.5) / f
    X, Y = np.meshgrid(xs, ys)
    inside = np.ones(X.shape, bool)
    centre = corners_canvas.mean(0)
    for a, b in zip(corners_canvas, np.roll(corners_canvas, -1, axis=0)):
        side = (b[0] - a[0]) * (centre[1] - a[1]) - (b[1] - a[1]) * (centre[0] - a[0])
        here = (b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0])
        inside &= (here * np.sign(side)) >= 0
    out[lo[1]:hi[1], lo[0]:hi[0]] = inside
    return out


def level_of(corners: np.ndarray, found: Dict[str, Tuple[np.ndarray, int]], height: int, width: int) -> Tuple[Optional[str], float]:
    """The level whose mask covers the most of a body's quadrilateral, and that share."""
    canvas = to_canvas(corners, height, width)
    best, share = None, 0.0
    for level in sorted(found, key=LEVELS.index):
        mask, f = found[level]
        q = quad_mask(canvas, f)
        if not q.any():
            continue
        s = float((mask & q).sum()) / float(q.sum())
        if s > share:
            best, share = level, s
    return (best, share) if share >= COVERAGE else (None, share)


def flexray_calls(bodies: Sequence[dict], found: Dict[str, Tuple[np.ndarray, int]], height: int,
                  width: int) -> Tuple[Dict[int, Tuple[str, float]], Dict[int, str]]:
    """FleXray's level, and the share of the body's quadrilateral its mask covers, for each body
    with four corners that some level's mask covers enough of; and for every other body, why
    FleXray made no call on it."""
    calls, misses = {}, {}
    for i, body in enumerate(bodies):
        cs = [XR.corner(body, k) for k in range(4)]
        if any(c is None for c in cs):
            misses[i] = "a corner is missing or hidden, so its quadrilateral is not known"
            continue
        level, share = level_of(np.array(cs), found, height, width)
        if level is None:
            misses[i] = ("no level's mask covers a quarter of it (the largest share is %.0f per cent)" % (100 * share)
                         if found else "FleXray's arrays hold no vertebra")
            continue
        calls[i] = (level, share)
    return calls, misses


def places(bodies: Sequence[dict]) -> Dict[int, Tuple[float, int]]:
    """Each body's place on the image, top down, as radiograph.view_bodies orders a view: the mean
    row of its corners, then its index; a body with no corner given has none."""
    out = {}
    for i, body in enumerate(bodies):
        row = XR.mean_height(body)
        if math.isfinite(row):
            out[i] = (row, i)
    return out


def against_order(i: int, level_i: str, j: int, level_j: str, place: Dict[int, Tuple[float, int]]) -> bool:
    """Whether two bodies' levels repeat or run against their order on the image: the body above
    must carry the level nearer the head."""
    if level_i == level_j:
        return True
    return (place[i] < place[j]) != (LEVELS.index(level_i) < LEVELS.index(level_j))


def keeping_to_the_reader(calls: Dict[int, Tuple[str, float]], own: Sequence[str],
                          place: Dict[int, Tuple[float, int]], problems: List[str]) -> Dict[int, str]:
    """FleXray's calls on unnamed bodies that repeat no name the reader gave and keep the image's
    order against every body the reader named once (a name given twice is read as "?" and places
    nothing); the others are recorded and left "?"."""
    given = {lv for lv in own if lv in LEVELS}
    anchors = [j for j, lv in enumerate(own) if lv in LEVELS and own.count(lv) == 1 and j in place]
    kept = {}
    for i, (level, share) in sorted(calls.items()):
        said = "body %d, left ? by the annotation, is %s by FleXray (%.0f per cent of it)" % (i, level, 100 * share)
        if level in given:
            problems.append("%s, a name the annotation gives another body; it stays ?" % said)
            continue
        crossed = [j for j in anchors if against_order(i, level, j, own[j], place)]
        if crossed:
            j = crossed[0]
            problems.append("%s, but it lies %s body %d, which the annotation names %s, so %s would run against the "
                            "order of the levels; it stays ?" % (said, "above" if place[i] < place[j] else "below", j,
                                                                 own[j], level))
            continue
        kept[i] = level
    return kept


def agreeing_with_each_other(calls: Dict[int, str], place: Dict[int, Tuple[float, int]],
                             problems: List[str]) -> Dict[int, str]:
    """The calls that repeat no other call and keep the image's order against every other; a pair
    that does not leaves both bodies "?", since nothing says which of the two is wrong."""
    crossed = set()
    for i, k in itertools.combinations(sorted(calls), 2):
        if against_order(i, calls[i], k, calls[k], place):
            crossed |= {i, k}
    for i in sorted(crossed):
        problems.append("body %d, left ? by the annotation, is %s by FleXray, which repeats or crosses FleXray's call on "
                        "another unnamed body; it stays ?" % (i, calls[i]))
    return {i: lv for i, lv in calls.items() if i not in crossed}


def name_bodies(doc: dict, found: Dict[str, Tuple[np.ndarray, int]], height: int, width: int,
                problems: List[str]) -> int:
    """FleXray's level on each body with four corners the annotation left "?", where it keeps to
    the reader's names (the module's docstring gives the rules); the annotation's own names are
    kept and every disagreement or refusal is recorded. The number of bodies FleXray named."""
    bodies = doc.get("bodies", [])
    own = [str(b.get("level", "?")) for b in bodies]
    calls, misses = flexray_calls(bodies, found, height, width)
    for i in sorted(misses):
        if own[i] == "?":
            problems.append("body %d, left ? by the annotation, is not called by FleXray: %s; it stays ?" % (i, misses[i]))
    contradicted = [i for i in sorted(calls) if own[i] in LEVELS and own[i] != calls[i][0]]
    for i in contradicted:
        problems.append("body %d is named %s by the annotation and %s by FleXray (%.0f per cent of it); the "
                        "annotation's name is kept" % (i, own[i], calls[i][0], 100 * calls[i][1]))
    unnamed = {i: c for i, c in calls.items() if own[i] == "?"}
    if not unnamed:
        return 0
    if contradicted:
        problems.append("FleXray contradicts the annotation's own names, so its count may be shifted against the "
                        "reader's; it names none of the bodies the annotation left ? (%d)" % len(unnamed))
        return 0
    place = places(bodies)
    named = agreeing_with_each_other(keeping_to_the_reader(unnamed, own, place, problems), place, problems)
    for i, level in named.items():
        bodies[i]["level"] = level
    return len(named)


# ---- corners from masks of the bodies alone ---------------------------------------------------------

def outline(mask: np.ndarray, f: int) -> np.ndarray:
    """The corners of the mask's edge pixels, in canvas units."""
    edge = mask & ~ndimage.binary_erosion(mask)
    rc = np.argwhere(edge)
    pts = np.concatenate([rc + d for d in ((0, 0), (0, 1), (1, 0), (1, 1))])
    return np.unique(pts[:, ::-1].astype(float) / f, axis=0)       # (u, v): across, down


def largest_quadrilateral(pts: np.ndarray) -> np.ndarray:
    """The quadrilateral of largest area with its vertices among pts: over every diagonal (i, k)
    of the hull's vertices, the farthest vertex on each side of it (Franchini 2014's maximal
    quadrilateral, solved exactly). Ties go to the lowest indices, so the answer is fixed."""
    hull = pts[ConvexHull(pts).vertices]
    d = hull[None, :, :] - hull[:, None, :]                          # d[i, k] = hull[k] - hull[i]
    e = hull[None, None, :, :] - hull[:, None, None, :]              # e[i, _, p] = hull[p] - hull[i]
    side = d[:, :, None, 0] * e[:, :, :, 1] - d[:, :, None, 1] * e[:, :, :, 0]
    area = 0.5 * (side.max(axis=2) - side.min(axis=2))
    i, k = np.unravel_index(int(np.argmax(area)), area.shape)
    j, l = int(np.argmax(side[i, k])), int(np.argmin(side[i, k]))
    return hull[[i, j, k, l]]


def ordered(quad: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Four points as superior-left, superior-right, inferior-right, inferior-left, the image
    shown with `up` (in image coordinates, y down) pointing up."""
    right = np.array([-up[1], up[0]])
    top = np.argsort(-(quad @ up), kind="stable")
    sup, inf = quad[top[:2]], quad[top[2:]]
    sl, sr = sup[np.argsort(sup @ right, kind="stable")]
    il, ir = inf[np.argsort(inf @ right, kind="stable")]
    return np.array([sl, sr, ir, il])


def heads(centres: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """At each level, the head's direction: from the next level down's centre to the next level
    up's, or from itself where it is the end; the image's up where no neighbour is named."""
    order = sorted(centres, key=LEVELS.index)
    out = {}
    for n, lv in enumerate(order):
        above = centres[order[n - 1]] if n > 0 else centres[lv]
        below = centres[order[n + 1]] if n + 1 < len(order) else centres[lv]
        d = above - below
        out[lv] = d / np.linalg.norm(d) if np.linalg.norm(d) > 0 else np.array([0.0, -1.0])
    return out


def corners_from_masks(found: Dict[str, Tuple[np.ndarray, int]], height: int, width: int) -> List[dict]:
    """A body with four corners per level, in the image's pixels."""
    quads = {lv: to_image(largest_quadrilateral(outline(m, f)), height, width) for lv, (m, f) in found.items()}
    centres = {lv: q.mean(0) for lv, q in quads.items()}
    up = heads(centres)
    return [{"level": lv, "corners": ordered(quads[lv], up[lv]).round(3).tolist(), "visible": [True] * 4}
            for lv in sorted(quads, key=LEVELS.index)]


# ---- the study ----------------------------------------------------------------------------------------

def image_doc(image: RD.Projection, view: Optional[str], modality: Optional[str]) -> dict:
    if view not in XR.VIEWS:
        raise SystemExit("--view must say which view the image is (ap, pa or lateral) when no annotation says it")
    return {"format": XR.FORMAT, "image": {"sha256": image.sha256, "width": image.width, "height": image.height,
                                           "view": view, "modality": modality or "film", "pixel_mm": None},
            "reader": {"id": "model:flexray"}, "bodies": []}


def read_masks(path: str, names_path: Optional[str], mask_content: str) -> Tuple[Dict[str, Tuple[np.ndarray, int]], dict]:
    """FleXray's vertebrae by level, with what the study records of them: the arrays' file, the
    names' file that decided the levels, what the arrays held and the levels found."""
    prob, names, kind = read_flexray(path, names_path)
    require_vertebra_channels(names, path)
    found = vertebrae(prob, names, kind)
    named_by = names_file(path, names_path)
    record = {"file": os.path.basename(path),
              "names": os.path.basename(named_by) if named_by else "FleXray's own 61 channels (no label_names.json)",
              "kind": kind, "mask_content": mask_content, "levels": sorted(found, key=LEVELS.index)}
    return found, record


def ingest_image(image_path: str, study_id: str, source: str, annotation: Optional[str], corners: Optional[str] = None,
                 flexray: Optional[str] = None, flexray_names: Optional[str] = None, mask_content: str = "whole",
                 view: Optional[str] = None, subject_id: Optional[str] = None, anterior: Optional[str] = None,
                 pixel_mm: Optional[float] = None, modality: Optional[str] = None) -> Column:
    """One image with its corners, its FleXray masks, or both, to a column."""
    if corners is None and flexray is None:
        raise SystemExit("a film is measured from what was drawn on it: give --corners, --flexray, or both (no "
                         "training-free method that reads a radiograph's intensities, seeded or not, publishes a corner "
                         "or end-plate point error in millimetres, and every millimetre-level corner result in the "
                         "research read comes from a trained model)")
    if mask_content not in ("whole", "body"):
        raise SystemExit("--mask-content is whole (FleXray's vertebrae) or body")
    if corners is None and mask_content == "whole":
        raise SystemExit("FleXray's vertebra channels are read as whole vertebrae, arch and processes with the body "
                         "(nothing read says they are bodies alone), so no body chord is read from them alone; give "
                         "the image's --corners too, or masks of the bodies alone with --mask-content body")
    image = RD.read_projection(image_path, pixel_mm)
    doc = read_annotation(corners, image, view, modality, annotation) if corners is not None else None
    problems: List[str] = []
    scale = scale_of(image, doc, problems)
    problems = image_problems(image, scale) + problems
    extra: Dict[str, object] = {"image_sha256": image.sha256, "image_source": image.source,
                                "image_size": [image.width, image.height], "covariates": image.header}
    if flexray is not None:
        found, extra["flexray"] = read_masks(flexray, flexray_names, mask_content)
        if doc is not None:
            if not found:
                problems.append("FleXray's arrays hold no vertebra of %d canvas pixels or more, so it names no body"
                                % MIN_CANVAS_PIXELS)
            extra["flexray"]["named"] = name_bodies(doc, found, image.height, image.width, problems)
            if extra["flexray"]["named"]:
                extra["corners_drawn_by"] = annotation      # who drew the corners, kept beside the names a model gave
                annotation = "machine"
        else:
            if not found:
                raise SystemExit("%s holds no body of %d canvas pixels or more, so there is nothing to measure"
                                 % (flexray, MIN_CANVAS_PIXELS))
            doc = image_doc(image, view, modality)
            doc["bodies"] = corners_from_masks(found, image.height, image.width)
            annotation = "machine"
    col = XR.ingest_docs([doc], [scale], study_id, source, annotation, subject_id, anterior, extra)
    col.study["problems"] = problems + list(col.study.get("problems", []))
    return col
