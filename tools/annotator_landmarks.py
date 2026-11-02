#!/usr/bin/env python3
"""The landmarks annotators place, as named 3-D points from the CT morphometry engine's constructions, and their
check against the points a person placed in the same CTs.

Greg, 1 November 2026: "the bare minimum my landmark net should also be able to place landmarks annotators have found
useful such as the ones deepfluoro placed, the corners a ton of xray groups have placed, etc; it should somehow find
where those points correspond to the 3d ct scans and propagate them through". By his rule of 29 October, corners and
landmarks come from the CT engine's constructions, projected, never from a 2-D corner fit. The engine is bordercall's
morphometry, imported here from the pinned copy under grid/bordercall/ (VENDORED, 9c85de1) and never changed; the one
reading the copy lacks, each end plate's own layer (bordercall morphometry/plates.py, commit 69cae89), is repeated
here in a few lines and named where it is used.

Every point is written in world millimetres in LPS (x to the patient's left, y posterior, z superior), the frame of
DeepFluoro's vol-landmarks and of the QA loop's pairs (tools/realx_pairs.py TO_LPS). The engine reads a NIfTI in its
RAS world, so every point is built there and turned on the way out (to_lps).

What it places, each from one construction (CONSTRUCTIONS says each in words):
- per vertebra, from the engine's own reading of it (anatomy.build): the four end-plate corners on the midline
  (column.wall_corner behind, the same construction mirrored to the front in front_corner), the two end-plate centres
  (column.plate_centre, the middle points of quantitative six-point morphometry, as Oei et al. 2013 review it; Genant's
  1993 method grades by eye and places no point), and each plate's lateral ends on its own layer (coronal_corners).
  These are fixed points on the bone; a reader marks the corner of a silhouette, which moves with the beam and the
  vertebra's rotation, so they stand for a reader's corners only as far as that is checked, which DeepFluoro, with no
  person-placed vertebral point, cannot do. Each vertebra's chords between them are set against Panjabi's at its level
  (plausibility), and a vertebra whose chords no body has is marked so;
- the pelvis from the engine's pelvis.py: the hip joint centres (socket_centre, the acetabulum's centre), the iliac
  crests' tops (crest_top), and the S1 end plate (s1_plate) under L5 with its front end, the promontory, and its back
  end (s1_points), on a sacrum that holds S1 (TotalSegmentator 2's sacrum class leaves S1 out: its vertebrae_S1 is
  joined to it, as scanimport's TOTALSEG_FILES joins it);
- DeepFluoro's other pelvic points (Grupp et al. 2020, IJCARS 15:759-769, the release's fourteen landmarks), each a
  short construction on a hip-bone mask written here: the anterior superior iliac spines where the anterior pelvic
  plane rests on each ilium (anterior_plane), the pubic symphysis's superior and inferior ends on each pubis
  (symphysis), the obturator foramen's inferior and medial points (obturator), read two ways: as the source paper
  defines them, the foramen's inferior and medial points of maximal curvature (Grupp et al. 2019, IEEE TBME, the paper
  Grupp 2020 cites for the landmark set; loop_corners), and as the outline's extreme along a direction (DIRECTIONS),
  the greater sciatic notch's deepest point (sciatic_notch), and the femoral head's centre read again as the centre of
  the femur's own ball (ball_centre).

Two of the points are not fixed on the bone: crest_top and symphysis_inferior are extremes along the scanner's long
axis, so on another CT they move on the bone with the pelvis's tilt on the table (KIND).

    python tools/annotator_landmarks.py points --ts <TotalSegmentator folder> [--femur <folder>] [--s1 <folder>] --out points.json
    python tools/annotator_landmarks.py points --labels <label NIfTI> --scheme enhance --out points.json
    python tools/annotator_landmarks.py persons --h5 <ipcai_2020_full_res_data.h5> --out persons.json
    python tools/annotator_landmarks.py check --data <realxray_work/deepfluoro> --persons persons.json --out <folder>

`persons` needs h5py, which only the grid's fluorogen environment has; it reads the vol-landmarks of the five
specimens and nothing else, and refuses the held-out specimen 18-1109. `check` runs where the CTs are, on the grid.
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "grid" / "bordercall"
if sys.path and sys.path[0] and Path(sys.path[0]).resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)                    # tools/ holds profile.py, which shadows the standard library's
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

TO_LPS = np.array([-1.0, -1.0, 1.0])
HELD_OUT = ("18-1109",)                # the QA loop's test specimen (tools/realx_pairs.py DEEPFLUORO_TEST), never read
CASES = ("17-1882", "17-1905", "18-0725", "18-2799", "18-2800")
AGREE_MM = 5.0                         # the bar docs/research/annotator-landmarks/constructions.md set before the run

# TotalSegmentator's files, read into the engine's ENHANCE.PET ids (scanimport/schemes.py: T12 19, L1 to L6 20 to 25,
# hips 26 left and 27 right, sacrum 28), the scheme whose pelvis the engine reads.
TS_SPINE = {"vertebrae_T11": ("T11", 18), "vertebrae_T12": ("T12", 19), "vertebrae_L1": ("L1", 20),
            "vertebrae_L2": ("L2", 21), "vertebrae_L3": ("L3", 22), "vertebrae_L4": ("L4", 23),
            "vertebrae_L5": ("L5", 24)}
LEVEL_ID = {level: value for level, value in TS_SPINE.values()}
LEVEL_ID["L6"] = 25
SACRUM_ID = 28
# DeepFluoro's own 3-D labels (vol_seg.nii.gz; tools/deepfluoro_shipped.py): 1 and 2 the hemipelves, 3 the lumbar
# vertebrae as one class, 4 the upper sacrum, 5 and 6 the femurs, 7 the lower sacrum. Which of each pair is the
# patient's right is read from where it lies, not from its number.
SEG_HIPS, SEG_LUMBAR, SEG_SACRUM, SEG_FEMURS = (1, 2), 3, (4, 7), (5, 6)
MIN_PIECE_VOXELS = 2000                # a piece of the authors' lumbar class smaller than this (2 ml at 1 mm) is no vertebra
NAMED_SHARE = 0.7                      # a piece is named by the TotalSegmentator level holding this share of it, else refused

CAP_MM = 1.0                           # an extreme point is the mean of the points within this of the extreme
APP_TURNS = 50                         # the anterior pelvic plane's turns at most; it stops once the plane repeats
APP_SETTLED_DEG = 0.01
PUBIC_MIDLINE_MM = 45.0                # the pubic tubercles and the symphysis lie within this of the midline
SYMPHYSIS_MM = 6.0                     # a pubis's face is its bone within this of the other pubis, beyond the joint's gap
END_MM = 2.0                           # a face's end is its points within this of the end along the joint's long axis
# The views the foramen is looked for in: pitch toward superior and yaw toward the right from the anterior pelvic
# plane's normal. The first run searched 40 degrees each way and its largest view lay on that edge on every side of
# every specimen (the yaw at the edge in 20 of 20), so the view along the foramen was never reached; the search runs
# far enough now that the largest view can lie inside it, and a view still on its edge is recorded (on_search_edge).
OBTURATOR_PITCH_DEG = tuple(range(-70, 41, 10))
OBTURATOR_YAW_DEG = tuple(range(-80, 81, 10))
TURN_ARC_MM = 8.0                      # a loop's turning at a point is read over this much arc on each side of it
PEAK_ARC_MM = 15.0                     # a corner turns most within this much arc on each side
LOOP_BINS = 360                        # the foramen's outline in the view, resampled by angle round its middle
LOOP_SMOOTH_BINS = 3                   # and smoothed over this many bins on each side
OBTURATOR_ABOVE_MM = 10.0              # the foramen is read on the hip bone below this height over the hip centre
OBTURATOR_AREA_MM2 = (150.0, 4000.0)   # a hole in the silhouette of this area can be the foramen
OBTURATOR_LATERAL_MM = 10.0            # and its middle lies no further than this lateral to the hip centre
RIM_MM = 2.5                           # a 2-D point's bone is the voxels projecting within this of it
NOTCH_BEHIND_MM = 10.0                 # the sciatic notch's concavity lies at least this far behind the hip centre
BALL_MM = (18.0, 32.0)                 # the femoral head's radius lies in this range, as the engine's socket's does
BALL_REACH_MM = 100.0                  # the head lies within the femur's highest 100 mm
S1_BELOW_MM = 4.0                      # the S1 plate's midline layer reaches this far below its plane
S1_GAP_MM = 2.0                        # a gap wider than this along the midline ends the plate (the sacral canal behind)
S1_BELOW_MAX_MM = 20.0                 # an S1 plate further below the lowest lumbar plate than a disc's height is suspect
S1_LATERAL_MAX_MM = 10.0               # and so is one further than this beside the midline
PLATE_BEYOND_LAYERS = 0.5              # plates.py's BEYOND_LAYERS
PLATE_FRONT_SHARE = 0.5                # plates.py's FRONT_SHARE
PLATE_MIN_POINTS = 20                  # plates.py's MIN_POINTS
# A vertebra's chords between its points are set against Panjabi's at its level (the pinned engine's reference table,
# mean, standard error and n, so the spread is sem * sqrt(n)): one further than this many spreads from the mean is no
# body's, and the vertebra's points are marked implausible, kept out of the picture and the S1 plate's reading.
PANJABI_TABLE = ENGINE / "bordercall" / "reference" / "panjabi_full_spine.csv"
PLAUSIBLE_SD = 4.0
# chord -> (the two points it runs between, Panjabi's measure). Panjabi's lumbar tables give no mid-body height, so
# the centre height is held to the posterior height's band: a lumbar body's middle is no taller than its taller wall,
# which at L5 is the front, a few millimetres over the back, and 4 spreads of VBHp are 13 mm at L5.
CHORDS = {"upper_width": (("superior_right", "superior_left"), "endplate"),
          "upper_depth": (("anterior_superior", "posterior_superior"), "endplate_depth"),
          "lower_width": (("inferior_right", "inferior_left"), "endplate_lower"),
          "lower_depth": (("anterior_inferior", "posterior_inferior"), "endplate_lower_depth"),
          "posterior_height": (("posterior_superior", "posterior_inferior"), "h_post"),
          "centre_height": (("centre_superior", "centre_inferior"), "h_post")}

# The four points read on a shape (the obturator foramen's outline, each pubis's face at the symphysis) are each the
# shape's extreme along one direction, given as (lateral, anterior, superior) in one of three frames of the pelvis,
# lateral toward the side's own outside so one direction serves both hips: "anatomical", the anterior pelvic plane
# upright as in a person standing (anatomical_frame); "scanner", the scanner's long axis made square to the hip axis
# (pelvic_frame); "joint", the symphysis's own long axis, its faces' greatest spread. Each entry says why; the numbers
# are DeepFluoro's five specimens' (docs/research/annotator-landmarks/constructions.md). The first was learned from
# them and the others chosen among readings measured on them, so none has a fair error there: `check`'s leave-one-out
# figure holds out only a direction's mean, not the frame or the outline it is read on, which were chosen on all five.
DIRECTIONS = {
    # learned: the person's points lie from the foramen's centre toward the ischium, back and down (both labelings gave
    # (0.24, -0.83, -0.51) and (0.23, -0.83, -0.51), each person's point within a median 9 degrees of it)
    "obturator_inferior": ("anatomical", (0.23, -0.83, -0.51)),
    # the name's words: toward the midline, with the anterior pelvic plane upright
    "obturator_medial": ("anatomical", (-1.0, 0.0, 0.0)),
    # the joint's upper end along its own long axis, the run the bars were set for
    "symphysis_superior": ("joint", (0.0, 0.0, 1.0)),
    # the joint's lowest point along the scanner's long axis, the slice where a person scrolling down sees it end
    "symphysis_inferior": ("scanner", (0.0, 0.0, -1.0)),
}
SHAPED = {"IOF": ("obturator_inferior", "outline"), "MOF": ("obturator_medial", "outline"),
          "SPS": ("symphysis_superior", "face"), "IPS": ("symphysis_inferior", "face")}


# Each construction in plain words, and the QA loop's landmark that stands nearest it (tools/qaloop_gates.py
# LANDMARKS), if any. The QA loop's points of those names are not these: its oracle (grid/autoanatomist/autoanatomist/
# oracle.py body_traces) puts a plate's lateral ends at the whole slab's x-extremes, at the slab's median depth and
# height, and a plate's front end on the whole slab's front surface, where these take the widest row of the plate's
# own layer across its front half and the corners on the midline; `check` measures the two on the same bodies
# (slab_points, qaloop_offsets_mm), and one name stands for one point only once that offset is known to be small.
# A vertebra's names are "<level>.<construction>", the pelvis's "<construction>.<side>" or "<construction>".
CONSTRUCTIONS = {
    "anterior_superior": ("the upper end plate's front end on the midline: column.wall_corner's construction mirrored "
                          "to the front (front_corner), in the plate's own frame", "endplate_depth.anterior"),
    "posterior_superior": ("the upper end plate's back end on the midline, where the posterior wall meets it "
                           "(column.wall_corner)", "endplate_depth.posterior"),
    "anterior_inferior": ("the lower end plate's front end on the midline (front_corner)", "endplate_lower_depth.anterior"),
    "posterior_inferior": ("the lower end plate's back end on the midline (column.wall_corner)",
                           "endplate_lower_depth.posterior"),
    "centre_superior": ("the upper end plate's centre, on its plane at the middle of its central part "
                        "(column.plate_centre); the six-point morphometry's upper middle point", None),
    "centre_inferior": ("the lower end plate's centre (column.plate_centre); the six-point morphometry's lower middle "
                        "point", None),
    "superior_right": ("the upper end plate's right end, on the widest row of its own layer across its front half "
                       "(bordercall plates.py's reading)", "endplate.right"),
    "superior_left": ("the upper end plate's left end (plates.py's reading)", "endplate.left"),
    "inferior_right": ("the lower end plate's right end (plates.py's reading)", "endplate_lower.right"),
    "inferior_left": ("the lower end plate's left end (plates.py's reading)", "endplate_lower.left"),
    "hip_centre": ("the acetabulum's centre: the densest vote of the hip bone's surface normals over radii of 18 to 32 "
                   "mm, refined by a sphere through the socket (pelvis.socket_centre)", None),
    "femoral_head": ("the femoral head's centre: the same vote on the femur's proximal 100 mm with the normals turned "
                     "inward, refined by a sphere through the head (ball_centre)", None),
    "crest_top": ("the iliac crest's highest point along the scanner's long axis (pelvis.crest_top)", None),
    "s1_centre": ("the S1 end plate's centre under the lowest lumbar body (pelvis.s1_plate)", None),
    "s1_anterior": ("the S1 end plate's front end on the midline, the sacral promontory: the plate's layer under its "
                    "plane walked forward from its centre to the first gap (s1_points)", None),
    "s1_posterior": ("the S1 end plate's back end on the midline, walked backward to the sacral canal (s1_points)", None),
    "asis": ("the anterior superior iliac spine: where the anterior pelvic plane, the plane resting on both ilia above "
             "the hip axis and on the pubis in front, touches the ilium (anterior_plane)", None),
    "symphysis_superior": ("the pubic symphysis's upper end on this pubis: the face of its bone within 6 mm of the "
                           "other pubis beyond the joint's gap, its end along the joint's own long axis (symphysis, "
                           "DIRECTIONS)", None),
    "symphysis_inferior": ("the pubic symphysis's lower end on this pubis: the same face's lowest point along the "
                           "scanner's long axis (symphysis, DIRECTIONS)", None),
    "obturator_inferior": ("the obturator foramen's lower end as DeepFluoro's annotators place it: the foramen as the "
                           "largest hole in the silhouette of the hip bone below the hip centre over views within 40 "
                           "degrees of the anterior pelvic plane's normal, its outline in 3-D the middle of the bone "
                           "round the hole's edge in that view, and the outline's extreme toward the ischium, back and "
                           "down with the plane upright (obturator, DIRECTIONS)", None),
    "obturator_medial": ("the obturator foramen's point nearest the midline: the same outline's extreme toward the "
                         "midline with the anterior pelvic plane upright (obturator, DIRECTIONS)", None),
    "obturator_inferior_curvature": ("the obturator foramen's inferior point of maximal curvature, as Grupp et al. 2019 "
                                     "define IOF: of the corners of the foramen's outline in the view that shows it "
                                     "largest (each a point turning most within 15 mm of arc, by more than the loop's "
                                     "mean turning), the lowest with the anterior pelvic plane upright, and the bone "
                                     "there (loop_corners)", None),
    "obturator_medial_curvature": ("the obturator foramen's medial point of maximal curvature, as Grupp et al. 2019 "
                                   "define MOF: of the same corners, the nearest the midline (loop_corners)", None),
    "sciatic_notch": ("the greater sciatic notch's deepest point: the hip bone's outline seen along the hip axis, the "
                      "point of its posterior concavity furthest inside the convex hull, and the bone there "
                      "(sciatic_notch)", None),
}
# DeepFluoro's fourteen (Grupp 2020): each person-placed point and the constructions it is set against.
PERSON = {"FH": ("hip_centre", "femoral_head"), "ASIS": ("asis",), "GSN": ("sciatic_notch",),
          "IOF": ("obturator_inferior", "obturator_inferior_curvature"),
          "MOF": ("obturator_medial", "obturator_medial_curvature"), "SPS": ("symphysis_superior",),
          "IPS": ("symphysis_inferior",)}
# What kind of point each construction gives: "bone", a point fixed on the bone wherever the CT was taken; "pose", an
# extreme along the scanner's long axis, which moves on the bone with the pelvis's tilt on the table (6 to 31 degrees
# against the anterior pelvic plane on DeepFluoro's specimens); "corner", a vertebral point fixed on the bone that
# stands for the corner a film reader marks on the body's silhouette, which moves with the beam and the vertebra's
# rotation (the lumbar posterior wall is concave at the midline, so a lateral film's posterior line runs along the
# posterolateral margins), and is not checked against one here.
POSE_DEPENDENT = ("crest_top", "symphysis_inferior")
VERTEBRAL = ("anterior_superior", "posterior_superior", "anterior_inferior", "posterior_inferior", "centre_superior",
             "centre_inferior", "superior_right", "superior_left", "inferior_right", "inferior_left")


def kind_of(construction):
    if construction in POSE_DEPENDENT:
        return "pose"
    return "corner" if construction in VERTEBRAL else "bone"


SIDE = {"l": "left", "r": "right"}

_E = {}


def engine():
    """The vendored engine's modules, imported once, where it is first needed, so that `persons` runs without scipy."""
    if not _E:
        from scanimport import LEVELS
        from scanimport import geometry as G
        from scanimport import volume as V
        from morphometry import anatomy as A
        from morphometry import body as BODY
        from morphometry import column as COL
        from morphometry import measure as M
        from morphometry import pelvis as PELVIS
        _E.update(LEVELS=LEVELS, G=G, V=V, A=A, BODY=BODY, COL=COL, M=M, PELVIS=PELVIS)
    return _E


def to_lps(point):
    """A RAS world point in LPS: x and y turned."""
    return np.asarray(point, float) * TO_LPS


def unit(v):
    v = np.asarray(v, float)
    return v / max(float(np.linalg.norm(v)), 1e-12)


def angle_deg(a, b):
    return math.degrees(math.acos(min(1.0, abs(float(np.dot(unit(a), unit(b)))))))


def extreme(points, direction, cap=CAP_MM):
    """The mean of the points within cap of the furthest along direction."""
    s = points @ direction
    return points[s >= s.max() - cap].mean(axis=0)


# ---------------------------------------------------------------- reading the labels

@dataclass
class Labelled:
    """A labelled CT as the constructions read it: the spine's labels (vertebrae and sacrum) under names, the grid,
    and each other bone's voxel indices by side."""
    source: str
    vol: np.ndarray
    grid: object
    names: dict
    sacrum: np.ndarray
    hips: dict = field(default_factory=dict)
    femurs: dict = field(default_factory=dict)
    notes: dict = field(default_factory=dict)


def read_mask(path):
    import nibabel as nib
    img = nib.load(str(path))
    return np.asarray(img.dataobj) > 0, np.asarray(img.affine, float)


def read_totalseg(folder, femur_folder=None, s1_folder=None):
    """TotalSegmentator's per-structure masks: the vertebrae and the sacrum into one volume in the ENHANCE.PET ids, the
    hip bones and the femurs by TotalSegmentator's own sides. TotalSegmentator 2's sacrum class leaves the S1 vertebra
    out (on DeepFluoro's specimens 2 to 53 per cent of vertebrae_S1 lies inside sacrum), so vertebrae_S1, from the
    folder or from s1_folder, is joined to the sacrum, as scanimport's TOTALSEG_FILES joins it; without it the engine
    reads the S1 plate on whatever lies lower."""
    G = engine()["G"]
    folder = Path(folder)
    vol, affine, names, notes = None, None, {}, {}
    masks = {}
    for stem in list(TS_SPINE) + ["sacrum", "hip_left", "hip_right"]:
        path = folder / f"{stem}.nii.gz"
        if path.is_file():
            masks[stem] = read_mask(path)
    for place in (folder, Path(s1_folder) if s1_folder else None):
        path = place / "vertebrae_S1.nii.gz" if place is not None else None
        if path is not None and path.is_file() and "vertebrae_S1" not in masks:
            masks["vertebrae_S1"] = read_mask(path)
    for stem in ("femur_left", "femur_right"):
        path = Path(femur_folder) / f"{stem}.nii.gz" if femur_folder else None
        if path is not None and path.is_file():
            masks[stem] = read_mask(path)
    if not masks:
        raise ValueError(f"no TotalSegmentator mask in {folder}")
    for stem, (mask, aff) in masks.items():
        if vol is None:
            vol, affine = np.zeros(mask.shape, np.int16), aff
        if mask.shape != vol.shape or not np.allclose(aff, affine, atol=1e-3):
            raise ValueError(f"{stem} lies on another grid than the other masks")
    for stem, (level, value) in TS_SPINE.items():
        if stem in masks and masks[stem][0].any():
            vol[masks[stem][0]] = value
            names[value] = level
    for stem in ("sacrum", "vertebrae_S1"):
        if stem in masks:
            vol[masks[stem][0] & (vol == 0)] = SACRUM_ID
            names[SACRUM_ID] = "sacrum"
    if "sacrum" in masks and "vertebrae_S1" not in masks:
        notes["sacrum"] = ("no vertebrae_S1 mask: TotalSegmentator 2's sacrum class leaves S1 out, so the S1 plate is "
                           "read on what lies lower")
    side = {s: np.argwhere(masks[f"hip_{s}"][0]) for s in ("left", "right") if f"hip_{s}" in masks}
    femurs = {s: np.argwhere(masks[f"femur_{s}"][0]) for s in ("left", "right") if f"femur_{s}" in masks}
    grid = G.VoxelGrid(affine, vol.shape)
    lab = Labelled("totalseg", vol, grid, names, np.argwhere(vol == SACRUM_ID), side, femurs, notes)
    for part in ("hips", "femurs"):
        swapped = sides_swapped(getattr(lab, part), grid)
        if swapped:
            notes[part] = swapped
    return lab


def sides_swapped(pair, grid):
    """A note where TotalSegmentator's right lies to the left of its left, which would turn every sided point."""
    if len(pair) < 2 or not len(pair["right"]) or not len(pair["left"]):
        return ""
    right_x = grid.world(pair["right"].astype(float)).mean(0)[0]
    left_x = grid.world(pair["left"].astype(float)).mean(0)[0]
    return "" if right_x > left_x else "the mask named right lies to the patient's left of the one named left"


def by_side(groups, grid):
    """Two voxel sets by side, the patient's right the one lying further along RAS x."""
    groups = [g for g in groups if len(g)]
    if len(groups) != 2:
        return {}
    xs = [grid.world(g.astype(float)).mean(0)[0] for g in groups]
    right = int(np.argmax(xs))
    return {"right": groups[right], "left": groups[1 - right]}


def read_deepfluoro(path, reference=None):
    """The dataset authors' own 3-D labels. Their lumbar class holds every vertebra as one label, so it is split into
    its connected pieces, each named by the level of the reference reading (TotalSegmentator's, on the same grid)
    that holds at least NAMED_SHARE of it; a piece joined across two levels, or with no reference, is left unnamed,
    and so out of the vertebrae."""
    from scipy import ndimage
    G = engine()["G"]
    import nibabel as nib
    img = nib.load(str(path))
    seg = np.asarray(img.dataobj).astype(np.int16)
    grid = G.VoxelGrid(np.asarray(img.affine, float), seg.shape)
    hips = by_side([np.argwhere(seg == k) for k in SEG_HIPS], grid)
    femurs = by_side([np.argwhere(seg == k) for k in SEG_FEMURS], grid)
    vol = np.zeros(seg.shape, np.int16)
    vol[np.isin(seg, SEG_SACRUM)] = SACRUM_ID
    names = {SACRUM_ID: "sacrum"} if (vol == SACRUM_ID).any() else {}
    notes = {}
    pieces, n = ndimage.label(seg == SEG_LUMBAR)
    sizes = np.bincount(pieces.ravel())
    ref_ok = reference is not None and reference.vol.shape == seg.shape
    levels = {v: lv for v, lv in reference.names.items() if lv != "sacrum"} if ref_ok else {}
    for k in range(1, n + 1):
        if sizes[k] < MIN_PIECE_VOXELS:
            continue
        if not ref_ok:
            notes["lumbar"] = "no reference reading on the same grid names the authors' lumbar pieces"
            break
        ref = reference.vol[pieces == k]
        counts = {lv: int((ref == v).sum()) for v, lv in levels.items()}
        best = max(counts, key=counts.get) if counts else None
        if best is None or counts[best] < NAMED_SHARE * sizes[k]:
            notes[f"piece_{k}"] = (f"a lumbar piece of {int(sizes[k])} voxels is not named: no TotalSegmentator level "
                                   f"holds {NAMED_SHARE:.0%} of it")
            continue
        if LEVEL_ID[best] in names:
            notes[f"piece_{k}"] = f"a second piece named {best} is left out"
            continue
        vol[pieces == k] = LEVEL_ID[best]
        names[LEVEL_ID[best]] = best
    return Labelled("authors", vol, grid, names, np.argwhere(vol == SACRUM_ID), hips, femurs, notes)


def read_label_file(path, scheme):
    """A label NIfTI read as the engine's measure_file reads it (scanimport.volume.read_labels); the hips are read
    where the scheme names them (ENHANCE.PET's 26 left and 27 right)."""
    E = engine()
    vol, grid, names, problems, _ = E["V"].read_labels(str(path), scheme)
    hips = {}
    if scheme == "enhance":
        hips = {"left": np.argwhere(vol == E["PELVIS"].HIP_LEFT), "right": np.argwhere(vol == E["PELVIS"].HIP_RIGHT)}
        hips = {s: idx for s, idx in hips.items() if len(idx)}
    spine = {v: lv for v, lv in names.items()}
    sacrum = np.argwhere(np.isin(vol, [v for v, lv in names.items() if lv == "sacrum"]))
    return Labelled(scheme, vol, grid, spine, sacrum, hips, {}, {"labels": "; ".join(problems)} if problems else {})


# ---------------------------------------------------------------- the vertebrae

def read_vertebrae(lab):
    """Each vertebra the engine can read, as measure.measure_volume prepares it: the label's main piece, the column's
    line through the neighbours held whole, the neighbours whose end plates set its own axis (anatomy.build)."""
    E = engine()
    A, G, M, V = E["A"], E["G"], E["M"], E["V"]
    vox = V.vertebra_voxels(lab.vol, lab.names)
    for lv in list(vox):
        vox[lv], _ = M.main_piece(vox[lv])
    order = [lv for lv in E["LEVELS"] if lv in vox]
    spine = [lv for lv in order if lv != "sacrum"]
    cents = [lab.grid.world(vox[lv].astype(float)).mean(0) for lv in spine]
    whole = M.whole_levels(vox, spine, lab.vol.shape)
    axes = dict(zip(spine, M.column_line(cents, whole, lab.grid.superior())))
    verts, notes = {}, {}
    for lv in spine:
        if lv in M.SKIP or len(vox[lv]) < G.MIN_BODY_VOXELS:
            continue
        built = {}
        attempt(built, notes, lv, lambda: A.build(lv, vox[lv], lab.grid, axes[lv],
                                                  V.touching_edge(vox[lv], lab.vol.shape),
                                                  M.neighbours_of(vox, order, lv)))
        if lv not in built:
            continue
        if A.usable(built[lv]):
            verts[lv] = built[lv]
        else:
            notes[lv] = built[lv].flags.get("all", "not read")
    return verts, notes


def front_corner(v, top):
    """Where the body's anterior surface meets its upper (or lower) end plate on the midline: column.wall_corner's
    construction mirrored to the front. In the plate's own frame (column.plate_frame), the body's points within 3 mm of
    the midline and 4 mm of the plate's extreme, their anterior surface; the plate the body's extreme along its
    normal. Only the body's points, since nothing is cut from the body's front."""
    E = engine()
    G, COL, BODY = E["G"], E["COL"], E["BODY"]
    f = COL.plate_frame(v, top)
    B = f.local(v.points_world(v.body_pts))
    xc = 0.5 * (B[:, 0].min() + B[:, 0].max())
    mid = B[np.abs(B[:, 0] - xc) <= BODY.ACROSS_HALF_MM]
    zb = B[:, 2].max() if top else B[:, 2].min()
    end = mid[np.abs(mid[:, 2] - zb) <= COL.WALL_END_MM]
    if len(end) < 2:
        return None
    y = G.surface(end[:, 1], True, v.grid.footprint(f.ey))
    return f.origin + xc * f.ex + y * f.ey + G.surface(B[:, 2], top, v.grid.footprint(f.ez)) * f.ez


def widest_front_row(slab, wall, pixel):
    """plates.py's width as its two ends: of the slab's rows across y in the front half of its depth, the widest run of
    cells through the row's middle; its mean y, its right end and its left end (cell edges), or None. Rows as wide as
    the widest are told apart by their nearness to the front half's middle."""
    front = float(slab[:, 1].max())
    reach = front - PLATE_FRONT_SHARE * (front - wall)
    rows = np.floor((slab[:, 1] - slab[:, 1].min()) / pixel).astype(int)
    found = []
    for r in np.unique(rows):
        sel = slab[rows == r]
        if len(sel) < 2 or sel[:, 1].mean() < reach:
            continue
        xm = 0.5 * (sel[:, 0].min() + sel[:, 0].max())
        cells = set(np.floor((sel[:, 0] - xm) / pixel).astype(int).tolist())
        start = 0 if 0 in cells else (-1 if -1 in cells else None)
        if start is None:
            continue
        lo = hi = start
        while lo - 1 in cells:
            lo -= 1
        while hi + 1 in cells:
            hi += 1
        found.append((hi - lo + 1, float(sel[:, 1].mean()), xm + (hi + 1) * pixel, xm + lo * pixel))
    if not found:
        return None
    widest = max(w for w, *_ in found)
    middle = 0.5 * (front + reach)
    _, y, right, left = min((row for row in found if row[0] == widest), key=lambda row: abs(row[1] - middle))
    return y, right, left


def coronal_corners(v):
    """Each end plate's two lateral ends, the corners an anteroposterior reader marks, read as bordercall's plates.py
    reads the plate (its commit 69cae89, not in the pinned copy): the body squared to the canal's wall line, the plate
    the body's points within the end plate's thickness inside its plane (scanimport's plate_plane and ENDPLATE_SHARE)
    and no more than half a layer beyond it, so an uncinate process or a lip rising past the plate is left out; the ends
    those of the widest row across the plate's front half, where no pedicle, rib facet or transverse process stands;
    each end on the plate's plane."""
    E = engine()
    A, G = E["A"], E["G"]
    B = A.square_to_wall(v, v.body_pts)
    fz, pixel = v.fz, v.pixel
    inner = G.central(B[:, 0], B[:, 1])
    t = max(min(max(G.ENDPLATE_SHARE * (float(np.ptp(B[:, 2])) + fz), G.ENDPLATE_MM[0]), G.ENDPLATE_MM[1]), fz)
    out = {}
    for top, name in ((True, "superior"), (False, "inferior")):
        c = G.plate_plane(B, inner, pixel, top, fz)
        d = B[:, 2] - (c[0] + c[1] * B[:, 0] + c[2] * B[:, 1])
        if not top:
            d = -d
        slab = B[(d >= -t - 1e-6) & (d <= PLATE_BEYOND_LAYERS * fz + 1e-6)]
        if len(slab) < PLATE_MIN_POINTS:
            continue
        row = widest_front_row(slab, v.wall_y0, pixel)
        if row is None:
            continue
        y, right, left = row
        for side, x in (("right", right), ("left", left)):
            z = c[0] + c[1] * x + c[2] * y
            local = np.array([[x, y + v.wall_slope * (z - v.wall_z0), z]])     # back from the wall's square
            out[f"{name}_{side}"] = v.points_world(local)[0]
    return out


def back_from_wall(v, local):
    """Points squared to the canal's wall line (anatomy.square_to_wall) back in the world."""
    local = np.array(local, float).reshape(-1, 3)
    local[:, 1] += v.wall_slope * (local[:, 2] - v.wall_z0)
    return v.points_world(local)


def slab_points(v):
    """The QA loop's oracle's end-plate points on this vertebra's own body in its own frame, so the offset between them
    and this tool's corners is the constructions' alone: the steps of oracle.body_traces, which are the engine's
    geometry.body_chords' (the body squared to the wall, each plate the slab within its thickness of the plane resting
    on the central part, and beyond it), with each plate's lateral ends the slab's x-extremes at its median depth and
    height, its front end the slab's front surface and its back end the wall, both at the slab's middle across."""
    E = engine()
    A, G = E["A"], E["G"]
    B = A.square_to_wall(v, v.body_pts)
    fx, fy, fz = (v.grid.footprint(e) for e in (v.frame.ex, v.frame.ey, v.frame.ez))
    if len(B) < G.MIN_BODY_VOXELS:
        return None
    core = B[G.central(B[:, 0], B[:, 1])]
    core = core if len(core) >= G.MIN_CHORD_POINTS else B
    t = max(min(max(G.ENDPLATE_SHARE * (float(np.ptp(core[:, 2])) + fz), G.ENDPLATE_MM[0]), G.ENDPLATE_MM[1]), fz)
    inner = G.central(B[:, 0], B[:, 1])
    out = {}
    for top, name in ((True, "superior"), (False, "inferior")):
        slab = G.plate(B, inner, max(fx, fy), t, top, fz)
        if len(slab) < G.MIN_CHORD_POINTS:
            continue
        right, left = G.surface(slab[:, 0], True, fx), G.surface(slab[:, 0], False, fx)
        yc, zc = float(np.median(slab[:, 1])), float(np.median(slab[:, 2]))
        xc = 0.5 * (float(slab[:, 0].min()) + float(slab[:, 0].max()))
        local = {f"{name}_right": [right, yc, zc], f"{name}_left": [left, yc, zc],
                 f"anterior_{name}": [xc, G.surface(slab[:, 1], True, fy), zc], f"posterior_{name}": [xc, v.wall_y0, zc]}
        out.update({k: back_from_wall(v, q)[0] for k, q in local.items()})
    return out


_PANJABI = {}


def panjabi_reference():
    """Panjabi's mean and spread (sem * sqrt(n)) by (measure, level), from the pinned engine's reference table."""
    if not _PANJABI:
        import csv
        lines = [ln for ln in PANJABI_TABLE.read_text().splitlines() if ln and not ln.startswith("#")]
        for row in csv.DictReader(lines):
            if row["mean"] and row["sem"] and row["n"]:
                _PANJABI[(row["measure"], row["level"])] = (float(row["mean"]), float(row["sem"]) * math.sqrt(float(row["n"])))
    return _PANJABI


def plausibility(level, points):
    """A vertebra's chords between its named points (CHORDS), each against Panjabi's mean at its level in spreads, and
    the chords further than PLAUSIBLE_SD spreads from it: a body no person has, which on DeepFluoro's cadavers came
    from a frame the engine turned onto a neighbour the labels left wrong. Levels Panjabi's tables lack are not
    judged."""
    ref = panjabi_reference()
    chords, wrong = {}, []
    for chord, ((a, b), measure) in CHORDS.items():
        if a not in points or b not in points or (measure, level) not in ref:
            continue
        mean, sd = ref[(measure, level)]
        value = float(np.linalg.norm(np.asarray(points[a], float) - np.asarray(points[b], float)))
        z = (value - mean) / sd
        chords[chord] = {"mm": round(value, 1), "panjabi_mm": mean, "spreads": round(z, 1)}
        if abs(z) > PLAUSIBLE_SD:
            wrong.append(f"{chord} {value:.1f} mm against Panjabi's {mean} (spread {sd:.1f})")
    return {"chords": chords, "plausible": not wrong, "why": "; ".join(wrong)}


def vertebra_points(v):
    """A vertebra's named points (RAS world) and what kept any from being placed."""
    COL = engine()["COL"]
    if v.touching[v.body].any():
        return {}, {"body": "the body touches the volume's edge, so its corners may be the edge's"}
    points, notes = {}, {}
    makers = {"posterior_superior": lambda: COL.wall_corner(v, True),
              "posterior_inferior": lambda: COL.wall_corner(v, False),
              "anterior_superior": lambda: front_corner(v, True),
              "anterior_inferior": lambda: front_corner(v, False),
              "centre_superior": lambda: COL.plate_centre(v, True),
              "centre_inferior": lambda: COL.plate_centre(v, False)}
    if v.level == "C2":                          # the dens stands on the body: no upper plate (measure.no_dens_plate)
        for k in ("posterior_superior", "anterior_superior", "centre_superior"):
            makers.pop(k)
    for name, make in makers.items():
        attempt(points, notes, name, make)
    corners, why = {}, {}
    attempt(corners, why, "coronal", lambda: coronal_corners(v))
    points.update(corners.get("coronal", {}))
    notes.update(why)
    return points, notes


def attempt(points, notes, name, make):
    """One construction: its result where it is placed, its reason in notes where it is not or where it failed, so one
    bone a mask leaves odd does not end a night's run; every failure is written with its error, and the note's
    tables count it as not placed."""
    try:
        got = make()
    except Exception as e:  # noqa: BLE001 - a construction that fails on one mask is recorded, never hidden
        notes[name] = f"failed: {type(e).__name__}: {e}"
        return None
    if got is None or (isinstance(got, dict) and not got):
        notes[name] = "not placed: too few points"
        return None
    points[name] = got
    return got


# ---------------------------------------------------------------- the pelvis

def pelvic_frame(right, left, grid):
    """The pelvis's frame: x through the two hip centres toward the patient's right, z the scanner's long axis made
    square to it, y anterior, origin between the hip centres (as pelvis.incidence takes its axes)."""
    G = engine()["G"]
    ex = unit(right - left)
    up = grid.superior() - (grid.superior() @ ex) * ex
    ez = unit(up)
    return G.Frame(0.5 * (right + left), ex, np.cross(ez, ex), ez)


def anterior_plane(right, left, frame):
    """The anterior pelvic plane and where it rests: the plane touching each ilium above the hip axis and the pubis in
    front, found by turning a plane from the frame's coronal plane until it rests on the bone: each turn takes the
    furthest point along its normal of each ilium's upper part and of both pubes within PUBIC_MIDLINE_MM of the
    midline below the axis, and the next normal is that of the plane through the three. Where it stops turning every
    point of those parts lies behind it, so its two upper contacts are the iliac spines a person palpates and the
    navigation systems' plane rests on (Lewinnek's plane)."""
    upper = {}
    for side, pts in (("right", right), ("left", left)):
        q = frame.local(pts)
        upper[side] = pts[q[:, 2] > 0]
    low = []
    for pts in (right, left):
        q = frame.local(pts)
        low.append(pts[(q[:, 2] < 0) & (np.abs(q[:, 0]) <= PUBIC_MIDLINE_MM)])
    low = np.vstack(low)
    if not len(upper["right"]) or not len(upper["left"]) or not len(low):
        return None
    n = frame.ey.copy()
    turns, settled = 0, False
    for turns in range(1, APP_TURNS + 1):
        ar, al, pub = extreme(upper["right"], n), extreme(upper["left"], n), extreme(low, n)
        m = unit(np.cross(ar - al, pub - al))
        if m @ frame.ey < 0:
            m = -m
        settled = angle_deg(m, n) < APP_SETTLED_DEG
        n = m
        if settled:
            break
    ar, al, pub = extreme(upper["right"], n), extreme(upper["left"], n), extreme(low, n)
    return {"right": ar, "left": al, "pubic": pub, "normal": n, "turns": turns, "settled": settled,
            "tilt_deg": angle_deg(n, frame.ey)}


def principal_axis(points):
    c = points - points.mean(axis=0)
    return np.linalg.eigh(np.cov(c.T))[1][:, -1]


def symphysis(right, left, frames, directions=None):
    """Each pubis's face at the symphysis, and its two named ends: the bone of each hip below the hip axis and within
    PUBIC_MIDLINE_MM of the midline (in frames["anatomical"]) that lies within SYMPHYSIS_MM of the other hip beyond the
    narrowest gap between them, which only the symphysis holds. The faces' greatest spread, taken upward, is the
    joint's long axis and sets frames["joint"]; each end is the mean of its face's points within END_MM of the face's
    extreme along the end's entry in DIRECTIONS.

    Three readings of the ends were measured on DeepFluoro (constructions.md): along the joint's long axis both (the
    run the bars were set for), whose superior end lay a median 4 mm from the person's and inferior end 14 mm; along
    the scanner's long axis, 14 and 3 mm; along the anatomical frame's, 12 and 8 mm. Along the line from the person's
    SPS to the person's IPS, the right pubis's face runs on past the person's IPS by 14.3 and 4.4 mm at its 95th
    percentile and 21.2 and 9.9 mm at its furthest (debug job 40940285, 17-1882 and 18-2799). The table takes the
    superior end from the first reading and the inferior from the second, both chosen on the same points."""
    from scipy.spatial import cKDTree
    G = engine()["G"]
    frame = frames["anatomical"]
    near = {}
    for side, pts in (("right", right), ("left", left)):
        q = frame.local(pts)
        near[side] = pts[(q[:, 2] < 0) & (np.abs(q[:, 0]) <= PUBIC_MIDLINE_MM)]
    if min(len(p) for p in near.values()) < 50:
        return None
    d_right = cKDTree(near["left"]).query(near["right"])[0]
    d_left = cKDTree(near["right"]).query(near["left"])[0]
    gap = float(min(d_right.min(), d_left.min()))
    face = {"right": near["right"][d_right <= gap + SYMPHYSIS_MM], "left": near["left"][d_left <= gap + SYMPHYSIS_MM]}
    axis = principal_axis(np.vstack(list(face.values())))
    axis = unit(axis - (axis @ frame.ex) * frame.ex)
    if axis @ frame.ez < 0:
        axis = -axis
    frames = dict(frames, joint=G.Frame(frame.origin, frame.ex, np.cross(axis, frame.ex), axis))
    out = {"gap_mm": gap, "axis_from_long_deg": angle_deg(axis, frames["scanner"].ez), "frames": frames}
    for side, pts in face.items():
        out[f"face_{side}"] = pts
        out[f"superior_{side}"] = shaped_point(pts, frames, side, "symphysis_superior", directions)
        out[f"inferior_{side}"] = shaped_point(pts, frames, side, "symphysis_inferior", directions)
    return out


def shaped_point(shape, frames, side, construction, directions=None):
    """A shape's extreme along a construction's direction (DIRECTIONS): the mean of its points within END_MM of the
    extreme on a symphysis's face, whose voxels stand in a slab, and within CAP_MM on a foramen's outline."""
    name, vector = (DIRECTIONS if directions is None else directions)[construction]
    cap = END_MM if construction.startswith("symphysis") else CAP_MM
    return extreme(shape, along_direction(frames[name], side, vector), cap)


def along_direction(frame, side, d):
    """A direction given as (lateral, anterior, superior) in the frame, lateral toward the side's own outside, so one
    direction serves the right and the left hip as mirror images."""
    sign = 1.0 if side == "right" else -1.0
    return unit(sign * d[0] * frame.ex + d[1] * frame.ey + d[2] * frame.ez)


def direction_of(frame, side, vector):
    """The inverse of along_direction: a world vector as (lateral, anterior, superior) in the frame, unit length."""
    sign = 1.0 if side == "right" else -1.0
    return unit(np.array([sign * vector @ frame.ex, vector @ frame.ey, vector @ frame.ez]))


def anatomical_frame(frame, normal):
    """The pelvis in the anatomical position: x the hip axis, y the anterior pelvic plane's normal made square to it,
    z up within that plane, so that the plane stands upright as it does in a person standing (Lewinnek), whatever the
    specimen's tilt on the table (7 to 31 degrees on DeepFluoro)."""
    G = engine()["G"]
    ahead = unit(normal - (normal @ frame.ex) * frame.ex)
    return G.Frame(frame.origin, frame.ex, ahead, np.cross(frame.ex, ahead))


def view(frame, pitch_deg, yaw_deg):
    """A view direction near the frame's anterior, tilted by pitch toward superior and by yaw toward the right, and
    the image's axes: u the frame's x made square to it, v upward."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    w = unit(math.cos(p) * (math.cos(y) * frame.ey + math.sin(y) * frame.ex) + math.sin(p) * frame.ez)
    u = unit(frame.ex - (frame.ex @ w) * w)
    return w, u, np.cross(u, w)


def bone_at(points, uv, point2, reach=RIM_MM):
    """The mean of the bone projecting within reach of a 2-D point, widened once where too little does."""
    for r in (reach, 2.0 * reach):
        near = np.linalg.norm(uv - point2, axis=1) <= r
        if near.sum() >= 3:
            return points[near].mean(axis=0)
    return None


def obturator(points, frames, hip_centre, side, directions=None):
    """The obturator foramen's outline in 3-D and its named points. The foramen is the one large hole the hip bone's
    silhouette shows below the acetabulum, as on an anteroposterior film: over views tilted from the frame's anterior
    (the anterior pelvic plane's normal, in pelvis_points) by OBTURATOR_PITCH_DEG toward superior and
    OBTURATOR_YAW_DEG toward the right, the largest enclosed hole of the bone below OBTURATOR_ABOVE_MM over the hip
    centre whose middle lies below the hip centre and no more than OBTURATOR_LATERAL_MM lateral to it. The view showing
    it largest looks along the foramen where it lies inside the search; one on the search's edge is recorded
    (on_search_edge), since there the view along the foramen was not reached. Its outline in 3-D: at each pixel of the
    hole's edge in that view, the mean of the bone projecting within RIM_MM, the middle of the rim's thickness there.
    Two readings of each named point: the outline's extreme along its entry in DIRECTIONS, and the corners of the
    hole's edge in that view as the source defines IOF and MOF, points of maximal curvature (loop_corners).

    Three readings of the inferior point by direction were set aside on DeepFluoro (docs/research/annotator-landmarks/
    constructions.md): the extremes in the oblique view itself (commit 18110ff4, the run the bars were set for), along
    the scanner's long axis and along the anatomical frame's; they lay a median 26, 25 and 11 mm from the person's, the
    person's point standing at the foramen's back lower end, toward the ischium, which the learned direction finds."""
    from scipy import ndimage
    from scipy.spatial import cKDTree
    G = engine()["G"]
    frame = frames["anatomical"]
    q = frame.local(points)
    sel = points[q[:, 2] < frame.local(hip_centre[None, :])[0, 2] + OBTURATOR_ABOVE_MM]
    if len(sel) < 100:
        return None
    sign = 1.0 if side == "right" else -1.0
    best = None
    for pitch in OBTURATOR_PITCH_DEG:
        for yaw in OBTURATOR_YAW_DEG:
            w, u, v = view(frame, pitch, yaw)
            uv = (sel - hip_centre) @ np.column_stack([u, v])
            grid, origin = G.raster(uv, 1.0)
            lab, n = ndimage.label(G.holes(grid))
            for k in range(1, n + 1):
                ij = np.argwhere(lab == k)
                area = float(len(ij))
                centre = origin + ij.mean(0) + 0.5
                lateral = sign * float(centre @ np.array([frame.ex @ u, frame.ex @ v]))
                if not (OBTURATOR_AREA_MM2[0] <= area <= OBTURATOR_AREA_MM2[1]) or centre[1] >= 0:
                    continue
                if lateral > OBTURATOR_LATERAL_MM or (best is not None and area <= best[0]):
                    continue
                edge = (lab == k) & ndimage.binary_dilation(grid, np.ones((3, 3), bool))
                best = (area, pitch, yaw, uv, origin + np.argwhere(edge) + 0.5)
    if best is None:
        return None
    area, pitch, yaw, uv, edge = best
    tree = cKDTree(uv)
    outline = np.array([sel[i].mean(axis=0) for i in tree.query_ball_point(edge, RIM_MM) if len(i) >= 3])
    if len(outline) < 10:
        return None
    on_edge = pitch in (OBTURATOR_PITCH_DEG[0], OBTURATOR_PITCH_DEG[-1]) or yaw in (OBTURATOR_YAW_DEG[0],
                                                                                    OBTURATOR_YAW_DEG[-1])
    out = {"area_mm2": area, "pitch_deg": pitch, "yaw_deg": yaw, "on_search_edge": bool(on_edge),
           "outline_points": len(outline), "outline": outline,
           "inferior": shaped_point(outline, frames, side, "obturator_inferior", directions),
           "medial": shaped_point(outline, frames, side, "obturator_medial", directions)}
    corners = loop_corners(edge)
    bone = [bone_at(sel, uv, c) for c in corners]
    bone = [b for b in bone if b is not None]
    out["corners"] = len(bone)
    if bone:
        local = frame.local(np.array(bone))
        out["inferior_curvature"] = bone[int(np.argmin(local[:, 2]))]
        out["medial_curvature"] = bone[int(np.argmin(sign * local[:, 0]))]
    return out


def loop_corners(edge, half=TURN_ARC_MM, reach=PEAK_ARC_MM):
    """The corners of a hole's edge in a view, its points of maximal curvature: the edge's pixels resampled as a closed
    loop by angle round their middle (LOOP_BINS, smoothed over LOOP_SMOOTH_BINS each side), the angle the loop turns
    through between the chords to its points `half` mm of arc behind and ahead, and each point that turns the most
    within `reach` mm of arc each side and more than the loop's mean turning (a circle has no corner). The foramen is
    near convex, so its edge is one loop round its middle."""
    edge = np.asarray(edge, float)
    if len(edge) < 12:
        return []
    centre = edge.mean(0)
    rel = edge - centre
    bins = np.floor((np.arctan2(rel[:, 1], rel[:, 0]) + math.pi) / (2 * math.pi) * LOOP_BINS).astype(int) % LOOP_BINS
    radius = np.full(LOOP_BINS, np.nan)
    for b in np.unique(bins):
        radius[b] = float(np.linalg.norm(rel[bins == b], axis=1).mean())
    known = np.flatnonzero(np.isfinite(radius))
    every = np.arange(LOOP_BINS)
    radius = np.interp(every, known, radius[known], period=LOOP_BINS)
    k = LOOP_SMOOTH_BINS
    radius = np.mean([np.roll(radius, j) for j in range(-k, k + 1)], axis=0)
    theta = (every + 0.5) / LOOP_BINS * 2 * math.pi - math.pi
    loop = centre + radius[:, None] * np.column_stack([np.cos(theta), np.sin(theta)])
    step = np.linalg.norm(np.roll(loop, -1, axis=0) - loop, axis=1)
    perimeter = float(step.sum())
    arc = np.concatenate([[0.0], np.cumsum(step)[:-1]])
    ahead = np.searchsorted(arc, (arc + half) % perimeter) % LOOP_BINS
    behind = np.searchsorted(arc, (arc - half) % perimeter) % LOOP_BINS
    a, b = loop[ahead] - loop, loop - loop[behind]
    turn = np.arctan2(b[:, 0] * a[:, 1] - b[:, 1] * a[:, 0], (a * b).sum(axis=1))
    mean_turn = 2 * math.pi * 2 * half / perimeter
    corners = []
    for i in range(LOOP_BINS):
        gap = np.abs(arc - arc[i])
        near = np.minimum(gap, perimeter - gap) <= reach
        if turn[i] > mean_turn and turn[i] >= turn[near].max():
            if not corners or np.min([np.linalg.norm(loop[i] - c) for c in corners]) > reach:
                corners.append(loop[i])
    return corners


def hull_mask(silhouette):
    """The pixels inside the convex hull of a silhouette's pixels."""
    from scipy.spatial import ConvexHull, Delaunay
    ij = np.argwhere(silhouette).astype(float)
    hull = Delaunay(ij[ConvexHull(ij).vertices])
    every = np.indices(silhouette.shape).reshape(2, -1).T.astype(float)
    return (hull.find_simplex(every) >= 0).reshape(silhouette.shape)


def sciatic_notch(points, frame, hip_centre):
    """The greater sciatic notch's deepest point. The hip bone seen along the hip axis (the frame's x), as on a
    lateral film of one hemipelvis: its silhouette, the convex hull over it, and the hull's pixels the bone leaves
    empty; of those concavities whose middle lies NOTCH_BEHIND_MM or more behind the hip centre, the empty pixel next
    to the bone furthest inside the hull (by the distance to the hull's outside), which on a hip bone is the apex of
    the greater sciatic notch, the deepest bay of its posterior border between the posterior inferior iliac spine
    and the ischial spine; and the bone projecting within RIM_MM of it."""
    from scipy import ndimage
    G = engine()["G"]
    uv = (points - hip_centre) @ np.column_stack([frame.ey, frame.ez])
    grid, origin = G.raster(uv, 1.0)
    sil = ndimage.binary_fill_holes(ndimage.binary_closing(grid, np.ones((3, 3), bool)))
    inside = hull_mask(sil)
    empty = inside & ~sil
    depth = ndimage.distance_transform_edt(inside)
    touching = empty & ndimage.binary_dilation(sil)
    lab, n = ndimage.label(empty)
    best = None
    for k in range(1, n + 1):
        comp = lab == k
        if float((origin + np.argwhere(comp).mean(0) + 0.5)[0]) > -NOTCH_BEHIND_MM:
            continue
        edge = np.argwhere(comp & touching)
        if not len(edge):
            continue
        d = depth[tuple(edge.T)]
        if best is None or d.max() > best[0]:
            deepest = edge[d >= d.max() - 0.5]          # a round notch's apex is a run of pixels as deep as each other
            best = (float(d.max()), origin + deepest.mean(0) + 0.5)
    if best is None:
        return None
    p = bone_at(points, uv, best[1])
    return None if p is None else {"point": p, "depth_mm": best[0]}


def ball_centre(mask_idx, grid):
    """The femoral head's centre: pelvis.socket_centre's vote turned inside out. Every surface voxel of the femur's
    highest BALL_REACH_MM votes along its inward normal at every radius from 18 to 32 mm; the head is the femur's one
    sphere, whose votes meet at its centre while the neck's and the shaft's spread along their axes; a least-squares
    sphere through the surface points near the vote, whose normals face away from it, refines the centre and gives the
    radius, fitted again on the points within 2 mm of it."""
    PELVIS = engine()["PELVIS"]
    if len(mask_idx) < 1000:
        return None
    height = grid.world(mask_idx.astype(float)) @ grid.superior()
    idx = mask_idx[height >= height.max() - BALL_REACH_MM]
    p, n = PELVIS.surface_normals(idx, grid)
    radii = np.arange(BALL_MM[0], BALL_MM[1] + 1e-9, 1.0)
    votes = (p[:, None, :] - radii[None, :, None] * n[:, None, :]).reshape(-1, 3)
    lo = votes.min(0)
    keys = np.floor((votes - lo) / PELVIS.VOTE_BIN_MM).astype(np.int64)
    dims = keys.max(0) + 1
    flat = (keys[:, 0] * dims[1] + keys[:, 1]) * dims[2] + keys[:, 2]
    best = int(np.argmax(np.bincount(flat)))
    k = np.array([best // (dims[1] * dims[2]), (best // dims[2]) % dims[1], best % dims[2]])
    c0 = lo + (k + 0.5) * PELVIS.VOTE_BIN_MM
    away = p - c0
    dist = np.linalg.norm(away, axis=1)
    facing = (away * n).sum(1) / np.maximum(dist, 1e-9)
    near = (dist >= BALL_MM[0] - 3) & (dist <= BALL_MM[1] + 3) & (facing > 0.9)
    if near.sum() < 50:
        return None
    c, r = PELVIS.fit_sphere(p[near])
    for _ in range(3):
        on = near & (np.abs(np.linalg.norm(p - c, axis=1) - r) <= 2.0)
        if on.sum() < 50:
            break
        c, r = PELVIS.fit_sphere(p[on])
    return {"centre": c, "radius": r, "points": int(near.sum())}


def s1_points(sacrum_idx, grid, low):
    """The S1 end plate's centre (pelvis.s1_plate) and its two ends on the midline. In the plate's own frame (z its
    normal, y toward the lowest lumbar body's front), the sacrum's points within 3 mm of the midline and between
    S1_BELOW_MM under the plane and two layers over it are the plate's layer; walked from the centre forward, and
    backward, until two points lie more than S1_GAP_MM apart (the sacral canal, behind), the run's ends are the plate's
    front end, the promontory, and its back end, each on the layer's surface over its last END_MM. The engine's plate
    is read under the lowest lumbar body only, so a promontory standing further forward than that body is still
    reached by the walk, which is not held to the body's footprint."""
    E = engine()
    G, PELVIS, BODY = E["G"], E["PELVIS"], E["BODY"]
    s1 = PELVIS.s1_plate(sacrum_idx, grid, low)
    if s1 is None:
        return None
    f = G.frame_from(s1["centre"], s1["normal"], low.frame.ey)
    q = f.local(grid.world(sacrum_idx.astype(float)))
    fy, fz = grid.footprint(f.ey), grid.footprint(f.ez)
    layer = q[(np.abs(q[:, 0]) <= BODY.ACROSS_HALF_MM) & (q[:, 2] >= -S1_BELOW_MM) & (q[:, 2] <= 2.0 * fz)]
    out = {"centre": s1["centre"], "normal": s1["normal"]}
    if len(layer) < 10:
        return out
    ys = np.sort(layer[:, 1])
    start = int(np.argmin(np.abs(ys)))
    hi = start
    while hi + 1 < len(ys) and ys[hi + 1] - ys[hi] <= S1_GAP_MM:
        hi += 1
    lo = start
    while lo > 0 and ys[lo] - ys[lo - 1] <= S1_GAP_MM:
        lo -= 1
    run = layer[(layer[:, 1] >= ys[lo]) & (layer[:, 1] <= ys[hi])]
    for name, front in (("anterior", True), ("posterior", False)):
        y = G.surface(run[:, 1], front, fy)
        end = run[run[:, 1] >= y - END_MM] if front else run[run[:, 1] <= y + END_MM]
        z = G.surface(end[:, 2], True, fz)
        out[name] = f.origin + y * f.ey + z * f.ez
    out["depth_mm"] = float(G.surface(run[:, 1], True, fy) - G.surface(run[:, 1], False, fy))
    return out


def s1_against(s1, low, notes, extras):
    """Where the S1 plate's centre lies against the lowest lumbar body's lower plate centre, in that body's frame
    (lateral, ahead, below), and a note where it lies further below than a disc holds or off the midline. On
    DeepFluoro's cadavers that came from a sacrum read without TotalSegmentator's vertebrae_S1 (read_totalseg) and from
    a plate read under L4 where L5 lay (lowest_lumbar); either can still put it there, as can the anatomy."""
    COL = engine()["COL"]
    try:
        offset = low.frame.local(s1["centre"][None, :])[0] - low.frame.local(COL.plate_centre(low, False)[None, :])[0]
    except Exception as e:  # noqa: BLE001 - the offset is a record; its failure is noted, never hidden
        notes["s1_offset"] = f"failed: {type(e).__name__}: {e}"
        return
    extras["s1_offset_mm"] = {"lateral": float(offset[0]), "ahead": float(offset[1]), "below": float(-offset[2])}
    if -offset[2] > S1_BELOW_MAX_MM or abs(offset[0]) > S1_LATERAL_MAX_MM:
        notes["s1"] = (f"the S1 plate's centre lies {-offset[2]:.0f} mm below and {abs(offset[0]):.0f} mm beside "
                       f"{low.level}'s lower plate centre, where no lumbosacral disc puts it")


def lowest_lumbar(names, verts, plausible):
    """The vertebra the S1 plate is read under: the lowest lumbar level the labels hold, L6 or L5, where the engine
    read it and its chords are a body's; else None and why. The first run fell back to L4 where the labels held an L5
    the engine could not read, and read the sacrum under L4, where L5 lies."""
    held = set(names.values())
    low = next((lv for lv in ("L6", "L5") if lv in held), None)
    if low is None:
        return None, "the labels hold no L5, so nothing says where the sacrum's top is"
    if low not in verts:
        return None, f"the engine did not read {low}, the lowest lumbar level the labels hold"
    if low not in plausible:
        return None, f"{low}'s chords are no body's (plausibility), so its frame cannot place the S1 plate"
    return low, ""


def pelvis_points(lab, verts, shapes=None, plausible=None):
    """The pelvis's named points (RAS world), what kept any from being placed, and the constructions' own readings
    (the plane's tilt, the joint's gap, the foramen's view) for the record; where shapes is given it is filled with the
    anatomical frame, the foramina's outlines and the symphysis's faces, for the check's calibration."""
    PELVIS = engine()["PELVIS"]
    points, notes, extras = {}, {}, {}
    hips, kept = {}, {}
    long_axis = int(np.argmax(np.abs(lab.grid.axes.T @ lab.grid.superior())))
    for side, idx in lab.hips.items():
        got = attempt(kept, notes, f"hip_centre.{side}", lambda: PELVIS.socket_centre(idx, lab.grid))
        if got is None:
            continue
        hips[side] = got
        points[f"hip_centre.{side}"] = got["centre"]
        extras[f"acetabulum_radius.{side}"] = got["radius"]
        attempt(points, notes, f"crest_top.{side}", lambda: PELVIS.crest_top(idx, lab.grid))
        if (idx[:, long_axis] == lab.vol.shape[long_axis] - 1).any() or (idx[:, long_axis] == 0).any():
            notes[f"crest_top.{side}"] = "the hip bone touches the volume's end along its long axis: the crest may be cut"
    for side, idx in lab.femurs.items():
        got = attempt(kept, notes, f"femoral_head.{side}", lambda: ball_centre(idx, lab.grid))
        if got is not None:
            points[f"femoral_head.{side}"] = got["centre"]
            extras[f"femoral_head_radius.{side}"] = got["radius"]
    low, why_not = lowest_lumbar(lab.names, verts, set(verts) if plausible is None else plausible)
    if low is not None and len(lab.sacrum) >= 1000:
        s1 = attempt(kept, notes, "s1", lambda: s1_points(lab.sacrum, lab.grid, verts[low]))
        if s1 is not None:
            s1_against(s1, verts[low], notes, extras)
            points["s1_centre"] = s1["centre"]
            for end in ("anterior", "posterior"):
                if end in s1:
                    points[f"s1_{end}"] = s1[end]
            if "depth_mm" in s1:
                extras["s1_depth_mm"] = s1["depth_mm"]
    else:
        notes["s1"] = why_not or "no sacrum"
    if len(hips) < 2:
        notes["pelvis"] = "both acetabula are needed for the pelvis's frame"
        return points, notes, extras
    frame = pelvic_frame(hips["right"]["centre"], hips["left"]["centre"], lab.grid)
    bone = {s: lab.grid.world(idx.astype(float)) for s, idx in lab.hips.items()}
    app = attempt(kept, notes, "asis", lambda: anterior_plane(bone["right"], bone["left"], frame))
    anat = frame
    if app is not None:
        anat = anatomical_frame(frame, app["normal"])
        points["asis.right"], points["asis.left"] = app["right"], app["left"]
        extras.update(app_turns=app["turns"], app_settled=app["settled"], app_tilt_deg=app["tilt_deg"])
    frames = {"scanner": frame, "anatomical": anat}
    if shapes is not None:
        shapes["frames"] = frames
    sym = attempt(kept, notes, "symphysis", lambda: symphysis(bone["right"], bone["left"], frames))
    if sym is not None:
        if shapes is not None:
            shapes["frames"] = sym["frames"]
        for side in ("right", "left"):
            points[f"symphysis_superior.{side}"] = sym[f"superior_{side}"]
            points[f"symphysis_inferior.{side}"] = sym[f"inferior_{side}"]
            if shapes is not None:
                shapes[f"face.{side}"] = sym[f"face_{side}"]
        extras.update(symphysis_gap_mm=sym["gap_mm"], symphysis_axis_deg=sym["axis_from_long_deg"])
    for side in ("right", "left"):
        ob = attempt(kept, notes, f"obturator.{side}", lambda: obturator(bone[side], frames, hips[side]["centre"], side))
        if ob is not None:
            for end in ("inferior", "medial", "inferior_curvature", "medial_curvature"):
                if end in ob:
                    points[f"obturator_{end}.{side}"] = ob[end]
            if shapes is not None:
                shapes[f"outline.{side}"] = ob["outline"]
            extras[f"obturator_view.{side}"] = {k: ob[k] for k in ("area_mm2", "pitch_deg", "yaw_deg", "on_search_edge",
                                                                   "outline_points", "corners")}
        notch = attempt(kept, notes, f"sciatic_notch.{side}",
                        lambda: sciatic_notch(bone[side], frame, hips[side]["centre"]))
        if notch is not None:
            points[f"sciatic_notch.{side}"] = notch["point"]
            extras[f"sciatic_notch_depth_mm.{side}"] = notch["depth_mm"]
    return points, notes, extras


def construction_of(name):
    """The construction a point's name comes from: '<level>.<c>' or '<c>.<side>' or '<c>'."""
    head, _, tail = name.partition(".")
    return tail if tail in CONSTRUCTIONS else head


def construct(lab, shapes=None):
    """Every named point of a labelled CT, in LPS world millimetres, with its construction, its QA loop landmark and
    the notes of what was not placed; and the vertebrae read, for drawing. shapes, where given, is filled as
    pelvis_points fills it."""
    verts, vnotes = read_vertebrae(lab)
    points, notes = {}, {f"{lv}": why for lv, why in vnotes.items()}
    chords, slabs, plausible = {}, {}, set()
    for lv, v in verts.items():
        got, why = vertebra_points(v)
        points.update({f"{lv}.{k}": p for k, p in got.items()})
        notes.update({f"{lv}.{k}": w for k, w in why.items()})
        judged = plausibility(lv, got)
        chords[lv] = dict(judged, engine={k: float(v.panjabi.get(k, float("nan"))) for k in
                                          ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
                                           "h_post")})
        if judged["plausible"]:
            plausible.add(lv)
        else:
            notes[f"{lv}.plausibility"] = f"no body's chords: {judged['why']}"
        slab = {}
        attempt(slab, notes, f"{lv}.slab", lambda: slab_points(v))
        slabs[lv] = {k: to_lps(p).round(3).tolist() for k, p in slab.get(f"{lv}.slab", {}).items()}
    got, why, extras = pelvis_points(lab, verts, shapes, plausible)
    points.update(got)
    notes.update(why)
    notes.update({f"labels.{k}": w for k, w in lab.notes.items()})
    extras["vertebra_chords"] = chords
    named = {}
    for name, p in points.items():
        c = construction_of(name)
        named[name] = {"lps": [round(float(x), 3) for x in to_lps(p)], "construction": c,
                       "qaloop_near": CONSTRUCTIONS[c][1], "kind": kind_of(c)}
        level = name.split(".")[0]
        if level in verts:
            named[name]["plausible"] = level in plausible
    return {"frame": "world millimetres, LPS (x to the patient's left, y posterior, z superior)", "source": lab.source,
            "levels": sorted(verts, key=engine()["LEVELS"].index), "plausible_levels": sorted(plausible),
            "points": named, "slab_points": slabs, "notes": notes, "extras": jsonable(extras)}


def jsonable(x):
    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, (np.floating, float)):
        return round(float(x), 3)
    if isinstance(x, (np.integer, int)) and not isinstance(x, bool):
        return int(x)
    if isinstance(x, np.ndarray):
        return [jsonable(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    return x


# ---------------------------------------------------------------- the person's points (h5py, the grid's fluorogen)

def refuse_held_out(cases):
    held = [c for c in cases if c in HELD_OUT]
    if held:
        raise ValueError(f"{', '.join(held)} is the QA loop's held-out test specimen and is never read")
    return list(cases)


def persons(h5, out, cases=CASES):
    """The fourteen vol-landmarks a person placed in each named specimen's CT, as the release holds them (the
    volume's world frame, which is ct.nii.gz's world in LPS); nothing else of the file is read."""
    import h5py
    cases = refuse_held_out(cases)
    record = {"h5": str(h5), "h5_bytes": Path(h5).stat().st_size, "frame": "the release's volume world, LPS mm",
              "held_out_never_read": list(HELD_OUT), "cases": {}}
    with h5py.File(str(h5), "r") as f:
        for case in cases:
            g = f[case]
            marks = {k: [float(x) for x in np.array(g["vol-landmarks"][k], np.float64).ravel()[:3]]
                     for k in sorted(g["vol-landmarks"].keys())}
            vol = {k: np.array(g["vol"][k]).tolist() for k in ("origin", "spacing", "dir-mat") if k in g["vol"]}
            record["cases"][case] = {"landmarks": marks, "vol": vol}
            print(f"{case}: {len(marks)} landmarks", flush=True)
    Path(out).write_text(json.dumps(record, indent=1))
    return record


# ---------------------------------------------------------------- the check against the person's points

def person_rows(case, person, readings):
    """One row per person-placed point and construction: the 3-D distance from the person's point to each source's
    construction, and from one source's construction to the other's."""
    rows = []
    for name, p in sorted(person.items()):
        kind, _, letter = name.partition("-")
        letter = letter.lower()
        if kind not in PERSON or letter not in SIDE:
            continue
        for c in PERSON[kind]:
            key = f"{c}.{SIDE[letter]}"
            row = {"case": case, "landmark": name, "construction": c}
            got = {}
            for source, reading in readings.items():
                q = reading["points"].get(key)
                row[source] = round(float(np.linalg.norm(np.array(q["lps"]) - np.array(p))), 2) if q else None
                got[source] = q
            if all(got.values()) and len(got) == 2:
                a, b = [np.array(q["lps"]) for q in got.values()]
                row["between_sources"] = round(float(np.linalg.norm(a - b)), 2)
            rows.append(row)
    return rows


def summary(rows, sources):
    """Per person-placed point and construction, and per kind with both sides pooled: each source's median, maximum
    and count of distances, and whether its median meets AGREE_MM."""
    out = []
    groups = {}
    for r in rows:
        groups.setdefault((r["landmark"], r["construction"]), []).append(r)
        groups.setdefault((r["landmark"].split("-")[0] + " (both sides)", r["construction"]), []).append(r)
    for (landmark, c), rs in sorted(groups.items()):
        line = {"landmark": landmark, "construction": c}
        for s in sources + ["between_sources"]:
            d = np.array([r[s] for r in rs if r.get(s) is not None], float)
            line[s] = {"median": round(float(np.median(d)), 1) if len(d) else None,
                       "max": round(float(d.max()), 1) if len(d) else None, "n": int(len(d))}
            if s != "between_sources" and len(d):
                line[s]["agrees"] = bool(np.median(d) <= AGREE_MM)
        out.append(line)
    return out


def frame_check(person, lab):
    """How far each person-placed point lies from the nearest voxel of the authors' bone labels: a few millimetres
    where the points and the CT share one frame, tens where they do not."""
    from scipy.spatial import cKDTree
    bone = np.vstack([idx for idx in list(lab.hips.values()) + list(lab.femurs.values()) + [lab.sacrum] if len(idx)])
    tree = cKDTree(lab.grid.world(bone.astype(float)))
    return {name: round(float(tree.query(np.asarray(p) * TO_LPS)[0]), 2) for name, p in person.items()}


def vertebra_agreement(readings):
    """For the vertebral and sacral points both sources placed, on vertebrae both read as a body's (plausibility), the
    distance between the two."""
    a, b = [r["points"] for r in readings.values()]
    out = {}
    for name in sorted(set(a) & set(b)):
        if not (name.startswith("s1_") or name.split(".")[0] in engine()["LEVELS"]):
            continue
        if a[name].get("plausible") is False or b[name].get("plausible") is False:
            continue
        out[name] = round(float(np.linalg.norm(np.array(a[name]["lps"]) - np.array(b[name]["lps"]))), 2)
    return out


def qaloop_offsets(reading):
    """For each vertebral corner with a QA loop name, on vertebrae read as a body's, the distance from this tool's
    construction to the QA loop oracle's construction of that name on the same body (slab_points), mm."""
    out = {}
    for lv, slab in reading.get("slab_points", {}).items():
        if lv not in reading.get("plausible_levels", []):
            continue
        for c, q in slab.items():
            mine = reading["points"].get(f"{lv}.{c}")
            if mine is not None:
                out[f"{lv}.{c}"] = round(float(np.linalg.norm(np.array(mine["lps"]) - np.array(q))), 2)
    return out


def promontory_offsets(reading):
    """The promontory against L5's lower plate, the check the old sacral anchor failed (docs/research/qa-loop-external):
    the S1 plate's front end less L5's lower plate centre and less L5's anterior-inferior corner, along the line from
    L5's lower plate's back end to its front end (the plate's own anterior), in mm."""
    p = reading["points"]
    low = next((lv for lv in ("L6", "L5") if f"{lv}.anterior_inferior" in p and f"{lv}.posterior_inferior" in p
                and p[f"{lv}.anterior_inferior"].get("plausible", True)), None)
    if low is None or "s1_anterior" not in p or "s1" in reading.get("notes", {}):
        return None
    front, back = np.array(p[f"{low}.anterior_inferior"]["lps"]), np.array(p[f"{low}.posterior_inferior"]["lps"])
    ahead = unit(front - back)
    prom = np.array(p["s1_anterior"]["lps"])
    out = {"level": low, "ahead_of_corner_mm": round(float((prom - front) @ ahead), 2),
           "gap_to_corner_mm": round(float(np.linalg.norm(prom - front)), 2)}
    if f"{low}.centre_inferior" in p:
        out["ahead_of_centre_mm"] = round(float((prom - np.array(p[f"{low}.centre_inferior"]["lps"])) @ ahead), 2)
    return out


def check(data, persons_path, out, cases=CASES, pictures=2):
    """The constructions on TotalSegmentator's masks and on the authors' own labels, set against the person's points,
    specimen by specimen; check.json and table.md in out, and a picture of the first specimens."""
    cases = refuse_held_out(cases)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    marks = json.loads(Path(persons_path).read_text())["cases"]
    rows, per_case, drawn, shapes = [], {}, [], {}
    for case in cases:
        folder = Path(data) / case
        ts = read_totalseg(folder / "ts", folder / "ts_femur", folder / "ts_s1")
        authors = read_deepfluoro(folder / "vol_seg.nii.gz", reference=ts)
        shapes[case] = {"totalseg": {}, "authors": {}}
        readings = {"totalseg": construct(ts, shapes[case]["totalseg"]),
                    "authors": construct(authors, shapes[case]["authors"])}
        person = marks[case]["landmarks"]
        rows += person_rows(case, person, readings)
        per_case[case] = {"readings": readings, "frame_check_mm": frame_check(person, authors),
                          "vertebra_agreement_mm": vertebra_agreement(readings),
                          "qaloop_offsets_mm": {s: qaloop_offsets(r) for s, r in readings.items()},
                          "promontory": {s: promontory_offsets(r) for s, r in readings.items()}}
        (out / f"{case}.json").write_text(json.dumps(per_case[case], indent=1))
        print(f"{case}: {len(readings['totalseg']['points'])} points on TotalSegmentator, "
              f"{len(readings['authors']['points'])} on the authors' labels", flush=True)
        if len(drawn) < pictures:
            drawn.append(panel(folder / "ct.nii.gz", case, person, readings))
    table = summary(rows, ["totalseg", "authors"])
    learned = calibrate(shapes, marks, cases)
    report = {"cases": cases, "held_out_never_read": list(HELD_OUT), "agree_mm": AGREE_MM, "rows": rows,
              "summary": table, "calibration": learned, "frame_check_mm": {c: v["frame_check_mm"] for c, v in per_case.items()},
              "vertebra_agreement_mm": {c: v["vertebra_agreement_mm"] for c, v in per_case.items()},
              "qaloop_offsets_mm": {c: v["qaloop_offsets_mm"] for c, v in per_case.items()},
              "qaloop_offsets_summary": offsets_summary(per_case),
              "promontory": {c: v["promontory"] for c, v in per_case.items()},
              "extras": {c: {s: r["extras"] for s, r in v["readings"].items()} for c, v in per_case.items()},
              "notes": {c: {s: r["notes"] for s, r in v["readings"].items()} for c, v in per_case.items()}}
    (out / "check.json").write_text(json.dumps(report, indent=1))
    (out / "table.md").write_text(markdown(table) + "\n" + calibration_markdown(learned) + "\n"
                                  + vertebra_markdown(per_case) + "\n"
                                  + offsets_markdown(report["qaloop_offsets_summary"]))
    if drawn:
        save_panels(drawn, out / "constructions.png")
    print(markdown(table))
    return report


def offsets_summary(per_case):
    """The QA loop offsets pooled over specimens and levels by construction and source: median, maximum and n, mm."""
    out = {}
    for v in per_case.values():
        for source, offsets in v["qaloop_offsets_mm"].items():
            for name, d in offsets.items():
                out.setdefault(name.split(".", 1)[1], {}).setdefault(source, []).append(d)
    return {c: {s: distances(d) for s, d in by.items()} for c, by in sorted(out.items())}


def vertebra_markdown(per_case):
    lines = ["| case | source | level | a body's? | chords, mm (spreads from Panjabi's mean) |", "|---|---|---|---|---|"]
    for case, v in per_case.items():
        for source, reading in v["readings"].items():
            for lv, got in reading["extras"].get("vertebra_chords", {}).items():
                cells = ", ".join(f"{k} {c['mm']} ({c['spreads']:+})" for k, c in got["chords"].items())
                lines.append(f"| {case} | {source} | {lv} | {'yes' if got['plausible'] else 'no'} | {cells} |")
    return "\n".join(lines) + "\n"


def offsets_markdown(by_construction):
    def cell(s):
        return "" if not s or s["median"] is None else f"{s['median']} / {s['max']} / {s['n']}"
    lines = ["| construction | QA loop name | TotalSegmentator (median / max / n, mm) | authors' labels |",
             "|---|---|---|---|"]
    for c, by in by_construction.items():
        lines.append(f"| {c} | {CONSTRUCTIONS[c][1]} | {cell(by.get('totalseg'))} | {cell(by.get('authors'))} |")
    return "\n".join(lines) + "\n"


def person_direction(shape, frame, side, point_lps):
    """The direction in which a person's point lies from a shape's centre, as (lateral, anterior, superior)."""
    return direction_of(frame, side, np.asarray(point_lps, float) * TO_LPS - shape.mean(axis=0))


def calibrate(shapes, marks, cases):
    """For each of the four points read on a shape (SHAPED), in the frame its DIRECTIONS entry names: the direction in
    which the person's points lie from the shape's centre, learned from the other specimens (both sides, mirrored) and
    used on the one left out, so a learned reading is judged only on specimens it never saw; beside it the distance
    with the table's own direction ("table", which for a direction the table took from these specimens is not a fair
    error); and the direction learned from every specimen, with each person's point's angle from it."""
    out = {"leave_one_out": {}, "table": {}, "learned_from_all": {}}
    for source in ("totalseg", "authors"):
        dirs = {}                        # (kind, case, side) -> the person's direction, where shape and point exist
        for kind, (construction, shape_name) in SHAPED.items():
            for case in cases:
                sh = shapes.get(case, {}).get(source, {})
                for letter, side in SIDE.items():
                    name = f"{kind}-{letter}"
                    point = marks[case]["landmarks"].get(name)
                    if f"{shape_name}.{side}" in sh and point is not None:
                        frame = sh["frames"][DIRECTIONS[construction][0]]
                        dirs[(kind, case, side)] = person_direction(sh[f"{shape_name}.{side}"], frame, side, point)
        for kind, (construction, shape_name) in SHAPED.items():
            rows, plain = [], []
            for k, case, side in sorted(dirs):
                if k != kind:
                    continue
                others = [d for (k2, c2, _), d in dirs.items() if k2 == kind and c2 != case]
                if not others:
                    continue
                sh = shapes[case][source]
                pts = sh[f"{shape_name}.{side}"]
                truth = np.asarray(marks[case]["landmarks"][f"{kind}-{side[0]}"], float) * TO_LPS
                learned = {construction: (DIRECTIONS[construction][0], unit(np.mean(others, axis=0)))}
                rows.append(float(np.linalg.norm(shaped_point(pts, sh["frames"], side, construction, learned) - truth)))
                plain.append(float(np.linalg.norm(shaped_point(pts, sh["frames"], side, construction) - truth)))
            out["leave_one_out"].setdefault(kind, {})[source] = distances(rows)
            out["table"].setdefault(kind, {})[source] = distances(plain)
            every = [d for (k, _, _), d in dirs.items() if k == kind]
            if every:
                mean = unit(np.mean(every, axis=0))
                spread = float(np.median([angle_deg(mean, d) for d in every]))
                out["learned_from_all"].setdefault(kind, {})[source] = {
                    "frame": DIRECTIONS[construction][0], "direction": [round(float(x), 3) for x in mean],
                    "median_angle_off_deg": round(spread, 1), "n": len(every)}
    return out


def distances(d):
    d = np.asarray(d, float)
    if not len(d):
        return {"median": None, "max": None, "n": 0}
    return {"median": round(float(np.median(d)), 1), "max": round(float(d.max()), 1), "n": int(len(d)),
            "agrees": bool(np.median(d) <= AGREE_MM)}


def calibration_markdown(learned):
    def cell(s):
        return "" if s["median"] is None else f"{s['median']} / {s['max']} / {s['n']}"
    lines = ["| landmark | reading | TotalSegmentator (median / max / n, mm) | authors' labels |", "|---|---|---|---|"]
    for kind in SHAPED:
        for reading, key in (("the table's direction", "table"), ("learned, leaving the specimen out", "leave_one_out")):
            got = learned[key].get(kind, {})
            if got:
                lines.append(f"| {kind} | {reading} | {cell(got['totalseg'])} | {cell(got['authors'])} |")
    return "\n".join(lines) + "\n"


def markdown(table):
    def cell(s):
        return "" if s["median"] is None else f"{s['median']} / {s['max']} / {s['n']}"
    lines = ["| landmark | construction | TotalSegmentator (median / max / n, mm) | authors' labels | between the two |",
             "|---|---|---|---|---|"]
    for t in table:
        lines.append(f"| {t['landmark']} | {t['construction']} | {cell(t['totalseg'])} | {cell(t['authors'])} | "
                     f"{cell(t['between_sources'])} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- the picture

PANEL_HEIGHT = 440
COLOURS = {"person": (60, 230, 60), "totalseg": (255, 60, 60), "authors": (70, 160, 255), "spine": (255, 170, 30)}


def panel(ct_path, case, person, readings):
    """The CT's mean along its anterior-posterior axis, bone's attenuation only (HU clipped to 0..1500), the patient's
    right on the left and superior up as on an anteroposterior film, with the person's points (green rings), the
    constructions set against them on TotalSegmentator's masks (red crosses) and on the authors' labels (blue diagonal
    crosses), and TotalSegmentator's vertebral points (orange dots) on the vertebrae whose chords are a body's
    (plausibility), with its S1 plate's points where they are not flagged (s1_against)."""
    import nibabel as nib
    from PIL import Image, ImageDraw
    img = nib.load(str(ct_path))
    affine = np.asarray(img.affine, float)
    axes = np.abs(affine[:3, :3] / np.linalg.norm(affine[:3, :3], axis=0))
    ax_x, ax_y, ax_z = (int(np.argmax(axes[r])) for r in range(3))
    ct = np.clip(np.asarray(img.dataobj, np.float32), 0.0, 1500.0).mean(axis=ax_y)
    keep = sorted([ax_x, ax_z])
    image = ct if keep == [ax_x, ax_z] else ct.T                  # rows along x, columns along z
    lo, hi = np.percentile(image, [1, 99.7])
    grey = np.clip((image - lo) / max(hi - lo, 1e-6), 0, 1)
    flip_x = affine[0, ax_x] > 0                                  # index growing toward the patient's right
    flip_z = affine[2, ax_z] > 0                                  # index growing upward
    pic = grey.T                                                  # rows along z, columns along x
    pic = pic[::-1] if flip_z else pic
    pic = pic[:, ::-1] if flip_x else pic
    sx, sz = np.linalg.norm(affine[:3, ax_x]), np.linalg.norm(affine[:3, ax_z])
    width = int(round(pic.shape[1] * sx * PANEL_HEIGHT / (pic.shape[0] * sz)))
    scale = (width / pic.shape[1], PANEL_HEIGHT / pic.shape[0])
    im = Image.fromarray((pic * 255).astype(np.uint8)).resize((width, PANEL_HEIGHT)).convert("RGB")
    inv = np.linalg.inv(affine)
    nx, nz = image.shape

    def at(lps):
        ijk = inv[:3, :3] @ (np.asarray(lps, float) * TO_LPS) + inv[:3, 3]
        col = (nx - 1 - ijk[ax_x]) if flip_x else ijk[ax_x]
        row = (nz - 1 - ijk[ax_z]) if flip_z else ijk[ax_z]
        return (col + 0.5) * scale[0], (row + 0.5) * scale[1]

    d = ImageDraw.Draw(im)
    flagged_s1 = "s1" in readings["totalseg"]["notes"]
    for name, q in readings["totalseg"]["points"].items():
        vertebral = name[:1] in "TL" and "." in name and q.get("plausible", False)
        if vertebral or (name.startswith("s1_") and not flagged_s1):
            u, v = at(q["lps"])
            d.ellipse([u - 1.5, v - 1.5, u + 1.5, v + 1.5], fill=COLOURS["spine"])
    for name, p in person.items():
        u, v = at(p)
        d.ellipse([u - 6, v - 6, u + 6, v + 6], outline=COLOURS["person"], width=2)
        d.text((u + 7, v - 5), name, fill=COLOURS["person"])
    wanted = set()
    for n in person:
        kind, _, letter = n.partition("-")
        if letter.lower() in SIDE:
            wanted |= {f"{c}.{SIDE[letter.lower()]}" for c in PERSON.get(kind, ())}
    for source, mark in (("totalseg", "+"), ("authors", "x")):
        for name in wanted:
            q = readings[source]["points"].get(name)
            if q is None:
                continue
            u, v = at(q["lps"])
            c = COLOURS[source]
            if mark == "+":
                d.line([u - 5, v, u + 5, v], fill=c, width=2)
                d.line([u, v - 5, u, v + 5], fill=c, width=2)
            else:
                d.line([u - 4, v - 4, u + 4, v + 4], fill=c, width=2)
                d.line([u - 4, v + 4, u + 4, v - 4], fill=c, width=2)
    d.text((6, 6), f"{case}: CT mean along A-P, patient's right on the left", fill=(255, 255, 0))
    d.text((6, 20), "green ring: a person's point; red +: on TotalSegmentator; blue x: on the authors' labels",
           fill=(255, 255, 0))
    d.text((6, 34), "orange dots: corners and plate centres of vertebrae read as a body's, and S1, on TotalSegmentator",
           fill=(255, 255, 0))
    return im


def save_panels(panels, path, limit=300_000):
    """The panels side by side, as a palette PNG kept under limit bytes."""
    from PIL import Image
    width = sum(p.width for p in panels) + 8 * (len(panels) - 1)
    sheet = Image.new("RGB", (width, PANEL_HEIGHT), "black")
    x = 0
    for p in panels:
        sheet.paste(p, (x, 0))
        x += p.width + 8
    for colours in (128, 64, 32):
        sheet.quantize(colours).save(path, optimize=True)
        if Path(path).stat().st_size <= limit:
            break
    return Path(path).stat().st_size


# ---------------------------------------------------------------- the command line

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("points", help="the named points of one labelled CT")
    p.add_argument("--ts", help="a TotalSegmentator folder of per-structure masks")
    p.add_argument("--femur", help="TotalSegmentator's femur masks, where they are in another folder")
    p.add_argument("--s1", help="the folder of TotalSegmentator's vertebrae_S1 mask, where it is in another folder")
    p.add_argument("--labels", help="a label NIfTI")
    p.add_argument("--scheme", default="enhance", help="its scheme, as scanimport names them")
    p.add_argument("--out", required=True)
    p = sub.add_parser("persons", help="DeepFluoro's person-placed points, under a Python with h5py")
    p.add_argument("--h5", required=True)
    p.add_argument("--cases", default=",".join(CASES))
    p.add_argument("--out", required=True)
    p = sub.add_parser("check", help="the constructions against the person's points, on the grid")
    p.add_argument("--data", required=True, help="realxray_work/deepfluoro")
    p.add_argument("--persons", required=True)
    p.add_argument("--cases", default=",".join(CASES))
    p.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "points":
        if bool(a.ts) == bool(a.labels):
            ap.error("give --ts or --labels")
        lab = read_totalseg(a.ts, a.femur or a.ts, a.s1) if a.ts else read_label_file(a.labels, a.scheme)
        Path(a.out).write_text(json.dumps(construct(lab), indent=1))
    elif a.cmd == "persons":
        persons(a.h5, a.out, a.cases.split(","))
    else:
        check(a.data, a.persons, a.out, a.cases.split(","))


if __name__ == "__main__":
    main()
