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
- per vertebra, from the engine's own reading of it (anatomy.build): the four corners a lateral reader marks on the
  midline (column.wall_corner behind, the same construction mirrored to the front in front_corner), the two end-plate
  centres (column.plate_centre, the middle points of Genant's and Black and McCloskey's six-point morphometry), and the
  four corners an anteroposterior reader marks, each plate's lateral ends on its own layer (coronal_corners);
- the pelvis from the engine's pelvis.py: the hip joint centres (socket_centre, the acetabulum's centre), the iliac
  crests' tops (crest_top), and the S1 end plate (s1_plate) with its front end, the promontory, and its back end
  (s1_points);
- DeepFluoro's other pelvic points (Grupp et al. 2020, IJCARS 15:759-769, the release's fourteen landmarks), each a
  short construction on a hip-bone mask written here: the anterior superior iliac spines where the anterior pelvic
  plane rests on each ilium (anterior_plane), the pubic symphysis's superior and inferior ends on each pubis
  (symphysis), the obturator foramen's inferior and medial points (obturator), the greater sciatic notch's deepest
  point (sciatic_notch), and the femoral head's centre read again as the centre of the femur's own ball
  (ball_centre).

    python tools/annotator_landmarks.py points --ts <TotalSegmentator folder> [--femur <folder>] --out points.json
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
OBTURATOR_TILTS_DEG = tuple(range(-40, 41, 10))
OBTURATOR_ABOVE_MM = 10.0              # the foramen is read on the hip bone below this height over the hip centre
OBTURATOR_AREA_MM2 = (150.0, 4000.0)   # a hole in the silhouette of this area can be the foramen
OBTURATOR_LATERAL_MM = 10.0            # and its middle lies no further than this lateral to the hip centre
RIM_MM = 2.5                           # a 2-D point's bone is the voxels projecting within this of it
NOTCH_BEHIND_MM = 10.0                 # the sciatic notch's concavity lies at least this far behind the hip centre
BALL_MM = (18.0, 32.0)                 # the femoral head's radius lies in this range, as the engine's socket's does
BALL_REACH_MM = 100.0                  # the head lies within the femur's highest 100 mm
S1_BELOW_MM = 4.0                      # the S1 plate's midline layer reaches this far below its plane
S1_GAP_MM = 2.0                        # a gap wider than this along the midline ends the plate (the sacral canal behind)
PLATE_BEYOND_LAYERS = 0.5              # plates.py's BEYOND_LAYERS
PLATE_FRONT_SHARE = 0.5                # plates.py's FRONT_SHARE
PLATE_MIN_POINTS = 20                  # plates.py's MIN_POINTS

# Each construction in plain words, and the QA loop's landmark it stands for (tools/qaloop_gates.py LANDMARKS), if
# any. A vertebra's names are "<level>.<construction>", the pelvis's "<construction>.<side>" or "<construction>".
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
                           "other pubis beyond the joint's gap, its end along the joint's long axis (symphysis)", None),
    "symphysis_inferior": ("the pubic symphysis's lower end on this pubis (symphysis)", None),
    "obturator_inferior": ("the obturator foramen's lowest point: the foramen as the largest hole in the silhouette of "
                           "the hip bone below the hip centre over views within 40 degrees of the anterior pelvic "
                           "plane's normal, its edge's lowest point, and the bone there (obturator)", None),
    "obturator_medial": ("the obturator foramen's point nearest the midline, in the same view (obturator)", None),
    "sciatic_notch": ("the greater sciatic notch's deepest point: the hip bone's outline seen along the hip axis, the "
                      "point of its posterior concavity furthest inside the convex hull, and the bone there "
                      "(sciatic_notch)", None),
}
# DeepFluoro's fourteen (Grupp 2020): each person-placed point and the constructions it is set against.
PERSON = {"FH": ("hip_centre", "femoral_head"), "ASIS": ("asis",), "GSN": ("sciatic_notch",),
          "IOF": ("obturator_inferior",), "MOF": ("obturator_medial",), "SPS": ("symphysis_superior",),
          "IPS": ("symphysis_inferior",)}
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


def read_totalseg(folder, femur_folder=None):
    """TotalSegmentator's per-structure masks: the vertebrae and the sacrum into one volume in the ENHANCE.PET ids, the
    hip bones and the femurs by TotalSegmentator's own sides."""
    G = engine()["G"]
    folder = Path(folder)
    vol, affine, names, notes = None, None, {}, {}
    masks = {}
    for stem in list(TS_SPINE) + ["sacrum", "hip_left", "hip_right"]:
        path = folder / f"{stem}.nii.gz"
        if path.is_file():
            masks[stem] = read_mask(path)
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
    if "sacrum" in masks:
        vol[masks["sacrum"][0] & (vol == 0)] = SACRUM_ID
        names[SACRUM_ID] = "sacrum"
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


def symphysis(right, left, frame):
    """Each pubis's face at the symphysis, and its two ends: the bone of each hip below the hip axis and within
    PUBIC_MIDLINE_MM of the midline that lies within SYMPHYSIS_MM of the other hip beyond the narrowest gap between
    them, which only the symphysis holds; the joint's long axis the faces' greatest spread, taken upward; each face's
    superior and inferior end the mean of its points within END_MM of its end along that axis."""
    from scipy.spatial import cKDTree
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
    if axis @ frame.ez < 0:
        axis = -axis
    out = {"gap_mm": gap, "axis_from_long_deg": angle_deg(axis, frame.ez)}
    for side, pts in face.items():
        out[f"superior_{side}"] = extreme(pts, axis, END_MM)
        out[f"inferior_{side}"] = extreme(pts, -axis, END_MM)
    return out


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


def obturator(points, frame, hip_centre, side, normal=None):
    """The obturator foramen's lowest point and its point nearest the midline. The foramen is the one large hole the
    hip bone's silhouette shows below the acetabulum, as on an anteroposterior film: over views tilted up to 40
    degrees, in steps of 10, from the anterior pelvic plane's normal (the frame's anterior where it is not given), the
    largest enclosed hole of the bone below OBTURATOR_ABOVE_MM over the hip centre whose middle lies below the hip
    centre and no more than OBTURATOR_LATERAL_MM lateral to it; the view showing it largest looks along the foramen.
    In that view the hole's extreme pixels downward and toward the midline (the frame's axes projected), and the bone
    projecting within RIM_MM of each, its mean over the rim's thickness."""
    from scipy import ndimage
    G = engine()["G"]
    q = frame.local(points)
    sel = points[q[:, 2] < frame.local(hip_centre[None, :])[0, 2] + OBTURATOR_ABOVE_MM]
    if len(sel) < 100:
        return None
    base = frame
    if normal is not None:
        ahead = unit(normal - (normal @ frame.ex) * frame.ex)
        base = G.Frame(frame.origin, frame.ex, ahead, np.cross(frame.ex, ahead))
    sign = 1.0 if side == "right" else -1.0
    best = None
    for pitch in OBTURATOR_TILTS_DEG:
        for yaw in OBTURATOR_TILTS_DEG:
            w, u, v = view(base, pitch, yaw)
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
                best = (area, pitch, yaw, u, v, uv, origin + ij + 0.5)
    if best is None:
        return None
    area, pitch, yaw, u, v, uv, hole = best
    down = -unit(np.array([frame.ez @ u, frame.ez @ v]))
    medial = -sign * unit(np.array([frame.ex @ u, frame.ex @ v]))
    out = {"area_mm2": area, "pitch_deg": pitch, "yaw_deg": yaw}
    for name, d in (("inferior", down), ("medial", medial)):
        p = bone_at(sel, uv, extreme(hole, d, 0.5))
        if p is not None:
            out[name] = p
    return out


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


def lowest_lumbar(verts):
    for lv in ("L6", "L5", "L4"):
        if lv in verts:
            return lv
    return None


def pelvis_points(lab, verts):
    """The pelvis's named points (RAS world), what kept any from being placed, and the constructions' own readings
    (the plane's tilt, the joint's gap, the foramen's view) for the record."""
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
    low = lowest_lumbar(verts)
    if low is not None and len(lab.sacrum) >= 1000:
        s1 = attempt(kept, notes, "s1", lambda: s1_points(lab.sacrum, lab.grid, verts[low]))
        if s1 is not None:
            points["s1_centre"] = s1["centre"]
            for end in ("anterior", "posterior"):
                if end in s1:
                    points[f"s1_{end}"] = s1[end]
            if "depth_mm" in s1:
                extras["s1_depth_mm"] = s1["depth_mm"]
    else:
        notes["s1"] = "no lowest lumbar vertebra read, or no sacrum"
    if len(hips) < 2:
        notes["pelvis"] = "both acetabula are needed for the pelvis's frame"
        return points, notes, extras
    frame = pelvic_frame(hips["right"]["centre"], hips["left"]["centre"], lab.grid)
    bone = {s: lab.grid.world(idx.astype(float)) for s, idx in lab.hips.items()}
    app = attempt(kept, notes, "asis", lambda: anterior_plane(bone["right"], bone["left"], frame))
    normal = None
    if app is not None:
        normal = app["normal"]
        points["asis.right"], points["asis.left"] = app["right"], app["left"]
        extras.update(app_turns=app["turns"], app_settled=app["settled"], app_tilt_deg=app["tilt_deg"])
    sym = attempt(kept, notes, "symphysis", lambda: symphysis(bone["right"], bone["left"], frame))
    if sym is not None:
        for side in ("right", "left"):
            points[f"symphysis_superior.{side}"] = sym[f"superior_{side}"]
            points[f"symphysis_inferior.{side}"] = sym[f"inferior_{side}"]
        extras.update(symphysis_gap_mm=sym["gap_mm"], symphysis_axis_deg=sym["axis_from_long_deg"])
    for side in ("right", "left"):
        ob = attempt(kept, notes, f"obturator.{side}",
                     lambda: obturator(bone[side], frame, hips[side]["centre"], side, normal))
        if ob is not None:
            for end in ("inferior", "medial"):
                if end in ob:
                    points[f"obturator_{end}.{side}"] = ob[end]
            extras[f"obturator_view.{side}"] = {k: ob[k] for k in ("area_mm2", "pitch_deg", "yaw_deg")}
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


def construct(lab):
    """Every named point of a labelled CT, in LPS world millimetres, with its construction, its QA loop landmark and
    the notes of what was not placed; and the vertebrae read, for drawing."""
    verts, vnotes = read_vertebrae(lab)
    points, notes = {}, {f"{lv}": why for lv, why in vnotes.items()}
    for lv, v in verts.items():
        got, why = vertebra_points(v)
        points.update({f"{lv}.{k}": p for k, p in got.items()})
        notes.update({f"{lv}.{k}": w for k, w in why.items()})
    got, why, extras = pelvis_points(lab, verts)
    points.update(got)
    notes.update(why)
    notes.update({f"labels.{k}": w for k, w in lab.notes.items()})
    named = {}
    for name, p in points.items():
        c = construction_of(name)
        named[name] = {"lps": [round(float(x), 3) for x in to_lps(p)], "construction": c,
                       "qaloop": CONSTRUCTIONS[c][1]}
    return {"frame": "world millimetres, LPS (x to the patient's left, y posterior, z superior)", "source": lab.source,
            "levels": sorted(verts, key=engine()["LEVELS"].index), "points": named, "notes": notes,
            "extras": jsonable(extras)}


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
    """For the vertebral and sacral points both sources placed, the distance between the two."""
    a, b = [r["points"] for r in readings.values()]
    out = {}
    for name in sorted(set(a) & set(b)):
        if not (name.startswith("s1_") or name.split(".")[0] in engine()["LEVELS"]):
            continue
        out[name] = round(float(np.linalg.norm(np.array(a[name]["lps"]) - np.array(b[name]["lps"]))), 2)
    return out


def promontory_offsets(reading):
    """The promontory against L5's lower plate, the check the old sacral anchor failed (docs/research/qa-loop-external):
    the S1 plate's front end less L5's lower plate centre and less L5's anterior-inferior corner, along the line from
    L5's lower plate's back end to its front end (the plate's own anterior), in mm."""
    p = reading["points"]
    low = next((lv for lv in ("L6", "L5") if f"{lv}.anterior_inferior" in p and f"{lv}.posterior_inferior" in p), None)
    if low is None or "s1_anterior" not in p:
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
    rows, per_case, drawn = [], {}, []
    for case in cases:
        folder = Path(data) / case
        ts = read_totalseg(folder / "ts", folder / "ts_femur")
        authors = read_deepfluoro(folder / "vol_seg.nii.gz", reference=ts)
        readings = {"totalseg": construct(ts), "authors": construct(authors)}
        person = marks[case]["landmarks"]
        rows += person_rows(case, person, readings)
        per_case[case] = {"readings": readings, "frame_check_mm": frame_check(person, authors),
                          "vertebra_agreement_mm": vertebra_agreement(readings),
                          "promontory": {s: promontory_offsets(r) for s, r in readings.items()}}
        (out / f"{case}.json").write_text(json.dumps(per_case[case], indent=1))
        print(f"{case}: {len(readings['totalseg']['points'])} points on TotalSegmentator, "
              f"{len(readings['authors']['points'])} on the authors' labels", flush=True)
        if len(drawn) < pictures:
            drawn.append(panel(folder / "ct.nii.gz", case, person, readings))
    table = summary(rows, ["totalseg", "authors"])
    report = {"cases": cases, "held_out_never_read": list(HELD_OUT), "agree_mm": AGREE_MM, "rows": rows,
              "summary": table, "frame_check_mm": {c: v["frame_check_mm"] for c, v in per_case.items()},
              "vertebra_agreement_mm": {c: v["vertebra_agreement_mm"] for c, v in per_case.items()},
              "promontory": {c: v["promontory"] for c, v in per_case.items()},
              "extras": {c: {s: r["extras"] for s, r in v["readings"].items()} for c, v in per_case.items()},
              "notes": {c: {s: r["notes"] for s, r in v["readings"].items()} for c, v in per_case.items()}}
    (out / "check.json").write_text(json.dumps(report, indent=1))
    (out / "table.md").write_text(markdown(table))
    if drawn:
        save_panels(drawn, out / "constructions.png")
    print(markdown(table))
    return report


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
    constructions on TotalSegmentator's masks (red crosses) and on the authors' labels (blue diagonal crosses), and
    TotalSegmentator's vertebral points (orange dots)."""
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
    for name, q in readings["totalseg"]["points"].items():
        if name[:1] in "TL" and "." in name:
            u, v = at(q["lps"])
            d.ellipse([u - 1.5, v - 1.5, u + 1.5, v + 1.5], fill=COLOURS["spine"])
    for name, p in person.items():
        u, v = at(p)
        d.ellipse([u - 6, v - 6, u + 6, v + 6], outline=COLOURS["person"], width=2)
        d.text((u + 7, v - 5), name, fill=COLOURS["person"])
    wanted = {"s1_anterior", "s1_centre", "s1_posterior"}
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
        lab = read_totalseg(a.ts, a.femur or a.ts) if a.ts else read_label_file(a.labels, a.scheme)
        Path(a.out).write_text(json.dumps(construct(lab), indent=1))
    elif a.cmd == "persons":
        persons(a.h5, a.out, a.cases.split(","))
    else:
        check(a.data, a.persons, a.out, a.cases.split(","))


if __name__ == "__main__":
    main()
