"""Shapes beside the straight lines: curves, arcs, circles, ellipses and splines, planes and flat
polygons, curved surfaces, and volumes, each in the world's millimetres of a mask's affine, as
morphoview.lines' ends are, and each carried onto a FleXray render by morphoview.projection's
camera.

A curve is a polyline, open or closed. An arc, a circle, an ellipse and a spline are curves
sampled finely enough that no point of the true shape lies further than a tolerance from the
polyline (0.05 mm unless asked otherwise), so every curve projects the same way: a straight
segment of the world is a straight segment of the render, its ends projected, so a polyline
projects exactly, and a smooth curve within its tolerance as the render enlarges it: under a cone
beam by the magnification, sdd over the depth, and off the beam's axis by up to one over the cosine
of the ray's angle to the axis besides, for a slip along the ray's tilt; under parallel rays not at
all. A segment that runs behind the source is cut where it reaches the source's plane, since no ray
of the render passes behind the source, and what is left of the curve is kept as the pieces it
falls into. Shapes hold arrays, so each is equal only to itself.

A plane is a point and a unit normal, fitted to points by least squares where it is not given
(the smallest singular vector of the centred points, with its root mean square residual); its
patch is the rectangle of the half sides asked for about the point, and a flat polygon, a patch or
one built from its corners, projects as a closed curve. How the render sees a plane is the angle
the ray through its point makes with it: none where the plane is seen edge on, as a line, and 90
degrees face on.

A surface is triangles of the world: through a grid of points; a height above a plane over the
rectangle a patch would be, on a grid fine enough that the middle of every triangle's edge lies
within the tolerance of the surface; through points as they are, triangulated by Delaunay's rule
where they fall on the plane fitted to them; or the least-squares quadric over that plane drawn
over the same triangles, a height of degree two in the plane's two directions, which a concave
end-plate's dip below its rim is. Its rim is the curve of the edges only one triangle has, and its
sag how far it departs from its rim's plane. A flat triangle of the world is a triangle of the
render, its corners projected, so a surface projects exactly, as a polyline does, and the pixels
whose rays meet it, its shadow, are those whose centres its projected triangles cover. A surface
reaching behind the source has no one picture on a cone beam's render and is refused.

A volume is a label's voxels on its grid, the largest face-connected piece unless asked otherwise.
Its projection is an image on the render's detector: the length in mm each ray runs through the
volume (path_length), and the silhouette, where that length is above zero. Two samplings are
offered. The fine one walks each ray through the volume's box at most half the smallest voxel
spacing apart, which is the geometric chord to about a voxel. The FleXray one samples the ray as
nanoDRR does (nanodrr/drr/renderer.py, render: n points from the source to the detector, each
the label of its nearest voxel as grid_sample's nearest mode reads it, every point weighing the
step). FleXray's channel for the label is the attenuation summed over the same points, read
between voxels as grid_sample's bilinear mode reads it (fxr/drr/rendering.py, render_drr's
rendered), so on a volume of one attenuation the channel is that attenuation times the path
length at every pixel, and on a CT, whose bone borders air, the channel is above zero where the
path length is.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np
from scipy import ndimage
from scipy.spatial import Delaunay

from .projection import Camera, Projected

TOLERANCE_MM = 0.05             # how far a sampled curve may lie from the true one
NEAR = 1e-6                     # a segment is cut this far in front of the source, in mm
MOST_SAMPLES = 1 << 16          # the most points one span or one closed shape is sampled at


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    n = float(np.linalg.norm(v))
    if not n > 0:
        raise ValueError("a direction of zero length")
    return v / n


def across(normal) -> Tuple[np.ndarray, np.ndarray]:
    """Two unit directions across a normal, right-handed with it."""
    n = unit(normal)
    seed = np.eye(3)[int(np.argmin(np.abs(n)))]
    e1 = unit(np.cross(n, seed))
    return e1, np.cross(n, e1)


# ---- curves ---------------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Curve2D:
    """A curve on a render: its points' places (Projected.uv), depths and whether the render
    sampled each, in order; the index where each of its pieces starts, one piece unless the
    source's plane cut it; closed when it is one piece whose last point joins its first; and the
    world's points it is the projection of, a cut's ends among them."""
    uv: np.ndarray
    depth: np.ndarray
    in_beam: np.ndarray
    closed: bool = False
    starts: Tuple[int, ...] = (0,)
    world: Optional[np.ndarray] = None

    def pieces(self) -> List[np.ndarray]:
        ends = list(self.starts[1:]) + [len(self.uv)]
        return [self.uv[s:e] for s, e in zip(self.starts, ends)]

    def length_px(self) -> float:
        total = 0.0
        for piece in self.pieces():
            pts = np.vstack([piece, piece[:1]]) if self.closed else piece
            total += float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
        return total

    def area_px(self) -> float:
        """The area a closed curve encloses on the render, by the shoelace rule."""
        if not self.closed:
            raise ValueError("only a closed curve encloses an area")
        u, v = self.uv[:, 0], self.uv[:, 1]
        return 0.5 * abs(float(np.dot(u, np.roll(v, -1)) - np.dot(v, np.roll(u, -1))))


@dataclass(frozen=True, eq=False)
class Curve:
    """A polyline in the world, open or closed."""
    points: np.ndarray
    closed: bool = False

    def __post_init__(self):
        pts = np.atleast_2d(np.asarray(self.points, float))
        if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
            raise ValueError("a curve is two or more points in three dimensions")
        if not np.isfinite(pts).all():
            raise ValueError("a curve's points are finite")
        object.__setattr__(self, "points", pts)

    def segments(self) -> np.ndarray:
        pts = np.vstack([self.points, self.points[:1]]) if self.closed else self.points
        return np.stack([pts[:-1], pts[1:]], axis=1)

    def length(self) -> float:
        seg = self.segments()
        return float(np.linalg.norm(seg[:, 1] - seg[:, 0], axis=1).sum())

    def resampled(self, step: float) -> "Curve":
        """The curve with points at most `step` mm apart along it, its corners kept, so the
        polyline is the same."""
        out = []
        for a, b in self.segments():
            n = max(1, int(math.ceil(float(np.linalg.norm(b - a)) / step)))
            out.append(a + np.linspace(0.0, 1.0, n, endpoint=False)[:, None] * (b - a))
        if not self.closed:
            out.append(self.points[-1:])
        return Curve(np.vstack(out), self.closed)

    def project(self, camera: Camera) -> Curve2D:
        """The curve on the render: each segment cut where it runs behind the source, then its
        points projected; a closed curve cut so becomes the open pieces left of it."""
        pts, starts = in_front(self.segments(), camera, closed=self.closed)
        got = camera.project(pts)
        cut = starts is not None
        return Curve2D(got.uv, got.depth, got.in_beam, self.closed and not cut, tuple(starts or (0,)), pts)


def in_front(segments: np.ndarray, camera: Camera, closed: bool) -> Tuple[np.ndarray, Optional[List[int]]]:
    """A polyline's points with each segment cut to the part in front of the source's plane, and
    the index where each piece left starts, or None where nothing was cut. Parallel rays reach
    behind nothing they render, so under them the points stand as they are."""
    whole = segments[:, 0] if closed else np.vstack([segments[:, 0], segments[-1:, 1]])
    depth = camera.camera_points(whole)[:, 2]
    if camera.view.orthographic or bool((depth > NEAR).all()):
        return whole, None
    out: List[np.ndarray] = []
    starts: List[int] = []
    joined = False
    for a, b in segments:
        za, zb = camera.camera_points(np.stack([a, b]))[:, 2]
        if za <= NEAR and zb <= NEAR:
            joined = False
            continue
        if za <= NEAR or zb <= NEAR:
            p = a + (NEAR - za) / (zb - za) * (b - a)
            a, b = (p, b) if za <= NEAR else (a, p)
        if not joined:
            starts.append(len(out))
            out.append(a)
        out.append(b)
        joined = zb > NEAR
    if not out:
        raise ValueError("the curve lies wholly behind the source")
    if closed and joined and len(starts) > 1:
        # the last piece runs on through the curve's first point into the first piece
        merged = out[starts[-1]:-1] + out[:starts[1]]
        rest = out[starts[1]:starts[-1]]
        starts = [0] + [s - starts[1] + len(merged) for s in starts[1:-1]]
        out = merged + rest
    return np.stack(out), starts


def segments_needed(radius: float, angle: float, tolerance: float) -> int:
    """How many chords an arc of `radius` and `angle` radians needs so that none lies further
    than `tolerance` from it: a chord's sagitta is r (1 - cos(t / 2))."""
    if tolerance >= radius:
        return max(1, int(math.ceil(abs(angle) / math.pi)))
    step = 2.0 * math.acos(1.0 - tolerance / radius)
    return max(1, int(math.ceil(abs(angle) / step)))


def arc(centre, normal, start, angle_deg: float, tolerance: float = TOLERANCE_MM) -> Curve:
    """The arc about `centre` in the plane of `normal`, from `start`'s place in that plane,
    turning `angle_deg` the right-handed way about the normal; open."""
    centre, n = np.asarray(centre, float), unit(normal)
    r0 = np.asarray(start, float) - centre
    r0 = r0 - (r0 @ n) * n
    radius = float(np.linalg.norm(r0))
    if not radius > 0:
        raise ValueError("an arc's start lies on its axis")
    e1 = r0 / radius
    e2 = np.cross(n, e1)
    angle = math.radians(angle_deg)
    t = np.linspace(0.0, angle, segments_needed(radius, angle, tolerance) + 1)
    return Curve(centre + radius * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2))


def circle(centre, normal, radius: float, tolerance: float = TOLERANCE_MM) -> Curve:
    """The circle of `radius` about `centre` in the plane of `normal`, closed."""
    if not (math.isfinite(radius) and radius > 0):
        raise ValueError("a circle's radius is above zero")
    centre, n = np.asarray(centre, float), unit(normal)
    e1, e2 = across(n)
    k = max(3, segments_needed(radius, 2.0 * math.pi, tolerance))
    t = np.linspace(0.0, 2.0 * math.pi, k, endpoint=False)
    return Curve(centre + radius * (np.cos(t)[:, None] * e1 + np.sin(t)[:, None] * e2), closed=True)


def ellipse(centre, semi_a, semi_b, tolerance: float = TOLERANCE_MM) -> Curve:
    """The ellipse about `centre` whose semi-axes are the perpendicular vectors semi_a and semi_b,
    closed, its points c + cos t a + sin t b, as many as keep every chord within the tolerance."""
    centre, a, b = (np.asarray(x, float) for x in (centre, semi_a, semi_b))
    la, lb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if not (la > 0 and lb > 0):
        raise ValueError("an ellipse's semi-axes have length")
    if abs(float(a @ b)) > 1e-9 * la * lb:
        raise ValueError("an ellipse's semi-axes are perpendicular")

    def at(t: np.ndarray) -> np.ndarray:
        return centre + np.cos(t)[:, None] * a + np.sin(t)[:, None] * b

    k = max(3, segments_needed(max(la, lb), 2.0 * math.pi, tolerance))
    return Curve(refined(at, 0.0, 2.0 * math.pi, k, tolerance, closed=True), closed=True)


def refined(at: Callable[[np.ndarray], np.ndarray], start: float, stop: float, k: int, tolerance: float,
            closed: bool) -> np.ndarray:
    """A curve's points at k even steps of its parameter from start to stop, k doubled until each
    step's midpoint lies within the tolerance of its chord's; the stop's point left off, for a
    closed curve or the next span to give."""
    while True:
        fine = at(np.linspace(start, stop, 2 * k + 1))
        coarse = fine[::2]
        mid = 0.5 * (coarse[:-1] + coarse[1:])
        if float(np.linalg.norm(fine[1::2] - mid, axis=1).max()) <= tolerance or k >= MOST_SAMPLES:
            return coarse[:-1]
        k *= 2


def spline(points, closed: bool = False, tolerance: float = TOLERANCE_MM) -> Curve:
    """The centripetal Catmull-Rom spline through the points, which passes through every one and,
    alone of the Catmull-Rom splines, forms no cusp and no loop within a span (Yuksel, Schaefer and
    Keyser 2011), each span sampled until halving its step moves no sample point by more than the
    tolerance."""
    pts = np.atleast_2d(np.asarray(points, float))
    if len(pts) < 2 or pts.shape[1] != 3:
        raise ValueError("a spline needs two or more points in three dimensions")
    ring = np.vstack([pts, pts[:1]]) if closed else pts
    if not (np.linalg.norm(np.diff(ring, axis=0), axis=1) > 0).all():
        raise ValueError("a spline's points follow one another without repeating")
    if closed:
        ext = np.vstack([pts[-1:], pts, pts[:2]])
        spans = len(pts)
    else:
        ext = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
        spans = len(pts) - 1
    out = [refined(lambda s, p=ext[i:i + 4]: catmull_rom(p, s), 0.0, 1.0, 4, tolerance, closed=False)
           for i in range(spans)]
    if not closed:
        out.append(pts[-1:])
    return Curve(np.vstack(out), closed)


def catmull_rom(p: np.ndarray, s: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """Points of the centripetal (alpha 1/2) Catmull-Rom span between p[1] and p[2] at s in 0 to 1,
    by the Barry and Goldman pyramid."""
    d = np.linalg.norm(np.diff(p, axis=0), axis=1) ** alpha
    t = np.concatenate([[0.0], np.cumsum(d)])
    tt = (t[1] + s * (t[2] - t[1]))[:, None]

    def lerp(a, b, ta, tb):
        return ((tb - tt) * a + (tt - ta) * b) / (tb - ta)

    a1, a2, a3 = lerp(p[0], p[1], t[0], t[1]), lerp(p[1], p[2], t[1], t[2]), lerp(p[2], p[3], t[2], t[3])
    b1, b2 = lerp(a1, a2, t[0], t[2]), lerp(a2, a3, t[1], t[3])
    return lerp(b1, b2, t[1], t[2])


# ---- planes ---------------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Plane:
    """A plane through `point` with the unit `normal`."""
    point: np.ndarray
    normal: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, "point", np.asarray(self.point, float))
        object.__setattr__(self, "normal", unit(self.normal))

    @classmethod
    def fit(cls, points) -> Tuple["Plane", float]:
        """The least-squares plane through three or more points and its root mean square residual
        in mm."""
        pts = np.atleast_2d(np.asarray(points, float))
        if len(pts) < 3 or pts.shape[1] != 3:
            raise ValueError("a plane needs three or more points in three dimensions")
        centre = pts.mean(axis=0)
        _, sv, vt = np.linalg.svd(pts - centre, full_matrices=False)
        if not sv[1] > 1e-12 * max(1.0, float(sv[0])):
            raise ValueError("the points lie on one line")
        return cls(centre, vt[2]), float(sv[2] / math.sqrt(len(pts)))

    def distance(self, points) -> np.ndarray:
        """Each point's signed distance from the plane, positive on the normal's side."""
        return (np.atleast_2d(np.asarray(points, float)) - self.point) @ self.normal

    def angle_deg(self, other: "Plane") -> float:
        """The angle between the two planes, 0 to 90 degrees."""
        c = min(1.0, abs(float(self.normal @ other.normal)))
        return math.degrees(math.acos(c))

    def meet(self, a, b) -> Optional[np.ndarray]:
        """Where the line through a and b meets the plane, or None where it runs parallel."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        den = float((b - a) @ self.normal)
        if abs(den) < 1e-12 * max(1.0, float(np.linalg.norm(b - a))):
            return None
        return a + float((self.point - a) @ self.normal) / den * (b - a)

    def seen_at_deg(self, camera: Camera) -> float:
        """The angle the render's ray through the plane's point makes with the plane: none where
        the render sees the plane edge on, as a line, 90 degrees where it sees it face on."""
        d = camera.ray_direction(self.point)[0]
        return math.degrees(math.asin(min(1.0, abs(float(d @ self.normal)))))

    def axes(self, toward=None) -> Tuple[np.ndarray, np.ndarray]:
        """Two unit directions in the plane, right-handed with its normal, the first along the
        part of `toward` that lies in the plane where `toward` is given."""
        if toward is None:
            return across(self.normal)
        t = np.asarray(toward, float)
        e1 = unit(t - (t @ self.normal) * self.normal)
        return e1, np.cross(self.normal, e1)

    def patch(self, half_a: float, half_b: float, toward=None) -> "Polygon":
        """The rectangle of half sides half_a and half_b about the point, its sides along the
        plane's axes (Plane.axes)."""
        e1, e2 = self.axes(toward)
        corners = [self.point + sa * half_a * e1 + sb * half_b * e2 for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        return Polygon(np.stack(corners))


@dataclass(frozen=True, eq=False)
class Polygon:
    """A flat polygon in the world, its corners in order."""
    corners: np.ndarray

    def __post_init__(self):
        pts = np.atleast_2d(np.asarray(self.corners, float))
        if pts.shape[1] != 3 or len(pts) < 3:
            raise ValueError("a polygon is three or more corners in three dimensions")
        object.__setattr__(self, "corners", pts)

    def plane(self) -> Plane:
        return Plane.fit(self.corners)[0]

    def area(self) -> float:
        """The area in mm2, half the length of the sum of the corners' cross products."""
        c = self.corners - self.corners.mean(axis=0)
        return 0.5 * float(np.linalg.norm(np.cross(c, np.roll(c, -1, axis=0)).sum(axis=0)))

    def outline(self) -> Curve:
        return Curve(self.corners, closed=True)

    def project(self, camera: Camera) -> Curve2D:
        return self.outline().project(camera)


# ---- surfaces -------------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Surface2D:
    """A surface on a render: its vertices' places, depths and whether the render sampled each,
    as Projected gives them, and its triangles."""
    uv: np.ndarray
    depth: np.ndarray
    in_beam: np.ndarray
    triangles: np.ndarray

    def area_px(self) -> float:
        """Its triangles' areas on the render, summed: the area its shadow covers where no two of
        them fall on one another."""
        c = self.uv[self.triangles]
        return 0.5 * float(np.abs(cross2(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0])).sum())

    def silhouette(self, height: int, width: int, chunk: int = 1 << 20) -> np.ndarray:
        """The pixels of a render of height by width pixels whose centres fall in one of its
        triangles, a centre on a triangle's edge counted in."""
        out = np.zeros((height, width), bool)
        tri = self.uv[self.triangles]
        # each triangle's box of pixel centres, held to the image before it is made whole numbers
        lo = np.clip(np.ceil(tri.min(axis=1) - 0.5), 0, [width, height]).astype(np.int64)
        hi = np.clip(np.floor(tri.max(axis=1) - 0.5), -1, [width - 1, height - 1]).astype(np.int64)
        cols, rows = np.clip(hi - lo + 1, 0, None).T
        count = np.where(cross2(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]) != 0, cols * rows, 0)
        total = np.cumsum(count)
        first = 0
        while first < len(tri):
            # as many triangles as keep their candidate pixels within the chunk, one at least
            before = int(total[first - 1]) if first else 0
            last = max(first + 1, int(np.searchsorted(total, before + chunk, side="right")))
            mark_inside(out, tri[first:last], lo[first:last], cols[first:last], count[first:last])
            first = last
        return out


def cross2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def mark_inside(out: np.ndarray, tri: np.ndarray, lo: np.ndarray, cols: np.ndarray, count: np.ndarray) -> None:
    """Marks the pixels of each triangle's box whose centres fall inside it, by the three edges'
    side tests from the triangle's first corner, so a triangle far from the image's corner tests
    as finely as one near it."""
    which = np.repeat(np.arange(len(tri)), count)
    if not len(which):
        return
    k = np.arange(len(which)) - np.repeat(np.cumsum(count) - count, count)
    col, row = lo[which, 0] + k % cols[which], lo[which, 1] + k // cols[which]
    a = tri[which, 0]
    p = np.stack([col + 0.5, row + 0.5], axis=1) - a
    b, c = tri[which, 1] - a, tri[which, 2] - a
    turn = np.sign(cross2(b, c))
    slack = 1e-12 * (np.abs(b).sum(axis=1) + np.abs(c).sum(axis=1)) ** 2
    sides = np.stack([cross2(b, p), cross2(c - b, p - b), cross2(-c, p - c)], axis=1) * turn[:, None]
    hit = (sides >= -slack[:, None]).all(axis=1)
    out[row[hit], col[hit]] = True


@dataclass(frozen=True, eq=False)
class Surface:
    """A surface in the world as triangles: its vertices, and each triangle's three corners as
    indices into them."""
    vertices: np.ndarray
    triangles: np.ndarray

    def __post_init__(self):
        pts = np.asarray(self.vertices, float)
        tri = np.asarray(self.triangles)
        if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 3 or not np.isfinite(pts).all():
            raise ValueError("a surface's vertices are three or more finite points in three dimensions")
        if tri.ndim != 2 or tri.shape[1] != 3 or len(tri) < 1 or tri.dtype.kind not in "iu":
            raise ValueError("a surface's triangles are rows of three vertex indices")
        ordered = np.sort(tri, axis=1)
        if ordered[:, 0].min() < 0 or ordered[:, 2].max() >= len(pts) or bool((np.diff(ordered, axis=1) == 0).any()):
            raise ValueError("each of a surface's triangles names three different vertices of it")
        object.__setattr__(self, "vertices", pts)
        object.__setattr__(self, "triangles", tri.astype(np.int64))

    @classmethod
    def from_grid(cls, points) -> "Surface":
        """The surface through a grid of points, rows by columns, each cell split into two
        triangles across its diagonal from (i, j) to (i + 1, j + 1), every triangle turning the
        right-handed way about the rows' direction crossed with the columns'."""
        g = np.asarray(points, float)
        if g.ndim != 3 or g.shape[2] != 3 or min(g.shape[:2]) < 2:
            raise ValueError("a grid of points is two or more rows by two or more columns in three dimensions")
        k = np.arange(g.shape[0] * g.shape[1]).reshape(g.shape[:2])
        a, b, c, d = (x.ravel() for x in (k[:-1, :-1], k[:-1, 1:], k[1:, 1:], k[1:, :-1]))
        return cls(g.reshape(-1, 3), np.concatenate([np.stack([a, d, c], axis=1), np.stack([a, c, b], axis=1)]))

    @classmethod
    def over(cls, plane: Plane, height: Callable[[np.ndarray, np.ndarray], np.ndarray], half_a: float,
             half_b: float, toward=None, tolerance: float = TOLERANCE_MM) -> "Surface":
        """The surface height(u, v) mm above the plane, along its normal, over the rectangle that
        Plane.patch lays out, u and v along the plane's axes, on a grid fine enough that the
        middle of every triangle's edge lies within the tolerance of the surface's point there."""
        if not (half_a > 0 and half_b > 0):
            raise ValueError("a surface's half sides are above zero")
        e1, e2 = plane.axes(toward)

        def at(u: np.ndarray, v: np.ndarray) -> np.ndarray:
            h = np.broadcast_to(np.asarray(height(u, v), float), u.shape)
            return plane.point + u[..., None] * e1 + v[..., None] * e2 + h[..., None] * plane.normal

        return cls.from_grid(refined_grid(at, float(half_a), float(half_b), tolerance))

    @classmethod
    def through(cls, points) -> "Surface":
        """The surface through the points as they are, triangulated by Delaunay's rule where they
        fall on the plane fitted to them, so it covers their outline's convex hull."""
        pts = np.asarray(points, float)
        plane, _ = Plane.fit(pts)
        e1, e2 = plane.axes()
        return lifted(pts, np.stack([(pts - plane.point) @ e1, (pts - plane.point) @ e2], axis=1))

    @classmethod
    def fit(cls, points) -> Tuple["Surface", float]:
        """The least-squares quadric through three-dimensional points, a height along the normal
        of the plane fitted to them, h = c0 + c1 u + c2 v + c3 u2 + c4 u v + c5 v2 with u and v
        across it, drawn over the points as Surface.through triangulates them, each moved onto the
        quadric; and the root mean square of the points' heights from it, in mm. A concave
        end-plate, a paraboloid's dip below its rim, is a quadric."""
        pts = np.asarray(points, float)
        if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 6:
            raise ValueError("a quadric needs six or more points in three dimensions")
        plane, _ = Plane.fit(pts)
        e1, e2 = plane.axes()
        d = pts - plane.point
        uv, h = np.stack([d @ e1, d @ e2], axis=1), d @ plane.normal
        s = uv / float(np.abs(uv).max())            # the terms on a unit scale, so their rank reads true
        terms = np.stack([np.ones(len(s)), s[:, 0], s[:, 1], s[:, 0] ** 2, s[:, 0] * s[:, 1], s[:, 1] ** 2], axis=1)
        if np.linalg.matrix_rank(terms) < 6:
            raise ValueError("the points do not fix a quadric: they fall on one conic of their plane")
        fitted = terms @ np.linalg.lstsq(terms, h, rcond=None)[0]
        on = plane.point + uv[:, :1] * e1 + uv[:, 1:] * e2 + fitted[:, None] * plane.normal
        return lifted(on, uv), float(np.sqrt(np.mean((h - fitted) ** 2)))

    def corners(self) -> np.ndarray:
        """Each triangle's three corners in the world, triangles by corners by axes."""
        return self.vertices[self.triangles]

    def area(self) -> float:
        """The area in mm2, its triangles' summed."""
        c = self.corners()
        return 0.5 * float(np.linalg.norm(np.cross(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]), axis=1).sum())

    def rims(self) -> List[Curve]:
        """The edges only one triangle has, joined end to end into closed curves: one for a
        surface like a disc, one more for each hole; each runs the way the triangle of its first
        edge turns."""
        tri = self.triangles
        edges = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
        key = edges.min(axis=1) * len(self.vertices) + edges.max(axis=1)
        _, which, count = np.unique(key, return_inverse=True, return_counts=True)
        lone = edges[count[which] == 1]
        if not len(lone):
            raise ValueError("a closed surface has no rim")
        ends: dict = {}
        for a, b in lone.tolist():
            ends.setdefault(a, []).append(b)
            ends.setdefault(b, []).append(a)
        if any(len(n) != 2 for n in ends.values()):
            raise ValueError("the surface's rim meets itself at a vertex")
        loops, seen = [], set()
        for a, b in lone.tolist():
            if a in seen:
                continue
            loop, here, last = [a], b, a
            while here != a:
                loop.append(here)
                here, last = next(n for n in ends[here] if n != last), here
            seen.update(loop)
            loops.append(Curve(self.vertices[loop], closed=True))
        return loops

    def sag(self) -> float:
        """How far the surface departs from the plane of its rims, the plane fitted to their
        points: the furthest vertex's distance from it, in mm; none for a flat surface."""
        plane, _ = Plane.fit(np.vstack([c.points for c in self.rims()]))
        return float(np.abs(plane.distance(self.vertices[np.unique(self.triangles)])).max())

    def project(self, camera: Camera) -> Surface2D:
        """The surface on the render: its vertices projected and its triangles kept, since a flat
        triangle of the world is a triangle of the render. A surface reaching behind the source
        has no one picture there and is refused."""
        got = camera.project(self.vertices)
        if not camera.view.orthographic and not bool((got.depth > NEAR).all()):
            raise ValueError("the surface reaches behind the source")
        return Surface2D(got.uv, got.depth, got.in_beam, self.triangles)

    def silhouette(self, camera: Camera) -> np.ndarray:
        """Where the render's rays meet the surface: the pixels whose centres its triangles cover
        on the render."""
        return self.project(camera).silhouette(camera.view.height, camera.view.width)


def lifted(points: np.ndarray, uv: np.ndarray) -> Surface:
    """The surface through the points, triangulated by Delaunay's rule at their places uv in a
    plane, each triangle turning the right-handed way about the plane's normal, and the points no
    triangle takes, such as one falling on another's place, left out."""
    tri = Delaunay(uv).simplices
    c = uv[tri]
    flip = cross2(c[:, 1] - c[:, 0], c[:, 2] - c[:, 0]) < 0
    tri[flip] = tri[flip][:, [0, 2, 1]]
    used, tri = np.unique(tri, return_inverse=True)
    return Surface(points[used], tri.reshape(-1, 3))


def refined_grid(at: Callable[[np.ndarray, np.ndarray], np.ndarray], half_a: float, half_b: float,
                 tolerance: float) -> np.ndarray:
    """A surface's points on a grid over u from -half_a to half_a and v from -half_b to half_b,
    four cells each way to start; a way's cells doubled where the middle of an edge along it lies
    further than the tolerance from its chord's middle, and both ways' where only a diagonal's
    does, until none does."""
    ka = kb = 4
    while True:
        u, v = np.linspace(-half_a, half_a, 2 * ka + 1), np.linspace(-half_b, half_b, 2 * kb + 1)
        fine = at(*np.meshgrid(u, v, indexing="ij"))
        if not np.isfinite(fine).all():
            raise ValueError("a surface's heights are finite")
        coarse = fine[::2, ::2]
        along_u = far_from_chords(fine[1::2, ::2], coarse[:-1], coarse[1:])
        along_v = far_from_chords(fine[::2, 1::2], coarse[:, :-1], coarse[:, 1:])
        diagonal = far_from_chords(fine[1::2, 1::2], coarse[:-1, :-1], coarse[1:, 1:])
        if max(along_u, along_v, diagonal) <= tolerance or ka * kb >= MOST_SAMPLES:
            return coarse
        grow_u, grow_v = along_u > tolerance, along_v > tolerance
        if not (grow_u or grow_v):
            grow_u = grow_v = True
        ka, kb = ka * (2 if grow_u else 1), kb * (2 if grow_v else 1)


def far_from_chords(middles: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(middles - 0.5 * (a + b), axis=-1).max())


# ---- volumes --------------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Volume:
    """A set of voxels on a grid: mask[i, j, k] on the voxel whose centre the affine puts in the
    world."""
    mask: np.ndarray
    affine: np.ndarray

    def __post_init__(self):
        object.__setattr__(self, "mask", np.asarray(self.mask, bool))
        object.__setattr__(self, "affine", np.asarray(self.affine, float))
        if self.mask.ndim != 3 or self.affine.shape != (4, 4):
            raise ValueError("a volume is a three-dimensional mask and its four by four affine")
        if not self.mask.any():
            raise ValueError("a volume of no voxels")

    @classmethod
    def from_labels(cls, labels: np.ndarray, affine: np.ndarray, value, largest: bool = True) -> "Volume":
        """The voxels of one label value, or of any of several, their largest face-connected piece
        alone where `largest`."""
        mask = np.isin(np.asarray(labels), np.atleast_1d(value))
        if largest and mask.any():
            parts, n = ndimage.label(mask)
            if n > 1:
                sizes = np.bincount(parts.ravel())
                sizes[0] = 0
                mask = parts == int(np.argmax(sizes))
        return cls(mask, affine)

    @property
    def spacing(self) -> np.ndarray:
        return np.linalg.norm(self.affine[:3, :3], axis=0)

    def points(self) -> np.ndarray:
        idx = np.argwhere(self.mask).astype(float)
        return idx @ self.affine[:3, :3].T + self.affine[:3, 3]

    def centroid(self) -> np.ndarray:
        return self.points().mean(axis=0)

    def volume_mm3(self) -> float:
        return float(self.mask.sum()) * abs(float(np.linalg.det(self.affine[:3, :3])))

    def box(self) -> Tuple[np.ndarray, np.ndarray]:
        """The voxel box the volume fills, from the low faces of its lowest voxels to the high faces
        of its highest, in voxel coordinates."""
        idx = np.argwhere(self.mask)
        return idx.min(axis=0) - 0.5, idx.max(axis=0) + 0.5

    def corners(self) -> np.ndarray:
        """The box's eight corners in the world."""
        lo, hi = self.box()
        c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        return c @ self.affine[:3, :3].T + self.affine[:3, 3]

    def footprint(self, camera: Camera) -> np.ndarray:
        """The pixels (row, column) whose rays can meet the volume: the bounding rectangle of the box's
        projected corners, on the detector."""
        got = camera.project(self.corners())
        if not camera.view.orthographic and not bool((got.depth > 0).all()):
            raise ValueError("the volume reaches behind the source")
        c0, r0 = np.floor(got.uv.min(axis=0)).astype(int)
        c1, r1 = np.ceil(got.uv.max(axis=0)).astype(int)
        rows = np.arange(max(r0, 0), min(r1, camera.view.height))
        cols = np.arange(max(c0, 0), min(c1, camera.view.width))
        r, c = np.meshgrid(rows, cols, indexing="ij")
        return np.stack([r.ravel(), c.ravel()], axis=1)

    def path_length(self, camera: Camera, step: Optional[float] = None, n_samples: Optional[int] = None,
                    chunk: int = 4096) -> np.ndarray:
        """The length in mm each of the render's rays runs through the volume, an image of the
        detector's size: by the fine sampling, at most `step` mm apart (half the smallest voxel
        spacing unless given) through the volume's box, or, with n_samples, by FleXray's sampling of
        the whole ray from the source to the detector."""
        if n_samples is not None and n_samples < 2:
            raise ValueError("FleXray samples a ray at two points or more")
        out = np.zeros((camera.view.height, camera.view.width))
        pix = self.footprint(camera)
        to_voxel = np.linalg.inv(self.affine)
        lo, hi = self.box()
        for i in range(0, len(pix), chunk):
            part = pix[i:i + chunk]
            src, tgt = camera.rays(part[:, ::-1] + 0.5)
            a = src @ to_voxel[:3, :3].T + to_voxel[:3, 3]
            b = tgt @ to_voxel[:3, :3].T + to_voxel[:3, 3]
            length = np.linalg.norm(tgt - src, axis=1)
            if n_samples is not None:
                got = self.flexray_samples(a, b, length, int(n_samples), lo, hi)
            else:
                got = self.fine_samples(a, b, length, lo, hi, step or 0.5 * float(self.spacing.min()))
            out[part[:, 0], part[:, 1]] = got
        return out

    def silhouette(self, camera: Camera, **kwargs) -> np.ndarray:
        """Where the render's rays meet the volume."""
        return self.path_length(camera, **kwargs) > 0

    def inside(self, ijk: np.ndarray) -> np.ndarray:
        """Whether each voxel coordinate's nearest voxel is the volume's, rounding half to even as
        grid_sample's nearest mode does; a place off the grid is not."""
        idx = np.rint(ijk).astype(np.int64)
        shape = np.array(self.mask.shape)
        ok = np.all((idx >= 0) & (idx < shape), axis=-1)
        hit = np.zeros(idx.shape[:-1], bool)
        hit[ok] = self.mask[idx[ok][:, 0], idx[ok][:, 1], idx[ok][:, 2]]
        return hit

    def flexray_samples(self, a: np.ndarray, b: np.ndarray, length: np.ndarray, n: int, lo: np.ndarray,
                        hi: np.ndarray) -> np.ndarray:
        """nanoDRR's sampling: n points from the source to the detector at t = k / (n - 1), the
        step the ray's length over n - 1, each point weighing one step where its nearest voxel is
        the volume's. Only the points within a step of the volume's box are read, since no other
        point's nearest voxel can be the volume's."""
        t0, t1 = slab(a, b, lo, hi)
        k0 = np.clip(np.floor(t0 * (n - 1)).astype(np.int64) - 1, 0, n - 1)
        k1 = np.clip(np.ceil(t1 * (n - 1)).astype(np.int64) + 1, 0, n - 1)
        width = int((k1 - k0).max(initial=-1)) + 1
        hits = np.zeros(len(a))
        for j in range(0, max(width, 0), 256):
            ks = k0[:, None] + np.arange(j, min(width, j + 256))[None, :]
            valid = ks <= k1[:, None]
            t = ks / float(n - 1)
            pts = a[:, None, :] + t[:, :, None] * (b - a)[:, None, :]
            hits += (self.inside(pts) & valid).sum(axis=1)
        return hits * length / (n - 1)

    def fine_samples(self, a: np.ndarray, b: np.ndarray, length: np.ndarray, lo: np.ndarray, hi: np.ndarray,
                     step: float) -> np.ndarray:
        """The chord through the volume's box, sampled at the midpoints of steps at most `step` mm
        long, each step counted where its midpoint's nearest voxel is the volume's."""
        t0, t1 = slab(a, b, lo, hi)
        span = np.clip(t1 - t0, 0.0, None) * length
        n = int(math.ceil(float(span.max(initial=0.0)) / step)) if span.size else 0
        if n == 0:
            return np.zeros(len(a))
        hits = np.zeros(len(a))
        for k in range(0, n, 256):
            s = (np.arange(k, min(n, k + 256)) + 0.5) / n
            tk = t0[:, None] + s[None, :] * (t1 - t0)[:, None]
            pts = a[:, None, :] + tk[:, :, None] * (b - a)[:, None, :]
            hits += self.inside(pts).sum(axis=1)
        return hits * span / n


def slab(a: np.ndarray, b: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Where each segment from a to b enters and leaves the box from lo to hi, as fractions of the
    segment, by the slab method; an entry after the exit means it misses."""
    d = b - a
    parallel = d == 0
    with np.errstate(divide="ignore", invalid="ignore"):
        ta, tb = (lo - a) / d, (hi - a) / d
    near = np.where(parallel, -np.inf, np.minimum(ta, tb))
    far = np.where(parallel, np.inf, np.maximum(ta, tb))
    outside = parallel & ((a < lo) | (a > hi))
    t0 = np.clip(near.max(axis=1), 0.0, 1.0)
    t1 = np.clip(far.min(axis=1), 0.0, 1.0)
    t1 = np.where(outside.any(axis=1), t0 - 1.0, t1)
    return t0, t1


def project_points(points, camera: Camera) -> Projected:
    """Points of any number onto the render, as projection.Camera.project."""
    return camera.project(np.atleast_2d(np.asarray(points, float)))
