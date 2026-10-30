"""A CT's chords from its intensities alone, with no label volume: the mask-free mode.

    python -m scanimport ingest-raw-ct --volume ct.nii.gz --study s0001 --source enhance --out imports/raw

The owner's ask of 27 October 2026, 13:45 UTC: "permit importing just the raw volume (either
nifti or dicom) and calculating the measurements from just the intensities ... identify the bone
by HU thresholding ... ALL YOUR CODE FOR THIS METHOD IS BASED ON PRIOR ART AND IS ENTIRELY
TRANSPARENT, REPRODUCIBLE, TESTED, ENCAPSULATED". The steps below are built from published
training-free rules, each named where it is used; where a step adapts a rule rather than
following it, or a constant has no source, the step or the constant's comment says so and why.
research_notes/Vertebra measures without masks/ct_intensity_methods.md holds the sources and
reports/Vertebra measures without masks.md the review. No trained model, no random number and no
iteration to convergence enters, so the same volume gives the same chords, bit for bit, on the
same machine with the same numpy, scipy and BLAS build (tests/test_intensity.py measures a volume
twice and compares). On another CPU or BLAS library the floating-point kernels of the coordinate
transforms (the matrix products and the affine's inverse) may round the last bits differently,
and such a difference can, rarely, move a voxel across a threshold and so a chord.

THE STEPS.
1. The body is what is denser than half-way from air to water, -500 HU (air near -1000 HU, water
   0; Westerhoff et al. US 10,706,538 B2 separate body from air at -1000 HU, and the half-way
   point is this module's, the half-maximum rule below applied to that step, as the research
   note infers in its section 1).
2. The canal is a hole in the bone. Radnostics (Blumfield and Blumfield US 8,891,848 B2) marks a
   pixel as canal when more than half the voxels along z in its search box, seeded from the
   spinous-process tips, lie at -50 to 50 HU, and accepts a flood-filled region only after size
   and shape tests; Yao et al. 2006 extract the canal by "a hybrid of watershed and directed
   graph search", which the research note knows from the abstract alone, with its cost and
   structure not read. This module takes Radnostics' vote, made per hole rather than per pixel,
   and leaves out the seeding from the spinous tips and the shape tests. In every axial slice
   the holes of the bone mask (at or above 200 HU, the lowest level Radnostics' disc weight
   counts, which the research note reads as dense bone's floor in its section 1) that are inside
   the body, no smaller than G.CANAL_AREA_MM2's 12 mm2 and no larger than a canal
   (CANAL_MAX_MM2), and with more than half of their own voxels at -50 to 50 HU are candidates.
   Of two candidates one behind the other, the posterior one's centre within the anterior one's
   left-right span, only the posterior is kept, so that the fatty marrow of a body in front of
   the canal is not taken for it: this rule is this module's own, standing in for the seeding
   from the spinous tips and the shape tests that are left out, and no source read describes it.
   The canal is then the longest chain of candidates from slice to slice, each step moving less
   than the canal can between slices (MAX_JUMP_MM, MAX_SLOPE), found by a longest-path search
   over the slices. The chain and its three limits are this module's design: Yao 2006 is cited
   only for extracting the canal by a graph search, not for this one. Where the arch is open
   between two vertebrae the chain skips slices, up to MAX_GAP_MM, and the centreline is
   interpolated across the gap. A
   chain whose holes have a median area above the largest canal of Panjabi's means
   (CANAL_LARGEST_MM2) is reported as a problem.
3. The column's axis is the canal's centreline, resampled every millimetre along its length and
   smoothed over SMOOTH_MM; at each point the cross-section perpendicular to it is sampled in
   front of the canal, 25 mm to either side and 70 mm forward. Profiles taken along a curved
   reformation that follows the cord are Yao et al. 2006's (ISBI 2006, abstract: "curved sagittal
   and coronal reformations along the cord are analysed through aggregated intensity profiles");
   Radnostics' own profile follows a rectangular parametric curve along the expected body
   centres. Taking the axis from the canal's centreline instead is the research note's inference
   (its sections 3 and 4), not a published step; Vrtovec's thesis (University of Ljubljana, 2007)
   fits the spine curve as a polynomial by optimisation, and his paper on curved planar
   reformation of the spine was not read. The smoothing and the section's size are this
   module's. Each section is weighed as Radnostics weighs it: the number of samples of 200 to 400 HU
   plus four times the number at 400 HU or above. The research note flags the patent's text as
   garbled at this equation, to be checked against its drawings; it is used as read.
4. The discs are the weight's dips, after Radnostics' rule that a disc is "a depression between
   two spikes", with its moving maximum and minimum over a 40 mm window ("the height of a
   vertebra plus adjacent discs"). The weight is first averaged over 3 mm (this module's choice,
   so one noisy section makes no dip of its own). A dip is a local minimum, the middle of a run
   of samples equal to the least within 5 mm. Every height is taken above the moving minimum, the
   least weight in the 40 mm window about the dip. The highest weight within 20 mm on each side
   of the dip must be a spike, at least a third as high as the moving maximum (Radnostics' spike
   is above about 33 per cent of the moving maximum itself; taking both above the moving minimum
   is this module's adaptation), and the dip must be a depression, no higher than half the lower
   of those two spikes (DEPTH_SHARE, this module's choice: Radnostics' depression lies within
   about 5 of the moving minimum in its own weight units, which depend on how densely it samples
   a section). Measured from the moving minimum, neither test moves when a weight is added to
   every section, such as a contrast-filled aorta inside the section, and a ripple on a body's
   plateau within 20 mm of a disc is no dip, since the disc sets the floor. A shallow dip with no
   deeper one within 20 mm, as a sacral segment's rudimentary disc or a ripple along a fused
   block can be, is its own moving minimum and would pass both, so its rise must also be at least
   half the column's typical rise from a disc to a body, the median over the weight of the moving
   maximum less the moving minimum (RISE_SHARE, this module's choice; a difference of weights, so
   a weight every section shares does not move it either). Where most of the weight is sacrum or
   fused bone the typical rise is that of their ripples, and the guard does not hold. Radnostics'
   gap analysis, which looks again for a disc in a gap over 150 per cent of the local average gap
   and repeats until no disc is added, is not implemented. Two dips closer than MIN_DISC_GAP_MM
   keep the deeper; Radnostics drops the wider of two discs closer than about 40 per cent of its
   window, and the width of a dip is not defined in the text read. The minimum gap is this
   module's, shorter than the shortest cervical body (Panjabi MM et al. Spine 1991;16(8):861-869,
   Table 2: VBHp 10.9 to 12.8 mm at C3 to C7), so cervical discs are kept.
5. A vertebra is the bone between two consecutive discs: every voxel within SPINE_RADIUS_MM of
   the centreline whose nearest centreline point lies between the two discs' points. The body at
   either end of the found discs is bounded by one disc only (cut by the field, or the C1-C2
   complex, or the sacrum) and is kept unmeasured. A vertebra whose region holds metal (at or
   above METAL_HU) is not measured either, and says so.
6. The edge of each vertebra is placed half way between two levels (HALF), the 50 per cent
   relative threshold Treece, Gee and Poole compare against (Cambridge CUED/F-INFENG/TR634, 2009);
   Hangartner (J Musculoskelet Neuronal Interact 7(1), 2007, PMID 17396001) found 49 per cent of
   the difference between the adjacent tissues accurate for geometry on the one pQCT scanner he
   tested, and 0.5 rather than 0.49 is this module's choice. The two levels are read from the
   vertebra itself, by this module's own rules: the soft tissue just outside its 200 HU mask (the
   median of the voxels 2 to 3 voxels out that are below 200 HU and above SHELL_FLOOR_HU) and its
   cortical rim (the 90th percentile of the mask's outermost layer, the rim's blurred peak). The
   threshold is half way between them, and never below 130 HU, the single threshold Westerhoff
   applies to bone and vessels together: the floor keeps soft tissue out, not a contrast-filled
   vessel (WHAT IT CANNOT DO). Taking the blurred peak as the upper level, rather than the
   cortex's own density, makes this the full width at half maximum form (Stradview's "Use local
   peak as density"), which TR634 found less accurate in cortical thickness than a simple
   threshold (0.90 +/- 0.92 mm against 0.25 +/- 0.69 mm on 16 femurs); it is kept because a
   relative rule needs no fixed HU, and step 9 then corrects it. The volume is interpolated
   linearly onto a finer grid before the
   threshold is applied, so the edge lies where the interpolated intensity crosses the threshold,
   as a marching-cubes iso-surface does, not on the scan's voxel lattice. The fine grid is no
   coarser than half a millimetre along an axis whose voxels are 2 mm or shorter, and holds at
   most MAX_SUPERSAMPLE sub-voxels per voxel beyond that, so it is 0.75 mm across 3 mm slices and
   1.25 mm across 5 mm slices.
7. Inside the cortical rim the trabecular bone of an osteoporotic body can be below any fixed
   threshold (Pickhardt et al. 2013: an L1 attenuation of 160 HU or less was 90 per cent
   sensitive for osteoporosis, as a news summary of the paper reports it), so holes inside the
   rim are filled slice by slice, all but the canal's (the holes the centreline passes through),
   the flood fill inside a closed rim the research note recommends.
8. The pseudo-mask then goes through the same chords as a whole-vertebra label
   (geometry.measure_whole): the vertebra's own frame, the canal as a hole, the body in front of
   it. The two record-only chords (the transverse span and the spinous length) are not taken, as
   the plane between two discs cuts the arches and facets of the neighbours.
9. The half-maximum edge lies outward of a cortex thinner than the blur (below), so each chord's
   ends are then moved to the surface Treece's blurred-step model places (edges.py; cortical
   bone mapping, Treece et al. Med Image Anal 2010, PMID 20163980, and its report TR634):
   profiles are cast in the vertebra's own frame across its walls at five heights, through its
   end-plates at nine points and into the canal's walls at five levels, the model is fitted to
   each kind of surface with one blur, and the median shift moves the chords that end on it
   (CHORD_SURFACES). A surface
   whose best blur keeps fewer than five profiles or fewer than a majority of them, or whose
   shift is past 2 mm, leaves its chords at the half-maximum length, and the chord's method says
   which it is. --half-maximum-only skips it.

WHAT IT CANNOT DO, stated so nobody believes more than it gives.
- Bodies are not named: every body is "?", the column is not countable, and its annotation is
  none, so alone it is tier 4 whatever the source; in a pair with an X-ray of the same person its
  tier comes from the X-ray, 2, or 1 when the X-ray carries a person's annotation (tiers.py).
  bordercall names it from the chords.
- The half-maximum rule is exact for a structure thicker than the scanner's blur. Under the
  blurred-step model (edges.py), with the threshold half way from the soft tissue to the blurred
  peak and soft tissue of 40 HU outside a cortex of 1,200 HU, the half-maximum edge lies outward
  of the surface by up to about three quarters of the blur's SD over trabecular bone of 230 HU
  (where the cortex is about half the SD thick), by up to about nine tenths of it over an
  osteoporotic core of 100 HU, and still by about a quarter of the SD over either where the
  cortex is one full width at half maximum thick; an isolated plate much thinner than that width
  is out by half the difference between the width and its thickness, up to about 1.1 SD
  (tests/test_intensity.py works these out; the shares change with the three levels). TR634 found the 50 per cent
  threshold 0.90 +/- 0.92 mm long in cortical thickness on 16 cadaveric femurs. So under clinical
  blur widths and depths may run up to about 2 mm long (the table in README.md). Step 9 corrects
  most of this where the cortex is thin and dense (the tests hold every chord of a 0.5 mm cortex
  of 1,500 HU at 1 mm blur within 0.5 mm) and moves the ends inward too far where the cortex is
  less dense than the fit assumes (edges.py, HOW IT IS FITTED; the table in README.md).
- Across slices thicker than THICK_VOXEL_MM the heights are not to be believed to better than a
  slice: on the phantom with 3 mm slices the posterior height came out short by the half-maximum
  edge and shorter with the fit (the 3 mm row of the table in README.md). Such a volume says so
  in its problems.
- Where a rib head touches the body at clinical resolution it joins the body, so thoracic widths
  may include it, and a contrast vessel touching the body above the threshold joins it too.
- Metal within a vertebra's region (step 5) leaves that vertebra unmeasured, and metal within
  SPINE_RADIUS_MM of the centreline is a problem of the study; metal farther away, such as teeth
  above a cervical scan's measured bodies, is neither. Streaks from metal that reach a
  neighbouring vertebra's region are not detected.
- No training-free CT chord measurement has been validated in millimetres against manual or
  caliper measurement (research note, section 6); this one is tested on synthetic phantoms with
  known chords (tests/test_intensity.py), and its agreement with labels on real scans is the
  question `python -m scanimport compare` answers once real volumes are imported beside their
  labels.

numpy and scipy do every step: thresholds, connected components, hole filling and linear
interpolation are integer and graph operations that scipy.ndimage runs in compiled code, and
PyTensor has no operation for connected components or flood fill, so writing them in it would be
slower and no more exact.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import MEASURES, SEVEN
from . import edges as E
from . import geometry as G
from .column import Body, Column, facts_from_levels
from .readers import Volume

AIR_BODY_HU = -500.0                  # half way from air (-1000 HU) to water (0): the body's outline (step 1)
BONE_HU = 200.0                       # the lowest level Radnostics' disc weight counts (200 to 400 HU once)
BONE_FLOOR_HU = 130.0                 # Westerhoff's single threshold for bone and vessels: no edge threshold below it
DENSE_HU = 400.0                      # Radnostics' disc weight: 4 x the count above this
CANAL_HU = (-50.0, 50.0)              # Radnostics' canal contents
CANAL_SHARE = 0.5                     # Radnostics' "more than 50 percent", here of a hole's own voxels in one slice
# The largest canal of Panjabi's means, as an ellipse of its width and depth: L5, pi/4 x 27.1 x
# 19.7 mm (archive/bordercall/reference/panjabi_full_spine.csv). A chain of holes whose median is
# larger is said to be a problem (step 2).
CANAL_LARGEST_MM2 = 419.0
# This module's choice: the largest canal cut by an axial slice at up to 45 degrees (x 1.41, 593
# mm2), rounded up, so a hole larger than any canal is no candidate. It keeps out the marrow of a
# lumbar body (L1's end-plate as an ellipse, 41.2 x 34.1 mm, 1,103 mm2), not a cervical or
# thoracic one, which the posterior rule of step 2 sets apart.
CANAL_MAX_MM2 = 600.0
# The research note's inference (section 7: mask voxels "above about 2500 to 3000 HU"), which no
# source read tested; it is above any bone.
METAL_HU = 2500.0
# This module's choices for the canal's chain (step 2). A step between consecutive candidates may
# move at least MAX_JUMP_MM, less than the distance from the canal's centre to the centre of the
# smallest body in front of it (Panjabi's C3: half its canal depth, 8.1 mm, and half its
# end-plate depth, 7.5 mm), or up to MAX_SLOPE = tan(31 degrees) of the distance between the
# slices, a column leaning up to 31 degrees from the scanner's axis; the chain may skip up to
# MAX_GAP_MM of slices, room for the open arch between two vertebrae and less than a lumbar
# vertebra with its disc (Panjabi's VBHp 22.9 to 24.3 mm at L1 to L5, and the disc).
MAX_JUMP_MM = 10.0
MAX_SLOPE = 0.6
MAX_GAP_MM = 30.0
# This module's choice: the centreline is smoothed over less than the shortest cervical body
# (Panjabi's VBHp 10.9 mm at C6), so a level's own curve is kept.
SMOOTH_MM = 9.0
# This module's choice: 25 mm to either side covers the widest body's half-width (Panjabi's widest
# end-plate, L4's lower, 49.5 mm wide), and 70 mm forward from the canal's centre passes the front of the
# deepest body (half of L5's canal depth, 9.9 mm, and L4's end-plate depth, 35.5 mm: 45 mm), with
# room for a body tilted against the section.
SECTION_HALF_WIDTH_MM, SECTION_DEPTH_MM = 25.0, 70.0
WINDOW_MM = 40.0                      # Radnostics' window: "the height of a vertebra plus adjacent discs"
LOCAL_MIN_MM = 5.0                    # this module's choice: a dip is the least within 5 mm either side
DEPTH_SHARE = 0.5                     # this module's depression: within this share of the rise from the floor (step 4)
SPIKE_SHARE = 1.0 / 3.0               # Radnostics' spike: above about 33 per cent of the moving maximum
# This module's choice: a dip's rise must be at least half the column's typical rise from a disc
# to a body (step 4), the share the depth test uses; a disc of every phantom in tests/ rises 0.85
# to 1 of it, a lone ripple on a plateau far less.
RISE_SHARE = 0.5
SMOOTH_WEIGHT_MM = 3                  # this module's choice: a running mean, so one noisy section makes no dip
MIN_DISC_GAP_MM = 10.0                # this module's choice: shorter than the shortest cervical body (step 4)
SPINE_RADIUS_MM = 60.0                # this module's choice: past the front of the deepest body (45 mm, as above)
SHELL_VOXELS = (1, 3)                 # this module's choice: soft tissue 2 to 3 voxels out, past the edge's blur
SHELL_FLOOR_HU = -200.0               # this module's choice: air (lung, bowel gas) is not the soft tissue next to bone
RIM_PERCENTILE = 90.0                 # this module's choice: near the rim's blurred peak, not its one noisiest voxel
# The half-maximum: TR634's 50 per cent variant, which with the rim's blurred peak (RIM_PERCENTILE)
# as the upper level is the FWHM form; Hangartner's 49 per cent held on his one scanner, and 0.5
# rather than 0.49 is this module's choice (step 6).
HALF = 0.5
FINE_MM = 0.5                         # this module's choice: the fine grid's step at most, for voxels up to 2 mm
# This module's choice: at most 4 sub-voxels per voxel along an axis, since linear interpolation
# adds no detail across a thick slice and the fine grid grows with the factor (0.75 mm across 3
# mm slices).
MAX_SUPERSAMPLE = 4
# This module's choice: a hole within this distance of the centreline is the canal's, kept open
# by step 7; less than half the narrowest canal (Panjabi's T4, 17.0 mm wide).
CANAL_KEEP_MM = 3.0
MIN_PIECE_MM3 = 200.0                 # this module's choice: a piece under about a 6 mm cube is not the vertebra
NOT_TAKEN = ("tp_span", "spinous_length")
# This module's choices for the fit's rays: how many heights (and canal slabs) they are cast at,
# the walls' heights spread over the middle half of the body, away from the end-plates' rims; how
# far either side of the body's middle they run as a share of its width or depth; and how far
# past the half-way point a ray may look for the surface.
WALL_LEVELS = 5
RAY_SPREAD = 0.15
RAY_BEYOND_MM = 3.0
THICK_VOXEL_MM = 2.0                  # this module's choice: longer voxels make the heights uncertain by a voxel


@dataclass
class Centreline:
    """The canal's centreline, every millimetre: points (N, 3) in world millimetres, unit tangents
    pointing up, and the slices it was found in."""
    points: np.ndarray
    tangents: np.ndarray
    found_slices: int
    skipped_slices: int


@dataclass
class Found:
    """What the mask-free mode found, for the record: the centreline, the disc positions along it
    (millimetres from its lower end), the weight it found them in, and its problems."""
    centreline: Optional[Centreline]
    discs: List[float] = field(default_factory=list)
    weight: Optional[np.ndarray] = None
    problems: List[str] = field(default_factory=list)


# ---- the volume as axial slices ----------------------------------------------------------------

def axial(vol: Volume) -> Tuple[np.ndarray, np.ndarray]:
    """The volume with the array axis closest to the world's superior direction last, and its
    affine permuted to match, so a slice hu[:, :, k] lies across the column."""
    a = np.asarray(vol.affine, float)
    cos_sup = np.abs(a[2, :3]) / np.linalg.norm(a[:3, :3], axis=0)
    k = int(np.argmax(cos_sup))
    order = [i for i in range(3) if i != k] + [k]
    hu = np.transpose(vol.hu, order)
    perm = np.eye(4)
    perm[:3, :3] = np.eye(3)[:, order]
    return np.ascontiguousarray(hu), a @ perm


def body_outline(hu: np.ndarray) -> np.ndarray:
    """The patient, slice by slice: denser than AIR_BODY_HU, holes (lungs, bowel gas) filled."""
    out = np.zeros(hu.shape, bool)
    for k in range(hu.shape[2]):
        out[:, :, k] = ndimage.binary_fill_holes(hu[:, :, k] > AIR_BODY_HU)
    return out


# ---- the canal ----------------------------------------------------------------------------------

@dataclass
class Candidate:
    k: int
    centre: np.ndarray                # world millimetres
    area: float


def canal_candidates(hu: np.ndarray, affine: np.ndarray, body: np.ndarray) -> List[List[Candidate]]:
    """Per slice, the holes of the 200 HU bone mask that could be the canal (step 2): inside the
    body, of a canal's area, mostly of canal density, and with no such hole behind them."""
    pixel_area = float(np.linalg.norm(affine[:3, 0]) * np.linalg.norm(affine[:3, 1]))
    out: List[List[Candidate]] = []
    for k in range(hu.shape[2]):
        out.append(holes_in_slice(hu[:, :, k], affine, body[:, :, k], k, pixel_area))
    return out


def holes_in_slice(sl: np.ndarray, affine: np.ndarray, body: np.ndarray, k: int, pixel_area: float) -> List[Candidate]:
    """One slice's canal candidates, each with its left-right span in world millimetres for the
    posterior rule."""
    bone = sl >= BONE_HU
    hole = ndimage.binary_fill_holes(bone) & ~bone & body
    lab, n = ndimage.label(hole)
    if not n:
        return []
    idx = np.arange(1, n + 1)
    counts = ndimage.sum_labels(np.ones_like(sl), lab, idx)
    canal_like = ndimage.sum_labels((sl >= CANAL_HU[0]) & (sl <= CANAL_HU[1]), lab, idx)
    cents = ndimage.center_of_mass(np.ones_like(sl), lab, idx)
    ii, jj = np.meshgrid(np.arange(sl.shape[0]), np.arange(sl.shape[1]), indexing="ij")
    world_x = affine[0, 0] * ii + affine[0, 1] * jj + affine[0, 2] * k + affine[0, 3]
    x_lo, x_hi = ndimage.minimum(world_x, lab, idx), ndimage.maximum(world_x, lab, idx)
    found, spans = [], []
    for n_vox, n_canal, ij, lo, hi in zip(counts, canal_like, cents, x_lo, x_hi):
        area = float(n_vox) * pixel_area
        if not (G.CANAL_AREA_MM2[0] <= area <= CANAL_MAX_MM2) or n_canal <= CANAL_SHARE * n_vox:
            continue
        world = affine[:3, :3] @ np.array([ij[0], ij[1], k], float) + affine[:3, 3]
        found.append(Candidate(k, world, area))
        spans.append((float(lo), float(hi)))
    return [c for i, c in enumerate(found) if not behind_another(i, found, spans)]


def behind_another(i: int, found: List[Candidate], spans: List[Tuple[float, float]]) -> bool:
    """Whether another candidate of the slice lies behind candidate i, its centre posterior (lower
    world y, RAS) and within i's left-right span: then i is in front of the canal, as a fatty
    body's marrow is, and the posterior one is the canal (step 2)."""
    lo, hi = spans[i]
    me = found[i].centre
    return any(j != i and c.centre[1] < me[1] and lo <= c.centre[0] <= hi for j, c in enumerate(found))


def longest_chain(cands: List[List[Candidate]], step_mm: float) -> List[Candidate]:
    """The longest sequence of candidates in increasing slices, each within reach of the last: a
    longest path in the directed graph whose edges join a candidate to one in a later slice no
    more than MAX_GAP_MM away and no farther across than the canal can move. Ties go to the
    nearer predecessor, then the lower slice, so the answer is fixed."""
    flat = [c for row in cands for c in row]
    if not flat:
        return []
    gap = max(1, int(math.floor(MAX_GAP_MM / step_mm)) + 1)
    best_len, best_prev = [1] * len(flat), [-1] * len(flat)
    start = {}
    pos = 0
    for k, row in enumerate(cands):
        start[k] = pos
        pos += len(row)
    for i, c in enumerate(flat):
        best = (1, math.inf, -1)
        for k0 in range(max(0, c.k - gap), c.k):
            for j in range(start[k0], start[k0] + len(cands[k0])):
                p = flat[j]
                dz = (c.k - p.k) * step_mm
                d = float(np.linalg.norm((c.centre - p.centre)[:2]))
                if d > max(MAX_JUMP_MM, MAX_SLOPE * dz):
                    continue
                cand = (best_len[j] + 1, d, j)
                if cand[0] > best[0] or (cand[0] == best[0] and cand[1] < best[1]):
                    best = cand
        best_len[i], best_prev[i] = best[0], best[2]
    end = int(np.argmax(best_len))
    chain = []
    while end >= 0:
        chain.append(flat[end])
        end = best_prev[end]
    return chain[::-1]


def resample(points: np.ndarray, every_mm: float = 1.0) -> np.ndarray:
    """A polyline resampled every `every_mm` along its length."""
    seg = np.linalg.norm(np.diff(points, axis=0), axis=1)
    s = np.r_[0.0, np.cumsum(seg)]
    t = np.arange(0.0, s[-1] + 1e-9, every_mm)
    return np.stack([np.interp(t, s, points[:, i]) for i in range(3)], axis=1)


def centreline_of(chain: List[Candidate]) -> Optional[Centreline]:
    """The chain's centreline, or None where it runs through fewer than three slices or less than
    a millimetre, too short to give a direction."""
    if len(chain) < 3:
        return None
    pts = resample(np.array([c.centre for c in chain]))
    if len(pts) < 2:
        return None
    w = max(1, int(round(SMOOTH_MM)))
    if len(pts) > w:
        pts = ndimage.uniform_filter1d(pts, size=w, axis=0, mode="nearest")
    tan = np.gradient(pts, axis=0)
    tan = ndimage.uniform_filter1d(tan, size=w, axis=0, mode="nearest")
    tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    if np.mean(tan[:, 2]) < 0:
        pts, tan = pts[::-1], -tan[::-1]
    covered = chain[-1].k - chain[0].k + 1
    return Centreline(points=pts, tangents=tan, found_slices=len(chain), skipped_slices=covered - len(chain))


# ---- the discs ----------------------------------------------------------------------------------

def section_axes(tangent: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Across the column: (to the patient's left, anterior), both perpendicular to the tangent;
    anterior is the world's +y in RAS, as geometry.VoxelGrid.anterior says."""
    a = np.array([0.0, 1.0, 0.0])
    a = a - (a @ tangent) * tangent
    a /= np.linalg.norm(a)
    return np.cross(tangent, a), a


def disc_weight(hu: np.ndarray, affine: np.ndarray, line: Centreline) -> np.ndarray:
    """Radnostics' weight of each cross-section in front of the canal: samples every millimetre
    of 200 to 400 HU, plus four times those of 400 HU or more."""
    inv = np.linalg.inv(affine)
    u = np.arange(-SECTION_HALF_WIDTH_MM, SECTION_HALF_WIDTH_MM + 1e-9, 1.0)
    v = np.arange(0.0, SECTION_DEPTH_MM + 1e-9, 1.0)
    uu, vv = np.meshgrid(u, v, indexing="ij")
    out = np.zeros(len(line.points))
    for i, (p, t) in enumerate(zip(line.points, line.tangents)):
        left, ant = section_axes(t)
        world = p + uu[..., None] * left + vv[..., None] * ant
        ijk = world.reshape(-1, 3) @ inv[:3, :3].T + inv[:3, 3]
        val = ndimage.map_coordinates(hu, ijk.T, order=1, mode="constant", cval=-1000.0)
        out[i] = float(((val >= BONE_HU) & (val < DENSE_HU)).sum() + 4 * (val >= DENSE_HU).sum())
    return out


def moving_max(w: np.ndarray, half: int) -> np.ndarray:
    return ndimage.maximum_filter1d(w, size=2 * half + 1, mode="nearest")


def find_discs(weight: np.ndarray) -> List[int]:
    """The disc dips of a weight sampled every millimetre (step 4 of the module's text)."""
    n = len(weight)
    if n < 2 * LOCAL_MIN_MM + 1:
        return []
    w = ndimage.uniform_filter1d(weight, size=SMOOTH_WEIGHT_MM, mode="nearest")
    half_local, half_win = int(LOCAL_MIN_MM), int(WINDOW_MM / 2)
    local_min = ndimage.minimum_filter1d(w, size=2 * half_local + 1, mode="nearest")
    lab, nr = ndimage.label(w <= local_min + 1e-9)
    # Radnostics' moving maximum and minimum, both over the one 40 mm window centred on a sample
    wide = moving_max(w, half_win)
    floor = ndimage.minimum_filter1d(w, size=2 * half_win + 1, mode="nearest")
    # the column's typical rise from a disc to a body, which a lone shallow dip falls far short of
    typical = float(np.median(wide - floor))
    picks = []
    for r in range(1, nr + 1):
        run = np.flatnonzero(lab == r)
        m = int(run[len(run) // 2])
        left = w[max(0, m - half_win):run[0]]
        right = w[run[-1] + 1:min(n, m + half_win + 1)]
        if not len(left) or not len(right):
            continue
        # every height is taken above the moving minimum, so a weight all sections share moves none
        base = float(floor[m])
        rise = min(float(left.max()), float(right.max())) - base
        depth = float(w[m]) - base
        if (rise <= 0.0 or rise < SPIKE_SHARE * (float(wide[m]) - base) or depth > DEPTH_SHARE * rise
                or rise < RISE_SHARE * typical):
            continue
        picks.append((depth / rise, m))
    kept: List[int] = []
    for _, m in sorted(picks):
        if all(abs(m - k) >= MIN_DISC_GAP_MM for k in kept):
            kept.append(m)
    return sorted(kept)


# ---- one vertebra -------------------------------------------------------------------------------

def supersample_of(spacing: np.ndarray) -> np.ndarray:
    return np.clip(np.ceil(spacing / FINE_MM - 1e-9), 1, MAX_SUPERSAMPLE).astype(int)


def edge_threshold(hu_box: np.ndarray, rough: np.ndarray, region: np.ndarray) -> Tuple[float, float, float]:
    """The half-maximum threshold of one vertebra, from its soft-tissue and rim levels (step 6)."""
    out1 = ndimage.binary_dilation(rough, iterations=SHELL_VOXELS[0])
    out3 = ndimage.binary_dilation(rough, iterations=SHELL_VOXELS[1])
    shell = out3 & ~out1 & region & (hu_box < BONE_HU) & (hu_box > SHELL_FLOOR_HU)
    rim = rough & ~ndimage.binary_erosion(rough)
    soft = float(np.median(hu_box[shell])) if shell.any() else 0.0
    peak = float(np.percentile(hu_box[rim], RIM_PERCENTILE)) if rim.any() else BONE_HU
    return max(soft + HALF * (peak - soft), BONE_FLOOR_HU), soft, peak


def fine_grid(affine: np.ndarray, lo: np.ndarray, shape: Tuple[int, ...], f: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """The coarse coordinates of the centres of a box's sub-voxels, f per voxel along each axis,
    and the affine of the fine grid."""
    axes = [lo[a] + (np.arange(shape[a] * f[a]) + 0.5) / f[a] - 0.5 for a in range(3)]
    fa = np.eye(4)
    fa[:3, :3] = affine[:3, :3] / f
    fa[:3, 3] = affine[:3, :3] @ np.array([axes[0][0], axes[1][0], axes[2][0]]) + affine[:3, 3]
    return axes, fa


def fill_rim(mask: np.ndarray, canal_seed: np.ndarray, axis: int) -> np.ndarray:
    """Holes inside the rim filled slice by slice across `axis`, all but those the canal's seed
    touches (step 7)."""
    out = mask.copy()
    for n in range(mask.shape[axis]):
        sl = [slice(None)] * 3
        sl[axis] = n
        m = mask[tuple(sl)]
        hole = ndimage.binary_fill_holes(m) & ~m
        if not hole.any():
            continue
        lab, _ = ndimage.label(hole)
        keep_open = np.unique(lab[canal_seed[tuple(sl)] & hole])
        fill = hole & ~np.isin(lab, keep_open[keep_open > 0])
        out[tuple(sl)] = m | fill
    return out


@dataclass
class Vertebra:
    """One vertebra's pseudo-mask on its fine grid, and how its edge was placed."""
    idx: np.ndarray
    grid: G.VoxelGrid
    touching: np.ndarray
    threshold: float
    soft: float
    peak: float
    tangent: np.ndarray


def vertebra_between(hu: np.ndarray, affine: np.ndarray, body: np.ndarray, line: Centreline,
                     tree: cKDTree, s0: int, s1: int) -> Tuple[Optional[Vertebra], str]:
    """The pseudo-mask of the bone between centreline samples s0 and s1 (steps 5 to 7), or None
    and why it is not measured."""
    little = "too little bone between the discs at %d and %d mm" % (s0, s1)
    reg = region_of(hu, affine, body, line, tree, s0, s1)
    if reg is None:
        return None, little
    hu_box = hu[reg.box]
    metal = metal_reason(hu_box, reg.region, s0, s1)
    if metal:
        return None, metal
    rough = reg.region & (hu_box >= BONE_HU)
    if rough.sum() * float(np.prod(reg.spacing)) < MIN_PIECE_MM3:
        return None, little
    t, soft, peak = edge_threshold(hu_box, rough, reg.region)
    fine = pseudo_mask(hu, affine, line, reg, rough, t, (s0 + s1) // 2)
    if fine is None:
        return None, little
    mask, axes, fa = fine
    idx = np.argwhere(mask)
    if len(idx) < G.MIN_BODY_VOXELS:
        return None, little
    coarse = np.stack([axes[a][idx[:, a]] for a in range(3)], axis=1)
    touching = ((coarse < 0.5) | (coarse > np.array(hu.shape) - 1.5)).any(1)
    tangent = line.tangents[s0:s1 + 1].mean(0)
    return Vertebra(idx=idx, grid=G.VoxelGrid(affine=fa, shape=mask.shape), touching=touching,
                    threshold=t, soft=soft, peak=peak, tangent=tangent / np.linalg.norm(tangent)), ""


@dataclass
class Region:
    """The box of voxels about one vertebra's stretch of centreline (its corner `lo` and its
    slices), and in it the vertebra's region (step 5) and the voxels near the canal (step 7)."""
    lo: np.ndarray
    box: Tuple[slice, ...]
    region: np.ndarray
    canal_near: np.ndarray
    spacing: np.ndarray


def region_of(hu: np.ndarray, affine: np.ndarray, body: np.ndarray, line: Centreline, tree: cKDTree,
              s0: int, s1: int) -> Optional[Region]:
    """Every body voxel within SPINE_RADIUS_MM of the centreline whose nearest centreline point lies
    between samples s0 and s1, in a box about them; None where the box is empty."""
    seg = line.points[s0:s1 + 1]
    inv = np.linalg.inv(affine)
    spacing = np.linalg.norm(affine[:3, :3], axis=0)
    reach = SPINE_RADIUS_MM / spacing
    ijk = seg @ inv[:3, :3].T + inv[:3, 3]
    lo = np.maximum(np.floor(ijk.min(0) - reach).astype(int), 0)
    hi = np.minimum(np.ceil(ijk.max(0) + reach).astype(int) + 1, np.array(hu.shape))
    if np.any(hi <= lo):
        return None
    box = tuple(slice(a, b) for a, b in zip(lo, hi))
    g = np.stack(np.meshgrid(*[np.arange(a, b) for a, b in zip(lo, hi)], indexing="ij"), -1).reshape(-1, 3)
    world = g @ affine[:3, :3].T + affine[:3, 3]
    dist, near = tree.query(world)
    shape = hu[box].shape
    region = ((near > s0) & (near < s1) & (dist <= SPINE_RADIUS_MM)).reshape(shape) & body[box]
    return Region(lo=lo, box=box, region=region, canal_near=(dist <= CANAL_KEEP_MM).reshape(shape), spacing=spacing)


def metal_reason(hu_box: np.ndarray, region: np.ndarray, s0: int, s1: int) -> str:
    """Why the vertebra is not measured when its region holds metal (step 5), or "" when it holds none."""
    metal = int(((hu_box >= METAL_HU) & region).sum())
    if not metal:
        return ""
    return ("metal: %d voxels at or above %.0f HU in the vertebra's region (within %.0f mm of the canal between the "
            "discs at %d and %d mm), so none of its chords is believed" % (metal, METAL_HU, SPINE_RADIUS_MM, s0, s1))


def on_fine_grid(coarse: np.ndarray, f: np.ndarray) -> np.ndarray:
    """A mask of the scan's voxels on the fine grid, each voxel repeated f times along each axis."""
    return np.repeat(np.repeat(np.repeat(coarse, f[0], 0), f[1], 1), f[2], 2)


def pseudo_mask(hu: np.ndarray, affine: np.ndarray, line: Centreline, reg: Region, rough: np.ndarray,
                threshold: float, middle: int) -> Optional[Tuple[np.ndarray, list, np.ndarray]]:
    """The vertebra on the fine grid (step 6): the interpolated intensities at or above the
    threshold within its region, the holes inside its rim filled (step 7) and pieces too small to
    be bone dropped; with the fine grid's axes and affine, or None where nothing is left."""
    # interpolate only round the bone, a margin of two voxels
    nz = np.argwhere(ndimage.binary_dilation(rough, iterations=2))
    blo, bhi = nz.min(0), nz.max(0) + 1
    sub = tuple(slice(a, b) for a, b in zip(blo, bhi))
    f = supersample_of(reg.spacing)
    axes, fa = fine_grid(affine, reg.lo + blo, tuple(bhi - blo), f)
    cc = np.meshgrid(*axes, indexing="ij")
    hu_fine = ndimage.map_coordinates(hu, [c.ravel() for c in cc], order=1, mode="nearest").reshape(cc[0].shape)
    mask = (hu_fine >= threshold) & on_fine_grid(reg.region[sub], f)
    axis = int(np.argmax(np.abs(fa[:3, :3].T @ line.tangents[middle]) / np.linalg.norm(fa[:3, :3], axis=0)))
    mask = fill_rim(mask, on_fine_grid(reg.canal_near[sub], f), axis)
    lab, n = ndimage.label(mask)
    if n == 0:
        return None
    sizes = np.bincount(lab.ravel())[1:] * float(np.prod(reg.spacing / f))
    return np.isin(lab, np.flatnonzero(sizes >= MIN_PIECE_MM3) + 1), axes, fa


# ---- the study ----------------------------------------------------------------------------------

def find(hu: np.ndarray, affine: np.ndarray, body: np.ndarray) -> Found:
    """The canal's centreline and the discs along it."""
    step = float(abs(affine[:3, 2] @ np.array([0.0, 0.0, 1.0])))
    cands = canal_candidates(hu, affine, body)
    chain = longest_chain(cands, step)
    line = centreline_of(chain)
    if line is None:
        return Found(None, problems=["no canal: no chain of bone-enclosed holes of canal density runs through three "
                                     "slices and a millimetre"])
    problems = []
    area = float(np.median([c.area for c in chain]))
    if area > CANAL_LARGEST_MM2:
        problems.append("the canal's holes have a median area of %.0f mm2, above the largest canal of Panjabi's means "
                        "(%.0f mm2 at L5): the chain may follow something other than the canal"
                        % (area, CANAL_LARGEST_MM2))
    weight = disc_weight(hu, affine, line)
    return Found(line, [float(d) for d in find_discs(weight)], weight, problems)


def metal_problem(hu: np.ndarray, affine: np.ndarray, line: Optional[Centreline]) -> Optional[str]:
    """The study's problem for metal: voxels at or above METAL_HU within SPINE_RADIUS_MM of the
    centreline, or anywhere when no centreline was found to tell; None when there are none."""
    ijk = np.argwhere(hu >= METAL_HU)
    if not len(ijk):
        return None
    if line is None:
        return ("%d voxels at or above %.0f HU (metal), and no canal was found to tell whether they are near the spine"
                % (len(ijk), METAL_HU))
    world = ijk @ affine[:3, :3].T + affine[:3, 3]
    dist, _ = cKDTree(line.points).query(world)
    near = int((dist <= SPINE_RADIUS_MM).sum())
    if not near:
        return None
    return ("%d voxels at or above %.0f HU (metal) within %.0f mm of the canal: a vertebra whose region holds any is "
            "not measured" % (near, METAL_HU, SPINE_RADIUS_MM))


def measure(vol: Volume, fit_edges: bool = True, fit_density: bool = False) -> Tuple[List[Body], Found]:
    """Every body between the found discs, top down, with its chords where they can be taken.
    fit_density runs the blurred-step fit with the cortical density fitted too (edges.fit_density),
    the trial edges.py describes and does not use; nothing but the bench asks for it."""
    hu, affine = axial(vol)
    body = body_outline(hu)
    found = find(hu, affine, body)
    found.problems = list(vol.problems) + found.problems
    longest = float(np.linalg.norm(affine[:3, :3], axis=0).max())
    if longest > THICK_VOXEL_MM:
        found.problems.append("voxels %.1f mm long on one axis: a chord across them, the height on axial slices, may be "
                              "out by up to a voxel (the phantom with 3 mm slices in "
                              "scanimport/tests/bench_mask_free.py read its posterior height short, the more so with "
                              "the blurred-step fit)" % longest)
    metal = metal_problem(hu, affine, found.centreline)
    if metal:
        found.problems.append(metal)
    if found.centreline is None:
        return [], found
    if len(found.discs) < 2:
        found.problems.append("%d disc found along the canal; a measured body needs a disc above and below"
                              % len(found.discs))
    line = found.centreline
    tree = cKDTree(line.points)
    discs = [int(d) for d in found.discs]
    bodies: List[Body] = []
    ends = Body(level="?", flags={"all": "bounded by one disc: cut by the field, the C1-C2 complex or the sacrum"})
    if discs:
        bodies.append(ends)
    for a, b in zip(discs, discs[1:]):
        bodies.append(measure_between(hu, affine, body, line, tree, a, b, fit_edges, fit_density))
    if discs:
        bodies.append(Body(level="?", flags=dict(ends.flags)))
    return bodies[::-1], found                # the centreline runs upward; the column is top down


def surface_rays(v: Vertebra, frame: G.Frame) -> Dict[str, List[Tuple[np.ndarray, np.ndarray, float]]]:
    """Rays for the blurred-step fit (edges.py), in the vertebra's own frame: across the walls from
    inside the body at mid-height, through the end-plates from the body's middle, and out from
    the canal's centre into its walls. Each ray is (origin, unit direction, reach), in world
    millimetres."""
    pts = v.grid.world(v.idx.astype(float))
    loc = frame.local(pts)
    fx, fy, fz = (v.grid.footprint(e) for e in (frame.ex, frame.ey, frame.ez))
    pixel = max(fx, fy)
    secs = G.sections(loc, fz, pixel, as_hole=True)
    canal = G.canal_chords(secs, pixel, (-np.inf, np.inf), fx, fy)
    if not canal:
        return {}
    body = loc[G.connected_front(v.idx, loc, canal["wall_anterior"], v.grid.shape)]
    if len(body) < G.MIN_BODY_VOXELS:
        return {}
    core = body[G.central(body[:, 0], body[:, 1])]
    x0, x1 = float(body[:, 0].min()), float(body[:, 0].max())
    y0, y1 = canal["wall_anterior"], float(body[:, 1].max())
    z0, z1 = float(core[:, 2].min()), float(core[:, 2].max())
    xc, yc, zc = 0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)
    w, d, h = x1 - x0, y1 - y0, z1 - z0
    world = lambda l: frame.origin + l[0] * frame.ex + l[1] * frame.ey + l[2] * frame.ez
    rays: Dict[str, List[Tuple[np.ndarray, np.ndarray, float]]] = {"walls": [], "plates": [], "canal": []}
    for z in np.linspace(z0 + 0.25 * h, z1 - 0.25 * h, WALL_LEVELS):
        for f in (-RAY_SPREAD, 0.0, RAY_SPREAD):
            for sign in (-1.0, 1.0):
                rays["walls"].append((world((xc, yc + f * d, z)), sign * frame.ex, 0.5 * w + RAY_BEYOND_MM))
            rays["walls"].append((world((xc + f * w, yc, z)), frame.ey, 0.5 * d + RAY_BEYOND_MM))
    for fxs in (-RAY_SPREAD, 0.0, RAY_SPREAD):
        for fys in (-RAY_SPREAD, 0.0, RAY_SPREAD):
            for sign in (-1.0, 1.0):
                rays["plates"].append((world((xc + fxs * w, yc + fys * d, zc)), sign * frame.ez, 0.5 * h + RAY_BEYOND_MM))
    found = sorted((s for s in secs if s.canal is not None), key=lambda s: abs(s.w - canal["w_mid"]))[:WALL_LEVELS]
    for s in found:
        c = s.canal
        centre = world((0.5 * (c[:, 0].min() + c[:, 0].max()), 0.5 * (c[:, 1].min() + c[:, 1].max()), s.w))
        for e, half in ((frame.ex, canal["canal_w"]), (frame.ey, canal["canal_ap"])):
            for sign in (-1.0, 1.0):
                rays["canal"].append((centre, sign * e, 0.5 * half + RAY_BEYOND_MM))
    return rays


def surface_fits(hu: np.ndarray, affine: np.ndarray, v: Vertebra, frame: G.Frame,
                 fit_density: bool = False) -> Dict[str, E.SurfaceFit]:
    """For the walls, the end-plates and the canal, the shift of the half-maximum edge outward of
    the blurred-step model's surface (edges.py), at the one cortical density or, for the trial
    edges.py describes, with the density fitted too."""
    fitter = E.fit_density if fit_density else E.fit
    out = {}
    for kind, rays in surface_rays(v, frame).items():
        prof = E.profiles_along(hu, affine, rays, v.threshold, from_inside=(kind != "canal"))
        out[kind] = fitter(prof, E.positions())
    return out


# which surfaces each chord ends on, and the sign that moves a chord when its surfaces move in
CHORD_SURFACES = {"endplate": (("walls", -1), ("walls", -1)), "endplate_lower": (("walls", -1), ("walls", -1)),
                  "endplate_depth": (("walls", -1), ("canal", -1)),
                  "endplate_lower_depth": (("walls", -1), ("canal", -1)),
                  "h_post": (("plates", -1), ("plates", -1)),
                  "canal_w": (("canal", 1), ("canal", 1)), "canal_ap": (("canal", 1), ("canal", 1))}


def corrected(values: Dict[str, float], fits: Dict[str, E.SurfaceFit]) -> Tuple[Dict[str, float], Dict[str, str]]:
    """Each chord with its two ends moved to the fitted surfaces; a chord one of whose surfaces has
    no believable fit is left at its half-maximum length and says why."""
    out, notes = dict(values), {}
    for m, ends in CHORD_SURFACES.items():
        if not np.isfinite(values.get(m, math.nan)):
            continue
        missing = [k for k, _ in ends if k not in fits or fits[k].reason]
        if missing:
            notes[m] = "half-maximum length: no blurred-step fit for the %s (%s)" % (
                missing[0], fits[missing[0]].reason if missing[0] in fits else "no rays")
            continue
        out[m] = values[m] + sum(sign * fits[k].shift for k, sign in ends)
    return out, notes


def surface_note(kind: str, sign: int, f: E.SurfaceFit, fit_density: bool) -> str:
    """How far one surface moved a chord's end, and the fit it came from."""
    density = ", cortex fitted at %.0f HU" % f.cortical if fit_density else ""
    return "%s %+.2f mm, blur SD %.2f mm%s, %d profiles" % (kind, -sign * f.shift, f.sigma, density, f.profiles)


def measure_between(hu: np.ndarray, affine: np.ndarray, body: np.ndarray, line: Centreline, tree: cKDTree,
                    a: int, b: int, fit_edges: bool = True, fit_density: bool = False) -> Body:
    out = Body(level="?")
    v, why = vertebra_between(hu, affine, body, line, tree, a, b)
    if v is None:
        out.flags = {"all": why}
        return out
    got = G.measure_whole(v.idx, v.grid, v.tangent, v.touching)
    out.values, out.flags = dict(got.values), dict(got.flags)
    for m in NOT_TAKEN:
        out.values[m] = math.nan
        out.flags[m] = "not taken without a mask: the plane between two discs cuts the neighbours' arches"
    edge = "half-maximum edge at %.0f HU (soft tissue %.0f, rim %.0f), between discs at %d and %d mm" % (
        v.threshold, v.soft, v.peak, a, b)
    out.methods = {m: "mask-free intensities, " + edge for m in MEASURES}
    if fit_edges and got.frame is not None:
        fits = surface_fits(hu, affine, v, got.frame, fit_density)
        out.values, notes = corrected(out.values, fits)
        for m, ends in CHORD_SURFACES.items():
            if m in notes:
                out.methods[m] += "; " + notes[m]
            elif np.isfinite(out.values.get(m, math.nan)):
                out.methods[m] += "; ends moved to the blurred-step surface (%s)" % ", ".join(
                    surface_note(k, sign, fits[k], fit_density) for k, sign in dict(ends).items())
    for m in MEASURES:
        if not np.isfinite(out.values.get(m, math.nan)):
            out.flags.setdefault(m, out.flags.get("all", out.flags.get("body", "not taken")))
    return out


def ingest(path: str, study_id: str, source: str, subject_id: Optional[str] = None,
           series_uid: Optional[str] = None, fit_edges: bool = True) -> Column:
    """A CT's intensities to a column: a NIfTI file, a folder of DICOM files (one series, or the one
    `series_uid` names) or one DICOM file holding an Enhanced CT Image."""
    from .readers import read_volume
    vol = read_volume(path, series_uid)
    if min(vol.hu.shape) < 3:
        raise SystemExit("%s holds %s voxels: the mask-free mode follows the canal through the slices, so it needs a "
                         "volume, not one slice" % (path, " x ".join(str(n) for n in vol.hu.shape)))
    bodies, found = measure(vol, fit_edges)
    levels = [b.level for b in bodies]
    expresses = {"L6": False, "T13": False, "ribs": False}
    spacing = np.linalg.norm(vol.affine[:3, :3], axis=0)
    line = found.centreline
    study = {"study_id": study_id, "subject_id": subject_id or study_id, "source": source, "modality": "ct",
             "views": ["ct"], "annotation": "none", "made_by": "scanimport.intensity (mask-free)",
             "scheme": "none: no labels, chords from intensities", "expresses": expresses,
             "scale_log_mean": 0.0, "scale_log_sd": 0.0, "volume": vol.source,
             "spacing_mm": [round(float(s), 4) for s in spacing], "problems": found.problems,
             "covariates": vol.header,
             "mask_free": {"edges": "blurred-step fit (edges.py)" if fit_edges else "half-maximum only",
                           "discs_mm": found.discs,
                           "canal_slices": line.found_slices if line else 0,
                           "canal_slices_skipped": line.skipped_slices if line else 0,
                           "centreline_mm": round(float(len(line.points) - 1), 1) if line else 0.0},
             "measured": sorted(m for m in SEVEN if any(np.isfinite(b.values.get(m, math.nan)) for b in bodies))}
    study.update(facts_from_levels(levels, expresses))
    return Column(study=study, bodies=bodies)
