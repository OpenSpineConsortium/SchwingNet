"""One vertebra's parts in its own frame, read from a whole-vertebra label.

The frame's z starts on the column's line at the vertebra, through the centroids of the
neighbours the volume holds whole (measure.column_line), and is then turned once onto the
vertebra's own axis (own_axis), since the column's line is the axis of the column at the
vertebra and not of the vertebra: in a lordotic neck and at L5 the two lie 9 to 18 degrees
apart. The axis is the bisector of the two end-plates' planes, each plate the body's face
toward the neighbouring vertebra (plate_face, body_axis), a reading that needs no frame; how
far it lies from the column's line is written as axis_offset, and how far the bisector of the
plates as the frame's cells read them lies from z as plate_offset. The thinnest direction
scanimport.geometry's refine_axis searches for was set aside, since on real masks it turned
cervical and lower lumbar levels 20 to 30 degrees and lost their canals, and so was every
reading taken inside the frame (body_axis). y starts toward the
scanner's anterior, is turned toward the side of the canal where the body is (toward_body) and
then settled about z toward the body's centre (settle); x is to the patient's right. The canal
is the hole that the arch closes round in slabs across the column (scanimport.geometry.holes),
the body the largest connected part in front of the canal's anterior wall, cut at the foramina
in the neck (clip_to_foramina), and a body whose right and left halves sit at different heights
flags the whole vertebra, since the label then holds part of a neighbour (halves_apart). Every
extractor in this package starts from this reading, so it is made once here; Panjabi's chords
that scanimport takes are read in the same frame, so a row written here carries them beside the
new measures.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy import ndimage

from scanimport import geometry as G

NAN = float("nan")
SETTLE_TURNS = 4
SETTLED_DEG = 0.5
SPLIT_SHARE = 0.3
FORAMEN_AREA_MM2 = (8.0, 150.0)
FORAMEN_BEHIND_MM = 8.0
STRIP_MIN_MM = 8.0
WALL_SPAN_MM = 6.0
WALL_PAIR_MM = 4.0
WALL_SLOPE_MAX = math.tan(math.radians(30.0))
AXIS_TURN_MAX_DEG = 25.0
PLATE_FACE_MM = 15.0
PLATE_FACING_DEG = 45.0
PLATE_SMOOTH_MM = 1.5
MIN_PLATE_POINTS = 30


@dataclass
class CanalSlab:
    """One slab across the column where the arch closes round the canal: its height along z,
    the canal's width through its middle and depth at its midline, the anterior and posterior
    walls at the midline, the midline's x, the hole's area, and the hole's pixel centres."""
    z: float
    width: float
    ap: float
    anterior: float
    posterior: float
    midline: float
    area: float
    hole: np.ndarray


@dataclass
class Vertebra:
    level: str
    grid: G.VoxelGrid
    idx: np.ndarray
    loc: np.ndarray
    frame: G.Frame
    touching: np.ndarray
    body: np.ndarray
    slabs: List[CanalSlab]
    wall: float
    wall_post: float
    midline: float
    panjabi: Dict[str, float]
    flags: Dict[str, str] = field(default_factory=dict)
    wall_slope: float = 0.0
    wall_z0: float = 0.0
    wall_y0: float = 0.0
    column_ez: Optional[np.ndarray] = None
    axis_turn: float = 0.0
    axis_residual: float = NAN

    @property
    def fx(self) -> float:
        return self.grid.footprint(self.frame.ex)

    @property
    def fy(self) -> float:
        return self.grid.footprint(self.frame.ey)

    @property
    def fz(self) -> float:
        return self.grid.footprint(self.frame.ez)

    @property
    def pixel(self) -> float:
        return max(self.fx, self.fy)

    @property
    def voxel_volume(self) -> float:
        return float(abs(np.linalg.det(np.asarray(self.grid.affine, float)[:3, :3])))

    def footprint(self, d_local: np.ndarray) -> float:
        """One voxel's shadow on a direction given in the frame."""
        return self.grid.footprint(self.to_world(d_local))

    def to_world(self, d_local: np.ndarray) -> np.ndarray:
        f = self.frame
        return d_local[0] * f.ex + d_local[1] * f.ey + d_local[2] * f.ez

    def points_world(self, local: np.ndarray) -> np.ndarray:
        f = self.frame
        return f.origin + local[:, :1] * f.ex + local[:, 1:2] * f.ey + local[:, 2:3] * f.ez

    @property
    def body_pts(self) -> np.ndarray:
        return self.loc[self.body]

    def mask_box(self):
        """The vertebra as a boolean box over its voxels, and the box's corner index."""
        if getattr(self, "_box", None) is None:
            lo = self.idx.min(0)
            box = np.zeros(tuple(self.idx.max(0) - lo + 1), bool)
            box[tuple((self.idx - lo).T)] = True
            self._box = (box, lo)
        return self._box

    def is_bone(self, ijk: np.ndarray) -> np.ndarray:
        """Whether each voxel index (N, 3) is one of the vertebra's."""
        box, lo = self.mask_box()
        rel = ijk - lo
        ok = ((rel >= 0) & (rel < np.array(box.shape))).all(1)
        out = np.zeros(len(ijk), bool)
        out[ok] = box[tuple(rel[ok].T)]
        return out

    def full_rings(self) -> List[CanalSlab]:
        """The slabs whose hole is at least half the median hole: where the arch closes fully,
        not the first or last slab of the ring, which a slab cuts at a slant."""
        if not self.slabs:
            return []
        med = float(np.median([s.area for s in self.slabs]))
        return [s for s in self.slabs if s.area >= 0.5 * med]


def build(level: str, idx: np.ndarray, grid: G.VoxelGrid, ez: np.ndarray, touching: np.ndarray,
          neighbours: Optional[Dict[str, np.ndarray]] = None) -> Vertebra:
    """The vertebra in its own frame, with its canal slabs and its body; flags say what failed.

    The frame's z starts on the column's line through the neighbours (ez) and is turned once onto
    the vertebra's own axis (own_axis), read from its end-plates' faces toward the neighbours
    given, the voxel indices of the labels above and below (measure.neighbours_of); with none
    the column's line is kept and flagged. y is turned from the canal toward the body (settle).
    Panjabi's chords are read by scanimport.geometry.chords_from in that frame, so they and the
    measures here share one axis."""
    pts = grid.world(idx.astype(float))
    v = Vertebra(level, grid, idx, np.zeros((len(idx), 3)), G.frame_from(pts.mean(0), ez, grid.anterior()),
                 touching, np.zeros(len(idx), bool), [], NAN, NAN, NAN, {}, {})
    first = toward_body(v, v.frame)
    if first is None:
        v.loc = v.frame.local(pts)
        v.flags["all"] = "no canal: the arch never closes round a hole in any slab across the column's line"
        v.panjabi = {k: NAN for k in PANJABI_KEYS}
        return v
    read_in(v, first)
    if "all" not in v.flags:
        settle(v)
    if "all" not in v.flags:
        own_axis(v, neighbours or {})
    if "all" in v.flags:
        return v
    secs = G.sections(v.loc, v.fz, v.pixel, as_hole=True)
    got = G.chords_from(v.loc, idx, grid, v.frame, secs, touching, {})
    v.panjabi = dict(got.values)
    for k, note in got.flags.items():
        v.flags.setdefault("panjabi_" + k, note)
    panjabi_body(v)
    return v


def panjabi_body(v: Vertebra) -> None:
    """Panjabi's five body chords read again on this module's body, with the wall along its line.
    scanimport's chords_from cuts its own body at one plane through the canal's median wall, as
    refine_axis's frame allowed; in the column line's frame that plane lies off the wall where
    the vertebra leans against the line, and it never sees a cervical body's clip at the
    foramina."""
    if v.touching[v.body].any() or v.body.sum() < G.MIN_BODY_VOXELS:
        return
    got = G.body_chords(square_to_wall(v, v.body_pts), v.wall_y0, v.grid, v.frame)
    v.panjabi.update({k: got[k] for k in ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth",
                                          "h_post")})


PANJABI_KEYS = ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post", "canal_w",
                "canal_ap", "tp_span", "spinous_length")


def toward_body(v: Vertebra, frame: G.Frame) -> Optional[G.Frame]:
    """The frame turned about its z so that y points from the canal to the body; None where no
    slab holds a canal.

    The body is told from the arch by what lies in front of and behind the canal within its own
    width: in front the body fills that strip from end-plate to end-plate, behind it the
    laminae and the spinous process only. measure_whole counts everything beyond the canal on
    each side, where the transverse processes, the facets and a long spinous process can
    outweigh a small body: on the phantom with a waisted, wedged body with concave end-plates,
    a 32 degree spinous process and 55 degree facets the arch's side held more voxels and the
    frame came out facing backwards. The canal's walls and centre are the medians over the slabs
    that hold one, as measure_whole's later turns take them, since the slab with the largest
    hole can be one where the arch closes round something else."""
    loc = frame.local(v.grid.world(v.idx.astype(float)))
    fz = v.grid.footprint(frame.ez)
    pixel = max(v.grid.footprint(frame.ex), v.grid.footprint(frame.ey))
    found = [s for s in G.sections(loc, fz, pixel, as_hole=True) if s.canal is not None]
    if not found:
        return None
    cc = np.median([s.canal.mean(0) for s in found], axis=0)
    front_wall = float(np.median([s.canal[:, 1].max() for s in found]))
    back_wall = float(np.median([s.canal[:, 1].min() for s in found]))
    half = max(0.5 * float(np.median([np.ptp(s.canal[:, 0]) for s in found])), STRIP_MIN_MM)
    strip = np.abs(loc[:, 0] - cc[0]) <= half
    front = loc[strip & (loc[:, 1] > front_wall)]
    back = loc[strip & (loc[:, 1] < back_wall)]
    side = front if len(front) >= len(back) else back
    if len(side) < G.MIN_BODY_VOXELS:
        return frame
    return frame.turned_toward(side[:, :2].mean(0) - cc)


def read_in(v: Vertebra, frame: G.Frame) -> None:
    """The voxels, the canal's slabs and walls, and the body, read in the given frame."""
    v.frame = frame
    v.loc = frame.local(v.grid.world(v.idx.astype(float)))
    v.slabs = []
    for k in ("all", "body_foramina"):
        v.flags.pop(k, None)
    for s in G.sections(v.loc, v.fz, v.pixel, as_hole=True):
        if s.canal is None:
            continue
        walls = G.canal_walls(s, v.pixel, v.fx, v.fy)
        if walls is None:
            continue
        w, ap, wa, wp, xm, z = walls
        v.slabs.append(CanalSlab(z, w, ap, wa, wp, xm, s.area, s.canal))
    if not v.slabs:
        v.flags["all"] = "no slab with a wall round the canal"
        return
    rings = v.full_rings()
    v.wall = float(np.median([s.anterior for s in rings]))
    v.wall_post = float(np.median([s.posterior for s in rings]))
    v.midline = float(np.median([s.midline for s in rings]))
    v.body = body_in_front(v)
    if v.level.startswith("C"):
        clip_to_foramina(v)
    if v.body.sum() < G.MIN_BODY_VOXELS:
        v.flags["all"] = "too few voxels in front of the canal for a body"
        return
    split = halves_apart(v.body_pts)
    if split is not None:
        v.flags["all"] = split


def wall_slope(z: np.ndarray, y: np.ndarray) -> float:
    """How far the canal's anterior wall moves forward per millimetre up the frame's z, the
    median of the slopes between pairs of slabs at least WALL_PAIR_MM apart (Theil and Sen), so
    that one slab's misread wall does not tilt it; nought where the slabs span too little, or
    where the slope is steeper than WALL_SLOPE_MAX, a wall leaning 30 degrees off the column's
    line, which no vertebra's wall does and a misread set of slabs can."""
    if len(z) < 3 or z.max() - z.min() < WALL_SPAN_MM:
        return 0.0
    i, j = np.triu_indices(len(z), 1)
    far = np.abs(z[j] - z[i]) >= WALL_PAIR_MM
    if far.sum() < 3:
        return 0.0
    slope = float(np.median((y[j] - y[i])[far] / (z[j] - z[i])[far]))
    return slope if abs(slope) <= WALL_SLOPE_MAX else 0.0


def body_in_front(v: Vertebra) -> np.ndarray:
    """The body: what lies in front of the canal's anterior wall, the wall a line along z
    through the slabs and not a plane square to the frame's y. The frame's z is the column's
    line, which a slipped or unevenly bent neighbour tilts against the vertebra's own axis, by 8
    degrees at the joint phantom's L3; a plane through the wall's median then cut 1.7 mm off the
    posterior wall at the top of the body and left the slip read 2.0 mm where it is 4.2. Only
    the full rings give the line: at study 0004's T6 two slabs at the top of the ring held
    small holes 20 mm in front of the canal's wall, inside the body, and with them the line
    leaned 69 degrees and cut the back third off the body."""
    rings = v.full_rings()
    z = np.array([s.z for s in rings])
    y = np.array([s.anterior for s in rings])
    v.wall_slope = wall_slope(z, y)
    v.wall_z0 = z0 = float(np.median(z))
    v.wall_y0 = float(np.median(y - v.wall_slope * (z - z0)))
    return G.connected_front(v.idx, square_to_wall(v, v.loc), v.wall_y0, v.grid.shape)


def square_to_wall(v: Vertebra, P: np.ndarray) -> np.ndarray:
    """Points in v's frame with y measured from the canal's wall line (body_in_front), so the
    wall is the plane y = v.wall_y0 whatever the line's lean."""
    out = P.copy()
    out[:, 1] -= v.wall_slope * (P[:, 2] - v.wall_z0)
    return out


def clip_to_foramina(v: Vertebra) -> None:
    """A cervical body without its transverse processes.

    From C2 to C7 the transverse process springs from the side of the body and the pedicle and
    is pierced by the foramen transversarium, so what lies in front of the canal's wall holds
    the body and both processes, and its width is the processes' span (46 mm at study 0004's C6
    against a body of about 20 mm). Each foramen is a hole in the slabs beside the canal; the
    body is what lies between the two foramina's medial edges, each the median over the slabs
    that show it. The masks often leave a foramen open at its front, as at study 0004's C6, and
    where a side shows none closed the body is cut a millimetre beyond the canal's side walls,
    since a cervical body (15 to 21 mm wide at its end-plates, Panjabi 1991) is narrower than
    its canal (about 24 mm) and the processes' roots lie beside the pedicles."""
    edges = {1.0: [], -1.0: []}
    for s in v.slabs:
        sel = np.abs(v.loc[:, 2] - s.z) <= 0.5 * v.fz
        xy = v.loc[sel, :2]
        grid, origin = G.raster(xy, v.pixel)
        lab, n = ndimage.label(G.holes(grid))
        for k in range(1, n + 1):
            ij = np.argwhere(lab == k)
            pts = origin + (ij + 0.5) * v.pixel
            area = len(ij) * v.pixel ** 2
            c = pts.mean(0)
            off = c[0] - s.midline
            if not (FORAMEN_AREA_MM2[0] <= area <= FORAMEN_AREA_MM2[1]) or abs(off) < 0.5 * s.width:
                continue
            if c[1] < v.wall - FORAMEN_BEHIND_MM:
                continue
            side = 1.0 if off > 0 else -1.0
            edges[side].append(float(pts[:, 0].min() if side > 0 else pts[:, 0].max()))
    half = 0.5 * float(np.median([s.width for s in v.full_rings()])) + 1.0
    if edges[1.0] and edges[-1.0]:
        right, left = float(np.median(edges[1.0])), float(np.median(edges[-1.0]))
    else:
        right, left = v.midline + half, v.midline - half
        v.flags["body_foramina"] = ("a foramen transversarium was not found closed: the body is cut at the canal's "
                                    "side walls and a millimetre beyond")
    inside = (v.loc[:, 0] < right) & (v.loc[:, 0] > left)
    v.body = v.body & inside


def halves_apart(B: np.ndarray) -> Optional[str]:
    """A note where the body's right and left halves sit at heights further apart than
    SPLIT_SHARE of its height, which no vertebra shows and a label that took half of a
    neighbour's body does: study 0004's T4 holds its own left half and its neighbour's right
    half, 15 mm higher, joined by a bridge a few voxels thick."""
    xc = float(np.median(B[:, 0]))
    right, left = B[B[:, 0] > xc + 2.0, 2], B[B[:, 0] < xc - 2.0, 2]
    if len(right) < G.MIN_BODY_VOXELS or len(left) < G.MIN_BODY_VOXELS:
        return None
    height = float(np.percentile(B[:, 2], 98) - np.percentile(B[:, 2], 2))
    apart = abs(float(np.median(right) - np.median(left)))
    if apart > SPLIT_SHARE * height:
        return "the body's halves sit %.1f mm apart in height: the label holds part of a neighbour" % apart
    return None


def plate_axis(v: Vertebra) -> Optional[np.ndarray]:
    """The direction half-way between the two end-plates' normals, in the world: each plate the
    robust plane through the extreme points of the cells of the plate's central part
    (body.plate_core)."""
    from . import body as BODY
    normals = []
    for top in (True, False):
        ext = BODY.plate_points(v.body_pts, v.pixel, top)
        if len(ext) < 6:
            return None
        c = BODY.plane_robust(ext, v.fz)
        n = np.array([-c[1], -c[2], 1.0])
        normals.append(n / np.linalg.norm(n))
    return G.unit(v.to_world(G.unit(normals[0] + normals[1])))


def settle(v: Vertebra) -> None:
    """Turn the frame about its z toward the body's centre until the turn is under SETTLED_DEG.

    The frame's z stays where it is, on the column's line through the neighbours' centroids or,
    after own_axis, on the vertebra's own axis. Two other axes were tried on the masks and set
    aside. scanimport.geometry.refine_axis, the direction along
    which the body's core is thinnest, is drawn to the slices' normal, along which the voxel
    centres of a plate all sit on one layer: at study 0001 (0.86 by 0.86 by 2.5 mm) it set
    T11's axis on the scan's z, 20 degrees from the line through its neighbours, so T10 on T11
    read a slip of 24 mm, and at study 0004 (1 mm slices) it turned C4, C5, C7 and L5 by 23 to
    30 degrees, after which no slab closed round the canal. The bisector of the two end-plates'
    planes is read on cells whose extremes step from layer to layer, a sawtooth whose period a
    17 mm core does not hold whole, and on the phantom with 2.5 mm slices and a 20 degree tilt it
    put the axis 1.1 degrees off, which raised the anterior height by 2 mm and lowered the disc
    by 2 mm against the column's line, which was exact there. A centroid is the mean of thousands
    of voxels and the line through two of them carries no such step. Its cost is at a junction
    or a wedged level, where the body's own axis leaves the line through its neighbours, which
    is why own_axis then turns z onto the vertebra's own axis, read from the plates' faces
    toward the neighbours without the frame (body_axis), and the bisector the cells give is
    written beside it as plate_offset."""
    for _ in range(SETTLE_TURNS):
        B = v.body_pts
        if not len(B):
            return
        d = np.array([np.median(B[:, 0]) - v.midline, np.median(B[:, 1]) - v.wall])
        if abs(math.degrees(math.atan2(d[0], d[1]))) < SETTLED_DEG:
            return
        keep = v.frame
        read_in(v, v.frame.turned_toward(d))
        if "all" in v.flags:
            read_in(v, keep)
            v.flags["axis_turn"] = "turning toward the body loses the canal: the turn is not taken"
            return


def angle_deg(a: np.ndarray, b: np.ndarray) -> float:
    """Degrees between two directions, either way round."""
    return math.degrees(math.acos(min(1.0, abs(float(np.dot(a, b))))))


def plate_offset(v: Vertebra) -> float:
    """Degrees between the frame's z and the bisector of the end-plates' planes as the frame's
    cells read them (plate_axis), a reading that moves with the frame and is written only to be
    seen beside the axis the faces give."""
    ez = plate_axis(v)
    return NAN if ez is None else angle_deg(ez, v.frame.ez)


def axis_offset(v: Vertebra) -> float:
    """Degrees between the frame's z, the vertebra's own axis, and the column's line through
    the neighbours: how far the vertebra leans against its column; nought where the column's
    line was kept (own_axis)."""
    return v.axis_turn


def plate_face(v: Vertebra, other: np.ndarray) -> Optional[np.ndarray]:
    """The body's face toward a neighbouring vertebra, as world points: the body's voxels on
    the vertebra's surface that lie within PLATE_FACE_MM of the neighbour's label (other, its
    voxel indices) and whose outward normal, the smoothed label's gradient, points within
    PLATE_FACING_DEG of the neighbour's nearest voxel. The anterior and lateral walls face
    sideways to the neighbour and are left out by the angle, the facets lie behind the canal's
    wall and are no body, and the surface is the whole label's, so the cut that made the body
    (body_in_front, clip_to_foramina) adds no face of its own. Nothing here is read along the
    frame, so the face is the same whichever frame the vertebra stands in, which is what a
    reading of the axis needs (body_axis). None where fewer than MIN_PLATE_POINTS voxels
    qualify."""
    body = v.idx[v.body]
    if not len(body) or not len(other):
        return None
    margin = np.ceil(PLATE_FACE_MM / v.grid.spacing).astype(int) + 2
    lo = np.maximum(body.min(0) - margin, 0)
    hi = body.max(0) + margin + 1
    shape = tuple(int(n) for n in hi - lo)

    def box_of(idx: np.ndarray) -> np.ndarray:
        keep = ((idx >= lo) & (idx < hi)).all(1)
        box = np.zeros(shape, bool)
        box[tuple((idx[keep] - lo).T)] = True
        return box

    mine, theirs, is_body = box_of(v.idx), box_of(other), box_of(body)
    if not theirs.any():
        return None
    surface = mine & ~ndimage.binary_erosion(mine)
    dist, near = ndimage.distance_transform_edt(~theirs, sampling=v.grid.spacing, return_indices=True)
    cand = np.argwhere(surface & is_body & (dist <= PLATE_FACE_MM))
    if len(cand) < MIN_PLATE_POINTS:
        return None
    smooth = ndimage.gaussian_filter(mine.astype(float), PLATE_SMOOTH_MM / v.grid.spacing)
    at = tuple(cand.T)
    slopes = np.stack([g[at] for g in np.gradient(smooth, *v.grid.spacing)], axis=1)
    normal = -(slopes @ v.grid.axes.T)
    toward = (np.stack([near[k][at] for k in range(3)], axis=1) - cand) @ np.asarray(v.grid.affine, float)[:3, :3].T
    size = np.linalg.norm(normal, axis=1) * np.linalg.norm(toward, axis=1)
    ok = size > 0
    cosine = np.einsum("ij,ij->i", normal[ok], toward[ok]) / size[ok]
    face = cand[ok][cosine >= math.cos(math.radians(PLATE_FACING_DEG))]
    if len(face) < MIN_PLATE_POINTS:
        return None
    return v.grid.world((face + lo).astype(float))


def face_normal(pts: np.ndarray, layer: float) -> Optional[np.ndarray]:
    """The unit normal of the plane through a face's points, the direction of their least
    spread, fitted again without the points more than two layers off the plane, as
    body.plane_robust refits a plate; None where the refit leaves too few."""
    n = None
    for _ in range(3):
        c = pts.mean(0)
        n = np.linalg.eigh(np.cov((pts - c).T))[1][:, 0]
        keep = np.abs((pts - c) @ n) <= 2.0 * layer
        if keep.all():
            break
        if keep.sum() < MIN_PLATE_POINTS:
            return None
        pts = pts[keep]
    return n


def body_axis(v: Vertebra, neighbours: Dict[str, np.ndarray]) -> Optional[np.ndarray]:
    """The vertebra's own axis in the world: the bisector of its two end-plates' planes, each
    plate the body's face toward the neighbour above or below (plate_face) and its plane the
    face's least spread (face_normal), both normals taken upward along the frame's z and
    summed; where one plate alone faces a neighbour, at the top or
    the bottom of the field, that plate's normal, which lies half the body's wedge off the
    bisector and is flagged. None where neither can be read.

    Every reading taken inside the frame was tried on study 0004 and set aside, since each
    moved with the frame it was read in: with the body's voxels fixed and the frame turned 20
    degrees, the bisector of the plates as the frame's cells read them (plate_axis) moved 4 to
    19 degrees, a line through the layers' centroids 17 to 47, one through their posterior tenth
    21 to 78, and the canal's axis through the slabs' holes stood on fewer than four full rings
    at many thoracic levels. A face read by distance and surface normal needs no frame, so the
    axis reads the same before and after the turn onto it (own_axis writes the residual)."""
    normals = []
    for side in ("above", "below"):
        other = neighbours.get(side)
        pts = plate_face(v, other) if other is not None else None
        n = face_normal(pts, v.fz) if pts is not None else None
        if n is None:
            continue
        normals.append(n if float(n @ v.frame.ez) >= 0 else -n)
    if not normals:
        return None
    if len(normals) == 1:
        v.flags["axis_one_plate"] = ("one end-plate alone faces a neighbour: the axis is that plate's normal, half "
                                     "the body's wedge off the bisector")
    return G.unit(np.sum(normals, axis=0))


def own_axis(v: Vertebra, neighbours: Dict[str, np.ndarray]) -> None:
    """Turn the frame's z from the column's line onto the vertebra's own axis (body_axis), once,
    and read the vertebra again there.

    The column's line through the neighbours' centroids is the axis of the column at the
    vertebra, not of the vertebra: in a lordotic neck and at L5, where the body leans against
    the line through its neighbours, the two lay 9 to 18 degrees apart over the 228 thin-slice
    studies of ENHANCE.PET (medians of C3 16.7, C5 8.9, L5 18.1), and an axial cut square to the
    column's line ran obliquely through the body, which the owner saw at study 0004's C5 on 29
    October 2026. The turn is taken once, since the axis is read without the frame; the axis
    read again in the turned frame, whose body is cut anew, lies within a degree or two of z,
    and that residual is written as axis_residual. The turn is not taken, and the column's line
    kept with a flag, where no end-plate faces a neighbour, where the axis lies more than
    AXIS_TURN_MAX_DEG off the column's line, further than a vertebra leans against its
    neighbours and as far as a misread body does, or where the turned frame loses the canal."""
    v.column_ez = v.frame.ez.copy()
    v.flags.pop("axis_one_plate", None)
    axis = body_axis(v, neighbours)
    if axis is None:
        v.flags["axis"] = "no end-plate faces a neighbour the volume holds: the column's line is kept"
        return
    turn = angle_deg(axis, v.frame.ez)
    if turn > AXIS_TURN_MAX_DEG:
        v.flags["axis"] = ("the end-plates' bisector lies %.0f degrees off the column's line, further than a "
                           "vertebra leans: the column's line is kept" % turn)
        return
    if turn >= SETTLED_DEG:
        keep = v.frame
        plain = G.frame_from(v.frame.origin, axis, v.grid.anterior())
        turned = toward_body(v, plain)
        read_in(v, plain if turned is None else turned)
        if "all" in v.flags:
            read_in(v, keep)
            v.flags["axis"] = "turning onto the end-plates' bisector loses the canal: the column's line is kept"
            return
        settle(v)
    v.axis_turn = angle_deg(v.frame.ez, v.column_ez)
    after = body_axis(v, neighbours)
    v.axis_residual = NAN if after is None else angle_deg(after, v.frame.ez)


def usable(v: Optional[Vertebra]) -> bool:
    return v is not None and "all" not in v.flags
