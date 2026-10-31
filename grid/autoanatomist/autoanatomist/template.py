"""A template vertebra stretched to drawn parameters, its landmarks set and so exact (bordercall #55,
step 4 of #51).

greg's direction of 2026-10-30 (thread "Train on randomized spine phantoms"): phantoms whose
annotation is exact by construction, their parameters drawn jointly from the population's
correlations. phantom.py's vertebra is a frustum with straight processes; this module keeps any
vertebra as a template, a shape in its own frame with the oracle's landmarks read off it, and makes
each drawn level by stretching the template so that each of the seven measured chords takes its
drawn value. The landmarks of a stretched level are set, not found: their 3-D positions, and
through project.py their 2-D ones, are the truth whatever a reader of the image does.

THE STRETCH. Each of the seven measures is an extent of one region of the vertebra, read along one
axis of the level's frame (x right, y anterior, z up, the body's posterior wall at y = wall):

    endplate, endplate_depth               x and y across the top slab of the body
    endplate_lower, endplate_lower_depth   x and y across the bottom slab
    h_post                                 z along the posterior column
    canal_w, canal_ap                      x and y across the canal, behind the wall

An extent scales exactly with a stretch that is constant over its region, so the stretch gives each
region its own ratio, the drawn value over the template's, and changes smoothly only between the
regions, where nothing is measured: x and y in the body by the top slab's ratios above z_top and the
bottom slab's below z_bot, blended between; y behind the wall by the canal's depth ratio, about the
wall, which stays put; x behind the wall by the canal's width ratio across the canal and by the
body's mean width ratio beyond it, out to the processes; z by the posterior height's ratio. Each
coordinate of the result depends on its own and on those after it in the order z, y, x, and grows
with its own, so the Jacobian is triangular with a positive diagonal: the stretch folds nowhere, by
construction, and its inverse is found one coordinate at a time.

A stretched level's set landmarks are the template's carried by the stretch, and each chord between
two of them has its drawn length. The image agrees with them to the voxel when the template's own
values are the oracle's values on the template, so those are read at several phases of the voxel
lattice against the template and averaged. tests/test_autoanatomist_template.py holds both, and that
the stretch folds nowhere.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from autoanatomist import oracle as O
from autoanatomist import phantom as PH
from autoanatomist import specs as S

MEASURED = list(S.SEVEN)
ANCHORS = list(S.EXTRA)            # read off the template and carried by the stretch, not drawn
READ_SPACING = 0.5                 # mm, the voxels a template's values are read in
READ_PHASES = 4                    # shifts of the column against those voxels, averaged
SLAB_ZONE_MM = 2.5                 # how far below the top slab's middle (above the bottom's) its ratio holds
WALL_BLEND_MM = 1.0                # half-width of the step between the body's y ratio and the canal's
BODY_REACH_BEHIND_MM = 3.0         # the body's x ratio holds this far behind the wall, the canal's beyond
CANAL_MARGIN_MM = 2.0              # the canal's x ratio holds this far beyond its walls
FOLD_FLOOR = 0.05                  # the smallest Jacobian determinant the tests allow


@dataclass
class Template:
    """A vertebra in its own frame, with the oracle's landmarks and values on it. `level` is an
    analytic phantom.py level whose frustum is the shape; a sampled shape (a mesh's voxels) takes
    its place through the same three methods."""
    level: PH.Level
    points: Dict[str, np.ndarray]
    values: Dict[str, float]

    def solid(self, p: np.ndarray) -> np.ndarray:
        return PH.solid(p, self.level)

    def inside_or_canal(self, p: np.ndarray) -> np.ndarray:
        parts = PH.parts(p, self.level)
        return parts["body"] | parts["arch"] | parts["tp"] | parts["spinous"] | parts["canal"]

    def tissue(self, p: np.ndarray) -> np.ndarray:
        return PH.tissue(p, self.level, (0.0, 0.0))

    @property
    def reach(self) -> float:
        return self.level.reach


def straight(levels: Sequence[PH.Level], spacing: float, offset: Sequence[float]) -> PH.Phantom:
    return PH.render(levels, spacing=(spacing,) * 3, tilt=((1.0, 0.0, 0.0), 0.0), grid_turn=((0.0, 0.0, 1.0), 0.0),
                     sub=1, with_ct=False, offset=offset)


def template_from(levels: Sequence[PH.Level], at: int, spacing: float = READ_SPACING,
                  phases: int = READ_PHASES) -> Template:
    """The template of levels[at]: its landmarks and values, the oracle's on a straight column of
    these levels, averaged over `phases` shifts of the column by a share of a voxel along every
    axis, so the lattice's rounding of each surface averages out."""
    keys = MEASURED + ANCHORS
    values = {k: [] for k in keys}
    points: Dict[str, list] = {}
    for k in range(phases):
        ph = straight(levels, spacing, (spacing * k / phases,) * 3)
        reading = O.ChordOracle(keys).read(ph.labels, ph.affine, ph.names)[at]
        centre, rot = ph.centres[at], ph.rotations[at]
        for key in keys:
            m = reading.measurements[key]
            if not m.taken:
                raise ValueError("the oracle took no %s on the template %s: %s" % (key, levels[at].name, m.flag))
            values[key].append(float(m.value))
            for name, xyz in m.points.items():
                points.setdefault(name, []).append((np.asarray(xyz, float) - centre) @ rot)
    return Template(level=levels[at], points={n: np.mean(v, axis=0) for n, v in points.items()},
                    values={k: float(np.mean(v)) for k, v in values.items()})


# the stretch

def step(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """0 below lo, 1 above hi, the smooth cubic step between."""
    t = np.clip((v - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def step_integral(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """The integral of step from lo to v, for v >= lo."""
    width = hi - lo
    t = np.clip((v - lo) / width, 0.0, 1.0)
    return width * (t ** 3 - 0.5 * t ** 4) + np.maximum(v - hi, 0.0)


@dataclass
class Stretch:
    """The template's frame to the drawn level's (the module's THE STRETCH), and back."""
    wall: float
    z_bot: float
    z_top: float
    canal_x: float
    ratio: Dict[str, float]

    # the ratios each coordinate takes, where it takes them

    def body_x(self, z):
        r = self.ratio
        return r["endplate_lower"] + (r["endplate"] - r["endplate_lower"]) * step(z, self.z_bot, self.z_top)

    def body_y(self, z):
        r = self.ratio
        return r["endplate_lower_depth"] + (r["endplate_depth"] - r["endplate_lower_depth"]) * step(z, self.z_bot, self.z_top)

    @property
    def side_x(self) -> float:
        return 0.5 * (self.ratio["endplate"] + self.ratio["endplate_lower"])

    def front_share(self, y):
        """1 where x takes the body's ratio, 0 where it takes the canal's and the processes'."""
        edge = self.wall - BODY_REACH_BEHIND_MM
        return step(y, edge - WALL_BLEND_MM, edge + WALL_BLEND_MM)

    def back_x(self, x):
        """x behind the body: the canal's ratio across the canal, the body's mean beyond it, the
        integral of a smooth step between, so it grows with x."""
        a, lo, hi = np.abs(x), self.canal_x - WALL_BLEND_MM, self.canal_x + WALL_BLEND_MM
        rc, rs = self.ratio["canal_w"], self.side_x
        return np.sign(x) * (rc * a + (rs - rc) * step_integral(np.maximum(a, lo), lo, hi))

    def scale_y(self, y, body):
        """y's ratio: the body's (body, at each point's height) in front of the wall, the canal's
        behind it."""
        w = step(y, self.wall - WALL_BLEND_MM, self.wall + WALL_BLEND_MM)
        return w * body + (1.0 - w) * self.ratio["canal_ap"]

    # the map and its inverse

    def forward(self, p: np.ndarray) -> np.ndarray:
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        w = self.front_share(y)
        return np.column_stack([w * x * self.body_x(z) + (1.0 - w) * self.back_x(x),
                                self.wall + (y - self.wall) * self.scale_y(y, self.body_y(z)),
                                z * self.ratio["h_post"]])

    def inverse(self, q: np.ndarray, steps: int = 48) -> np.ndarray:
        z = q[:, 2] / self.ratio["h_post"]
        by = self.body_y(z)
        y = self.solve(lambda y_: self.wall + (y_ - self.wall) * self.scale_y(y_, by), q[:, 1], self.wall, steps)
        w, bx = self.front_share(y), self.body_x(z)
        x = self.solve(lambda x_: w * x_ * bx + (1.0 - w) * self.back_x(x_), q[:, 0], 0.0, steps)
        return np.column_stack([x, y, z])

    def solve(self, f, target: np.ndarray, centre: float, steps: int) -> np.ndarray:
        """The v with f(v) = target, f growing and f(centre) = centre, by bisection: |v - centre| is
        at most |target - centre| over the smallest ratio."""
        reach = np.abs(target - centre) / min(self.ratio.values()) + 1.0
        lo, hi = centre - reach, centre + reach
        for _ in range(steps):
            mid = 0.5 * (lo + hi)
            below = f(mid) < target
            lo, hi = np.where(below, mid, lo), np.where(below, hi, mid)
        return 0.5 * (lo + hi)

    def jacobian_det(self, p: np.ndarray, h: float = 1e-3) -> np.ndarray:
        """The forward map's determinant: the product of its diagonal, the map being triangular."""
        e = np.eye(3) * h
        d = [(self.forward(p + e[j])[:, j] - self.forward(p - e[j])[:, j]) / (2 * h) for j in range(3)]
        return d[0] * d[1] * d[2]


def stretch_for(t: Template, drawn: Dict[str, float]) -> Stretch:
    z_of = lambda key: float(np.mean([t.points[n][2] for n in S.SPECS[key].points]))
    half_canal = max(abs(t.points[n][0]) for n in S.SPECS["canal_w"].points)
    z_top, z_bot = z_of("endplate") - SLAB_ZONE_MM, z_of("endplate_lower") + SLAB_ZONE_MM
    if z_top - z_bot < 2.0:                      # a body too short for two zones and a step between
        mid = 0.5 * (z_top + z_bot)
        z_top, z_bot = mid + 1.0, mid - 1.0
    return Stretch(wall=float(t.points["canal_ap.anterior"][1]), z_bot=z_bot, z_top=z_top,
                   canal_x=half_canal + CANAL_MARGIN_MM, ratio={k: drawn[k] / t.values[k] for k in MEASURED})


@dataclass
class Warp:
    """A drawn level made from a template: the stretch and the landmarks it set."""
    template: Template
    stretch: Stretch
    points: Dict[str, np.ndarray]
    drawn: Dict[str, float] = field(default_factory=dict)

    @property
    def reach(self) -> float:
        """A bound on how far from the level's centre the stretched vertebra reaches."""
        r = self.stretch.ratio.values()
        return self.template.reach * max(r) + abs(self.stretch.wall) * max(abs(1.0 - v) for v in r) + 4.0

    def solid(self, q: np.ndarray) -> np.ndarray:
        return self.template.solid(self.stretch.inverse(q))

    def tissue(self, q: np.ndarray, lv: PH.Level, half_gaps: Tuple[float, float]) -> np.ndarray:
        """The template's own tissue where the stretch takes a point into the vertebra or its canal,
        and phantom.py's soft tissue and disc round it, in the drawn level's frame."""
        out = PH.tissue_outside(q, lv, half_gaps)
        p = self.stretch.inverse(q)
        mine = self.template.inside_or_canal(p)
        out[mine] = self.template.tissue(p[mine])
        return out


def warp(t: Template, lv: PH.Level) -> PH.Level:
    """lv with its shape made from the template, every measured chord at lv's drawn value."""
    drawn = lv.truth()
    st = stretch_for(t, drawn)
    names = sorted(t.points)
    moved = st.forward(np.array([t.points[n] for n in names]))
    return PH.with_shape(lv, Warp(template=t, stretch=st, points=dict(zip(names, moved)), drawn=drawn))


def set_values(w: Warp) -> Dict[str, float]:
    """Each measured chord's length between the landmarks the stretch set."""
    return {k: float(np.linalg.norm(np.subtract(*[w.points[n] for n in S.SPECS[k].points]))) for k in MEASURED}


def landmarks_world(ph: PH.Phantom, i: int) -> Dict[str, np.ndarray]:
    """A stretched level's set landmarks in world millimetres: the truth a 2-D view projects."""
    shape = ph.levels[i].shape
    return {n: ph.centres[i] + ph.rotations[i] @ p for n, p in shape.points.items()}


def folds(lv: PH.Level, step_mm: float = 1.5) -> float:
    """The smallest Jacobian determinant of a stretched level's map over the template's points near
    the vertebra, the fold test of #55: a map that folds has one at or below 0."""
    w = lv.shape
    reach = w.template.reach
    axis = np.arange(-reach, reach + step_mm, step_mm)
    p = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), -1).reshape(-1, 3)
    p = p[w.template.solid(p)]
    return float(w.stretch.jacobian_det(p).min())
