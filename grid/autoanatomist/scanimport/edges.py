"""Where a bone surface lies under the scanner's blur: Treece's blurred-step model fitted to
intensity profiles, for the mask-free mode.

The half-maximum rule that places intensity.py's edges is exact only for a structure thicker
than the scanner's blur. A vertebra's cortex is often thinner (end plates and canal walls under
1 mm, the research note's inference in its section 2, which no source read tested). Such a
cortex's blurred profile is a low, wide bump, so the half-maximum edge lies outside the true
surface, and a body reads too wide and its canal
too narrow (by more than a millimetre on every width and depth of a 0.5 mm cortex at 1 mm blur in
tests/test_intensity.py, and by up to about 2 mm on the phantoms of the table in README.md). The
sources agree in kind: on 16 cadaveric femurs the half-maximum variant overstated cortical
thickness by 0.90 +/- 0.92 mm (Treece, Gee and Poole, CUED/F-INFENG/TR634, 2009), and Treece and
Gee (2015) find cortex under about 3 mm too blurred on clinical CT for thresholding or
full-width half-maximum methods to give its width. Cortical bone mapping (Treece GM, Gee AH,
Mayhew PM, Poole KES. Med Image Anal 2010, PMID 20163980, whose report is TR634; Treece and Gee,
Med Image Anal 2015;20:249-264) fits each profile normal to the surface with piecewise-constant tissue levels
blurred by a Gaussian. What its sources report, as the research note records them (section 2),
is the cortex's thickness, not where its outer surface lies: -0.01 +/- 0.58 mm over cortices of
0.3 to 4 mm on those femurs (TR634), and 0.12 +/- 0.39 mm over 1 to 3 mm (Treece and Gee 2015).
No source read measured the outer-surface position, which is what a chord uses; here it is
checked on phantoms only. This module fits that model and reports, per vertebra and kind of
surface, how far the half-maximum edge lies outside the fitted surface, so intensity.py can move
each chord's ends by it.

THE MODEL, as US 10,360,681 B2 (Humbert L, 2015) writes Treece's: along a profile with x
increasing into the bone,

    y(x) = y0 + (y1 - y0) Phi((x - a) / sigma) + (y2 - y1) Phi((x - a - t) / sigma)

with y0 the tissue outside, y1 the cortex, y2 the bone inside it, a the outer surface, t the
cortex's thickness and sigma the blur's SD (Phi the standard normal distribution function).

HOW IT IS FITTED, and why so. For thin cortex, density and thickness trade off (Treece, Poole and
Gee, Med Image Anal 2012, their report TR665, call the free problem ill-posed), so the fit holds
the cortical density at one value. Cortical bone mapping's first version holds one value too,
but estimates it from the scan itself, over the whole surface, before the per-point fit
(Stradview's "Estimate cortical density", after which version 1 holds it). This module holds a
fixed value instead, CORTICAL_HU, chosen beforehand: that is its own departure from cortical
bone mapping, and a density estimated over the whole scan, as cortical bone mapping estimates
it, was not tried here. Stradview's guidance warns that an estimated cortical density "much less
than 1000 HU" likely means the thickness is overestimated, and says the best results need a
prior estimate of the unblurred cortex's HU. Where the cortex
is denser than CORTICAL_HU the fit reads it as thicker than it is and leaves the surface a little
outward, so a chord between two such surfaces is a little long; where it is less dense, as an
osteoporotic or porous shell is, the fit reads it as thinner and moves the surface inward of the
truth, so the chord is short. On profiles drawn by the model the surface stays within the
cortex's thickness of the truth either way (tests/test_intensity.py). On the phantoms the tests
hold every chord of a 0.5 mm cortex of 1,500 HU at 1 mm blur within 0.5 mm of the truth, and of a
1 mm cortex of 800 HU at 0.6 mm blur within 0.75 mm, the ends moved inward too far; the table in
README.md, which tests/bench_mask_free.py writes, gives every phantom's errors.

Fitting the density as well, per kind of surface on each vertebra, on DENSITY_GRID_HU (600 to
1,800 HU), was tried and is not used. That trial is a local estimate, not cortical bone
mapping's one density over the scan. It is kept as fit_density so the trial can be run again:
`python -m scanimport.tests.bench_mask_free --density "thin dense" default` adds its errors and
the densities it chose as two more columns. On the thin dense phantom (a 0.5 mm cortex of
1,500 HU) it took the worst chord from 0.24 to 0.74 mm and chose 600 HU for the walls and the
end-plates and 1,800 HU for the canal of the one vertebra; on the default phantom (a 1 mm cortex
of 800 HU) it took the worst chord from 0.67 to 0.57 mm, choosing 600 to 1,000 HU. So it helps a
little where the held density is far off, harms where it is near, and its densities run from one
end of the grid to the other on one vertebra, which is the ill-posedness Treece names; Treece and
Gee (2015) found local density estimable only above 800 mg/cm3. So CORTICAL_HU is held at
1,200 HU, this module's own choice: a dense cortex at clinical kVp, above the 1,000 HU that
Stradview's warning names.

The blur is held common to all the profiles of one kind of surface on one vertebra (walls,
end-plates, canal), as cortical bone mapping estimates it over a surface before the per-point
fit, and separately for the end-plates, which run across the slices, and the walls, which run
along them, as its second version does for in-plane and out-of-plane blur. y0 and y2 enter the
model linearly, so for each surface position, thickness and blur on a fixed grid they are solved
in closed form by least squares, and each profile takes its best node, the lowest index on a
tie. The fixed grid with levels in closed form, in place of the Levenberg-Marquardt fit the
patent describes, is this module's choice, so that no starting value and no iteration enter. Nodes whose solution puts the cortex below the tissue on either side are not physical and
are passed over. A profile with no physical node at a blur (one whose inner part is solid bone
denser than CORTICAL_HU, say) is left out at that blur. Among the blurs that keep a majority of
the profiles and at least MIN_PROFILES, the one chosen has the least sum of the profiles'
smallest errors, as many of them as that majority: a trimmed sum, as least trimmed squares is in
robust statistics. The shift applied to the chords is the median of the kept profiles' surfaces,
one shift per kind of surface on each vertebra where cortical bone mapping keeps a surface point
by point: this module's choice, since a chord needs only where its two ends lie and a median
over a surface's profiles is steadier than any one of them. The trimming is this module's choice, so that a minority of profiles the model cannot describe
neither vetoes a blur nor steers it, in the spirit of Stradview's rejecting outlying measurements
before it smooths; the plain sum over every profile it replaced let one profile that runs into
dense bone pull the blur or cancel the fit of its whole kind of surface (tests/test_intensity.py).
There is no starting value, no iteration and no random number: the same profiles give the same
surface on the same machine and the same numpy, scipy and BLAS build. On another CPU or BLAS
library the floating-point kernels may round the last bits differently, which can, rarely, tip a
tie between two nodes.

WHAT IT CANNOT DO. The grid's step (0.05 mm in surface position) bounds its resolution. A
profile that runs into another bone within PROFILE_IN_MM or PROFILE_OUT_MM breaks the model's
three levels; a minority of such profiles is left out or outvoted, as above, and a majority is
not. The model knows no partial-volume across the profile (a surface oblique to the slices adds
blur, which the fitted sigma absorbs). Across slices thicker than about 2 mm the profiles
through an end-plate are linear interpolations between samples a slice apart, which the model
does not describe: on the phantom with 3 mm slices the fit made the posterior height worse than
the half-maximum edge alone (the 3 mm row of the table in README.md), and the README says so. Its
accuracy on vertebrae has not been measured against a reference in any source read (research
note, section 2); it is tested here on synthetic vertebrae of known size at several blurs and
cortical densities.

numpy and scipy run it: the least squares is closed form over a fixed grid, a few array
reductions per blur, which PyTensor would compile to the same operations with nothing gained.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy import ndimage
from scipy.special import ndtr

# The fixed cortical density y1: this module's choice, a dense cortex at clinical kVp, above the
# 1000 HU below which Stradview warns ("much less than 1000 HU") that the thickness is likely
# overestimated; cortical bone mapping estimates its one density from the scan instead (HOW IT
# IS FITTED).
CORTICAL_HU = 1200.0
# The profile's sampling step: this module's choice, far finer than any CT voxel, so the profile
# follows the linearly interpolated volume and adds no error of its own.
STEP_MM = 0.1
# How far a profile reaches into the bone and out of it: this module's choice, 7 mm in all, about
# three times a 2 mm cortex as Stradview's guidance asks of a measurement line ("approximately
# three times the thickness of the thickest cortex"), and short of the far wall of a canal.
PROFILE_IN_MM, PROFILE_OUT_MM = 4.0, 3.0
# The fit's grid, each this module's choice. The outer surface from 1.5 mm outward of the
# half-maximum edge to 2.5 mm inward, past MAX_SHIFT_MM either way, every 0.05 mm (the
# resolution); the cortex up to 3 mm, below which Treece and Gee (2015) find thresholding fails;
# the blur's SD from a sharp kernel's 0.3 mm to a soft one's 2.5 mm.
SURFACE_MM = np.round(np.arange(-1.5, 2.5 + 1e-9, 0.05), 4)
THICKNESS_MM = np.round(np.arange(0.1, 3.0 + 1e-9, 0.1), 4)
SIGMA_MM = np.round(np.arange(0.3, 2.5 + 1e-9, 0.05), 4)
# This module's choice: with fewer profiles the median rests on one or two of them.
MIN_PROFILES = 5
# This module's choice: a fitted shift beyond this is more likely a failed fit than the blur, and
# is not believed (the half-maximum's own error on the phantoms reaches about 2 mm per chord, so
# about 1 mm per surface).
MAX_SHIFT_MM = 2.0
# The densities fit_density tries, the trial HOW IT IS FITTED describes and does not use: this
# module's choice, from a porous shell to the densest cortex, every 200 HU.
DENSITY_GRID_HU = np.arange(600.0, 1800.0 + 1e-9, 200.0)


@dataclass
class SurfaceFit:
    """One kind of surface on one vertebra: the common blur, each kept profile's outer surface
    inward of its half-maximum edge, their median (the shift applied to the chords), how many
    profiles were kept, why the fit is not believed if it is not, and the cortical density it
    was fitted with."""
    sigma: float
    surfaces: np.ndarray
    shift: float
    profiles: int
    reason: str = ""
    cortical: float = CORTICAL_HU


def positions(inward: float = PROFILE_IN_MM, outward: float = PROFILE_OUT_MM) -> np.ndarray:
    """The sample positions of a profile, x increasing into the bone, 0 at the half-maximum edge."""
    n_out, n_in = int(round(outward / STEP_MM)), int(round(inward / STEP_MM))
    return np.arange(-n_out, n_in + 1) * STEP_MM


def basis(x: np.ndarray, sigma: float) -> Tuple[np.ndarray, np.ndarray]:
    """Phi((x - a) / sigma) for every surface a, (A, N), and Phi((x - a - t) / sigma) for every
    surface and thickness, (A, T, N)."""
    a = SURFACE_MM[:, None]
    pa = ndtr((x[None, :] - a) / sigma)
    pb = ndtr((x[None, None, :] - a[:, :, None] - THICKNESS_MM[None, :, None]) / sigma)
    return pa, pb


def errors(y: np.ndarray, x: np.ndarray, sigma: float, cortical: float) -> Tuple[np.ndarray, np.ndarray]:
    """For profiles y (P, N): the least-squares error at every (surface, thickness) node, (P, A, T),
    with y0 and y2 solved in closed form, inf where the solution is not physical; and the node's
    surface positions, (A,)."""
    pa, pb = basis(x, sigma)
    u = np.broadcast_to((1.0 - pa)[:, None, :], pb.shape)    # weight of y0
    v = pb                                                     # weight of y2
    c = cortical * (pa[:, None, :] - pb)                       # the cortex's fixed part
    uu, uv, vv = (u * u).sum(-1), (u * v).sum(-1), (v * v).sum(-1)
    uc, vc, cc = (u * c).sum(-1), (v * c).sum(-1), (c * c).sum(-1)
    det = uu * vv - uv * uv
    yu = np.einsum("pn,an->pa", y, 1.0 - pa)[:, :, None]
    yv = np.einsum("pn,atn->pat", y, pb)
    yc = np.einsum("pn,atn->pat", y, c)
    yy = (y * y).sum(-1)[:, None, None]
    ru, rv = yu - uc, yv - vc                                  # u.(y - c), v.(y - c)
    with np.errstate(divide="ignore", invalid="ignore"):
        y0 = (vv * ru - uv * rv) / det
        y2 = (uu * rv - uv * ru) / det
        sse = yy - 2.0 * yc + cc - (y0 * ru + y2 * rv)
    bad = ~np.isfinite(sse) | (y0 >= cortical) | (y2 >= cortical) | (det <= 1e-12)
    return np.where(bad, np.inf, sse), SURFACE_MM


def best_blur(y: np.ndarray, x: np.ndarray, cortical: float) -> Optional[Tuple[float, float, np.ndarray]]:
    """The blur on SIGMA_MM that fits the profiles y (P, N) best at one cortical density, as
    (score, sigma, the kept profiles' surfaces), or None where no blur keeps enough of them. At
    each blur a profile with no physical node is left out, and a blur must keep a majority of the
    profiles and at least MIN_PROFILES. The score is the sum of the smallest of the profiles' least
    errors, as many as that majority (least trimmed squares), so a minority of profiles the model
    cannot describe neither vetoes a blur nor steers the choice. The first blur on the grid wins a
    tie."""
    need = max(MIN_PROFILES, len(y) // 2 + 1)
    best = None
    for s in SIGMA_MM:
        err, surf = errors(y, x, float(s), cortical)
        flat = err.reshape(len(y), -1)
        k = np.argmin(flat, axis=1)
        each = flat[np.arange(len(y)), k]
        kept = np.isfinite(each)
        if int(kept.sum()) < need:
            continue
        score = float(np.sort(each)[:need].sum())
        if best is None or score < best[0]:
            best = (score, float(s), surf[k[kept] // len(THICKNESS_MM)])
    return best


def believed(sigma: float, surfaces: np.ndarray, cortical: float) -> SurfaceFit:
    """The fit with its median shift, or the reason the shift is not believed."""
    shift = float(np.median(surfaces))
    if abs(shift) > MAX_SHIFT_MM:
        why = "a shift of %.2f mm is beyond %.1f mm and is not believed" % (shift, MAX_SHIFT_MM)
        return SurfaceFit(sigma, surfaces, 0.0, len(surfaces), why, cortical)
    return SurfaceFit(sigma, surfaces, shift, len(surfaces), "", cortical)


def too_few(n: int, cortical: float) -> Optional[SurfaceFit]:
    if n >= MIN_PROFILES:
        return None
    return SurfaceFit(math.nan, np.zeros(0), 0.0, n, "%d profiles, fewer than %d" % (n, MIN_PROFILES), cortical)


def fit(profiles: np.ndarray, x: np.ndarray, cortical: float = CORTICAL_HU) -> SurfaceFit:
    """The common blur and each profile's outer surface, at the one cortical density (step 'HOW IT
    IS FITTED')."""
    y = np.asarray(profiles, float)
    refused = too_few(len(y), cortical)
    if refused:
        return refused
    best = best_blur(y, x, cortical)
    if best is None:
        return SurfaceFit(math.nan, np.zeros(0), 0.0, len(y), "no blur fits a majority of the %d profiles with the "
                          "cortex densest" % len(y), cortical)
    return believed(best[1], best[2], cortical)


def fit_density(profiles: np.ndarray, x: np.ndarray, densities: np.ndarray = DENSITY_GRID_HU) -> SurfaceFit:
    """The fit with the cortical density chosen from `densities` as well as the blur, by the same
    trimmed score as the blur (best_blur), the lowest density winning a tie: the trial HOW IT IS FITTED describes, which
    intensity.py runs only when asked (measure(..., fit_density=True)) and the default never does."""
    y = np.asarray(profiles, float)
    refused = too_few(len(y), math.nan)
    if refused:
        return refused
    best = None
    for d in densities:
        got = best_blur(y, x, float(d))
        if got is not None and (best is None or got[0] < best[0][0]):
            best = (got, float(d))
    if best is None:
        return SurfaceFit(math.nan, np.zeros(0), 0.0, len(y), "no density and blur fit a majority of the %d profiles"
                          % len(y), math.nan)
    (_, sigma, surfaces), density = best
    return believed(sigma, surfaces, density)


# ---- profiles through a volume --------------------------------------------------------------------

def sample(hu: np.ndarray, affine_inv: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Linear interpolation of the volume at world points (..., 3), as the pseudo-mask's grid is."""
    ijk = pts.reshape(-1, 3) @ affine_inv[:3, :3].T + affine_inv[:3, 3]
    out = ndimage.map_coordinates(hu, ijk.T, order=1, mode="nearest")
    return out.reshape(pts.shape[:-1])


def crossing(values: np.ndarray, s: np.ndarray, threshold: float, outermost: bool) -> Optional[float]:
    """Where values along s cross the threshold: the outermost fall from at or above it to below
    (a surface reached from inside the bone), or the first rise to it (from inside the canal)."""
    above = values >= threshold
    if outermost:
        i = np.flatnonzero(above[:-1] & ~above[1:])
        if not len(i):
            return None
        i = int(i[-1])
    else:
        i = np.flatnonzero(~above[:-1] & above[1:])
        if not len(i):
            return None
        i = int(i[0])
    f = (values[i] - threshold) / (values[i] - values[i + 1])
    return float(s[i] + f * (s[i + 1] - s[i]))


def profiles_along(hu: np.ndarray, affine: np.ndarray, rays: List[Tuple[np.ndarray, np.ndarray, float]],
                   threshold: float, from_inside: bool) -> np.ndarray:
    """One profile per ray (origin, unit direction outward from where it starts, reach), resampled
    about its half-maximum crossing with x increasing into the bone. From inside the bone the
    surface is the outermost fall below the threshold and the bone lies back along the ray; from
    inside the canal it is the first rise, and the bone lies ahead."""
    inv = np.linalg.inv(affine)
    x = positions()
    out = []
    for origin, d, reach in rays:
        s = np.arange(0.0, reach + 1e-9, STEP_MM / 2.0)
        vals = sample(hu, inv, origin[None, :] + s[:, None] * d[None, :])
        at = crossing(vals, s, threshold, outermost=from_inside)
        if at is None:
            continue
        along = at - x if from_inside else at + x
        out.append(sample(hu, inv, origin[None, :] + along[:, None] * d[None, :]))
    return np.array(out) if out else np.zeros((0, len(x)))
