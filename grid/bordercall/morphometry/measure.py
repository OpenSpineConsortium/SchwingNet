"""A labelled CT to rows of morphometrics: every vertebra, every disc, the column and the pelvis.

The label volume is read by scanimport (volume.read_labels), so the schemes, the voxel lists and
the column's axes through the centroids are the ones scanimport's chords use. Each vertebra from
C2 to L6 is built once (anatomy.build) and handed to each family of measures in turn; C1 has no
body and the sacrum is read by the pelvis. Every row names the study, the level (a vertebra, a
disc as "L4-L5", "column" or "pelvis"), the measure, its value, and the reason where the value
could not be taken. Nothing is resampled, reoriented or written back.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import ndimage

from scanimport import LEVELS
from scanimport import geometry as G
from scanimport import volume as V

from . import anatomy as A
from . import body as BODY
from . import canal as CANAL
from . import column as COL
from . import pedicle as PED
from . import pelvis as PELVIS
from . import posterior as POST

NAN = float("nan")
SKIP = ("C1", "sacrum")
PIECE_CELL = 4                 # voxels per side of the coarse cells pieces are told apart on
PIECE_SHARE = 0.05             # a piece under this share of the largest is apart from the vertebra
FRAGMENT_SHARE = 0.2           # a label under this share of the median level is no neighbour to steer by
DENS = ("h_ant", "h_mid", "h_post_inset", "h_post", "body_index_ant_post", "body_index_mid_post", "endplate_incl",
        "wedge", "endplate_concavity", "endplate_area", "endplate", "endplate_depth", "body_w_mid", "body_d_mid",
        "canal_index_torg", "canal_index_jones")
PANJABI = ("endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post", "canal_w", "canal_ap",
           "tp_span", "spinous_length")


def ratio(a: float, b: float) -> float:
    return a / b if np.isfinite(a) and np.isfinite(b) and b > 0 else NAN


def derived(vals: Dict[str, float]) -> Dict[str, float]:
    """Ratios of measures already taken: the canal to the body, as Torg and Pavlov and as Jones
    and Thomson (Eisenstein's credit) set them."""
    return {"canal_index_torg": ratio(vals.get("canal_ap", NAN), vals.get("body_d_mid", NAN)),
            "canal_index_jones": ratio(vals.get("canal_ap_min", NAN) * vals.get("interpedicular_max", NAN),
                                       vals.get("body_d_mid", NAN) * vals.get("body_w_mid", NAN))}


def vertebra_values(v: A.Vertebra) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, dict]]:
    vals = {k: v.panjabi.get(k, NAN) for k in PANJABI}
    vals["axis_offset"] = A.axis_offset(v)
    vals["plate_offset"] = A.plate_offset(v)
    vals["axis_residual"] = v.axis_residual
    flags = dict(v.flags)
    got, f = BODY.measures(v)
    vals.update(got)
    flags.update(f)
    zb = CANAL.body_span(v)
    got, f, ped = PED.measures(v, zb)
    vals.update(got)
    flags.update(f)
    got, f = CANAL.measures(v, PED.band(ped))
    vals.update(got)
    flags.update(f)
    got, f = POST.measures(v)
    vals.update(got)
    flags.update(f)
    if v.touching.any():
        cut_by_the_edge(vals, flags)
    vals.update(derived(vals))
    if v.level == "C2":
        no_dens_plate(vals, flags)
    return vals, flags, ped


def rows_of(study: str, level: str, vals: Dict[str, object], flags: Dict[str, str]) -> List[Dict[str, object]]:
    rows = []
    for k, x in vals.items():
        if isinstance(x, np.ndarray):
            continue
        note = ""
        if isinstance(x, float) and not math.isfinite(x):
            note = flags.get(k, flags.get("all", flags.get("body", "")))
        rows.append({"study": study, "level": level, "key": k, "value": x, "note": note})
    for k, why in flags.items():
        if k not in vals:
            rows.append({"study": study, "level": level, "key": "flag:" + k, "value": "", "note": why})
    return rows


def adjacent(a: str, b: str, present) -> bool:
    """Whether b follows a in the column, T13 counted only where the volume names it: scanimport's
    LEVELS holds T13 between T12 and L1, and with it counted no ENHANCE study, whose scheme has
    no T13, had a T12-L1 disc."""
    seq = [lv for lv in LEVELS if lv != "T13" or "T13" in present]
    return seq.index(b) == seq.index(a) + 1


def neighbours_of(vox: Dict[str, np.ndarray], order: List[str], lv: str) -> Dict[str, np.ndarray]:
    """The labels above and below a level, by their voxel indices, where the volume holds the
    adjacent level: the vertebrae its end-plates face, from which anatomy reads its axis
    (anatomy.plate_face). The lowest lumbar level's lower face is the sacrum's; C2's top is
    the dens and faces no plate, so C2 gets no label above."""
    i = order.index(lv)
    out: Dict[str, np.ndarray] = {}
    if i > 0 and lv != "C2" and adjacent(order[i - 1], lv, vox):
        out["above"] = vox[order[i - 1]]
    if i + 1 < len(order):
        below = order[i + 1]
        if adjacent(lv, below, vox) or (below == "sacrum" and lv.startswith("L")):
            out["below"] = vox[below]
    return out


def main_piece(idx: np.ndarray) -> Tuple[np.ndarray, int]:
    """The label's voxels less the pieces lying apart from the vertebra, and how many were left
    out. A stray island of a label (a bit of the sacral ala labelled L5, a neighbour's spinous tip)
    would set a vertebra's extents and its centroid; pieces are told apart on cells PIECE_CELL
    voxels a side, so the whole box is never labelled at full size."""
    c = idx // PIECE_CELL
    lo = c.min(0)
    box = np.zeros(tuple(c.max(0) - lo + 1), bool)
    box[tuple((c - lo).T)] = True
    lab, n = ndimage.label(box, structure=np.ones((3, 3, 3), bool))
    if n <= 1:
        return idx, 0
    ids = lab[tuple((c - lo).T)]
    counts = np.bincount(ids)
    keep = counts[ids] >= PIECE_SHARE * counts[1:].max()
    return idx[keep], int((~keep).sum())


def whole_levels(vox: Dict[str, np.ndarray], spine: List[str], shape) -> List[bool]:
    """Which levels may steer their neighbours' line: held whole by the volume and not a fragment
    of a label, which a segmenter leaves at a junction."""
    med = float(np.median([len(vox[lv]) for lv in spine])) if spine else 0.0
    return [not V.touching_edge(vox[lv], shape).any() and len(vox[lv]) >= max(G.MIN_BODY_VOXELS, FRAGMENT_SHARE * med)
            for lv in spine]


def cut_by_the_edge(vals: Dict[str, float], flags: Dict[str, str]) -> None:
    """A vertebra the volume's edge cuts keeps no canal, pedicle or posterior reading: the ring,
    the pedicles' run and the processes' apices may all end at the cut and not at bone."""
    for k in list(vals):
        if k.startswith(("canal_", "interpedicular", "pedicle_", "lamina_", "facet_", "interfacet_", "sap_", "iap_")):
            vals[k] = NAN
    flags["cut"] = "the vertebra touches the edge of the volume: its canal, pedicles and posterior elements are not read"


def no_dens_plate(vals: Dict[str, float], flags: Dict[str, str]) -> None:
    """C2's dens stands on its body in front of the canal, so the body's top is the dens's tip:
    no upper end-plate, height or waist is read, only the lower plate C2-C3 needs."""
    for k in DENS:
        if k in vals:
            vals[k] = NAN
    flags["dens"] = "C2: the dens stands on the body, so no upper end-plate, height or waist is read"


def column_line(cents: List[np.ndarray], whole: List[bool], superior: np.ndarray) -> List[np.ndarray]:
    """The column's direction at each vertebra, as scanimport.geometry.column_axes takes it,
    through the neighbours above and below, but only through neighbours the volume holds whole:
    a vertebra the scan's edge cuts has its centroid inside what is left of it, and on the
    phantom a neighbour cut by 30 per cent turned L3's line by 6 degrees and its pedicles'
    transverse angle by 27. The sacrum is left out, its centroid lying far in front of the
    line through the lumbar bodies, so L5's line is the one through L4."""
    out = []
    for i, c in enumerate(cents):
        above = cents[i - 1] if i > 0 and whole[i - 1] else None
        below = cents[i + 1] if i + 1 < len(cents) and whole[i + 1] else None
        if above is not None and below is not None:
            d = above - below
        elif above is not None:
            d = above - c
        elif below is not None:
            d = c - below
        else:
            d = np.asarray(superior, float)
        d = G.unit(d)
        out.append(d if d @ superior >= 0 else -d)
    return out


def measure_volume(vol: np.ndarray, grid: G.VoxelGrid, names: Dict[int, str], study: str,
                   pelvis: bool = True, keep: Optional[dict] = None) -> List[Dict[str, object]]:
    """The study's rows. Where `keep` is given it is filled with what the rows were read from, so
    that the lines of the measures (morphoview.lines) are drawn on the same vertebrae and checked
    against the same values: "verts" and "peds" by level, "values" by level, and "discs", the
    disc's values by its pair of levels."""
    vox = V.vertebra_voxels(vol, names)
    rows: List[Dict[str, object]] = []
    for lv in list(vox):
        vox[lv], apart = main_piece(vox[lv])
        if apart:
            rows.append({"study": study, "level": lv, "key": "flag:pieces", "value": "",
                         "note": "%d voxels in pieces apart from the vertebra were left out" % apart})
    order = [lv for lv in LEVELS if lv in vox]
    spine = [lv for lv in order if lv != "sacrum"]
    cents = [grid.world(vox[lv].astype(float)).mean(0) for lv in spine]
    whole = whole_levels(vox, spine, vol.shape)
    axes = dict(zip(spine, column_line(cents, whole, grid.superior())))
    verts: Dict[str, A.Vertebra] = {}
    peds: Dict[str, Dict[str, dict]] = {}
    depths: Dict[str, float] = {}
    values: Dict[str, Dict[str, float]] = {}
    disc_values: Dict[Tuple[str, str], Dict[str, float]] = {}
    for lv in spine:
        if lv in SKIP:
            continue
        ez = axes[lv]
        idx = vox[lv]
        if len(idx) < G.MIN_BODY_VOXELS:
            rows.append({"study": study, "level": lv, "key": "flag:all", "value": "", "note": "only %d voxels" % len(idx)})
            continue
        v = A.build(lv, idx, grid, ez, V.touching_edge(idx, vol.shape), neighbours_of(vox, order, lv))
        if not A.usable(v):
            rows += rows_of(study, lv, {}, v.flags)
            continue
        vals, flags, ped = vertebra_values(v)
        rows += rows_of(study, lv, vals, flags)
        verts[lv], peds[lv], depths[lv], values[lv] = v, ped, vals.get("endplate_depth", NAN), vals
    measured = [lv for lv in LEVELS if lv in verts]
    for a, b in zip(measured, measured[1:]):
        if adjacent(a, b, vox) and not verts[a].touching[verts[a].body].any() and not verts[b].touching[verts[b].body].any():
            disc_values[(a, b)] = COL.disc(verts[a], verts[b], peds[a], peds[b], depths[b])
            rows += rows_of(study, "%s-%s" % (a, b), disc_values[(a, b)], {})
    if keep is not None:
        keep.update(verts=verts, peds=peds, values=values, discs=disc_values)
    pel: Dict[str, object] = {}
    if pelvis:
        pel, flags = PELVIS.measures(vol, grid, verts, present=vox)
        rows += rows_of(study, "pelvis", pel, flags)
    rows += rows_of(study, "column", COL.regional(verts, pel.get("s1_normal")), {})
    return rows


def measure_file(labels: str, scheme: str, study: str, keep: Optional[dict] = None) -> List[Dict[str, object]]:
    vol, grid, names, problems, _ = V.read_labels(labels, scheme)
    rows = measure_volume(vol, grid, names, study, pelvis=(scheme == "enhance"), keep=keep)
    for p in problems:
        rows.append({"study": study, "level": "study", "key": "flag:labels", "value": "", "note": p})
    return rows
