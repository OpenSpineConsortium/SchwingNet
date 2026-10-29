"""Every measurement defined once: the points that make it and the rule that gives its value.

A measurement here is a value and the points it is taken between. An end-plate width is the
distance between the end-plate's two lateral ends, and the line between them is how it was taken.
The oracle (oracle.py) returns both from a mask; the network (model.py) predicts the points and
computes the value from them by the same rule, so the line drawn for a measurement and the number
reported for it never disagree, and a loss on the points is a loss on the measurement's own
definition. Each rule is written once over an array namespace `xp`, numpy for the oracle and
jax.numpy for the network.

The measures are scanimport's (scanimport/__init__.py, SEVEN and EXTRA): the seven chords of
Panjabi's tables a vertebral mask can read, and two the import pipeline keeps for the record only
and never sets beside Panjabi (the transverse span and a spinous length). Their definitions in
the papers' words are schwingcheck.mnemonics'; how the stand-in oracle takes each is the `how`
below, from scanimport/geometry.py's docstring. The frame is the vertebra's own (geometry.py): x
to the patient's right, y from the canal toward the body (anterior), z up the column.

A length is the distance between two points. The interface carries angles (between two segments)
and areas (of a planar polygon) too, for the extractors that will measure pedicles, facets and
end-plate areas: nothing here measures one yet, and their rules are tested on figures whose
answer is known.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from schwingcheck import SIZE_POWER, UNITS
from schwingcheck.mnemonics import MEASURE_INFO

KINDS = ("length", "area", "angle")
PLANES = ("coronal", "sagittal", "axial")          # (x, z), (y, z) and (x, y) of the vertebra's frame
TINY = 1e-12                                       # under a square root, so a gradient at a zero length is finite


@dataclass(frozen=True)
class Spec:
    """One measurement: its key (scanimport's name), its kind, the names of its points in the
    order the rule reads them, the frame axis a chord runs along (empty when it runs along none),
    the plane it is drawn on, Panjabi's mnemonic (empty for a record-only chord) and how the
    stand-in oracle takes it."""
    key: str
    kind: str
    points: Tuple[str, ...]
    axis: str
    plane: str
    panjabi: str
    how: str

    @property
    def units(self) -> str:
        return UNITS[self.kind]

    @property
    def size_power(self) -> int:
        return SIZE_POWER[self.kind]

    @property
    def definition(self) -> str:
        """The papers' definition, where schwingcheck.mnemonics has one."""
        info = MEASURE_INFO.get(self.key)
        return info.definition if info is not None else ""

    def value(self, P, xp=np):
        """The value from the points P (..., len(points), 3), in millimetres, square millimetres
        or degrees."""
        if self.kind == "length":
            return length(P[..., 0, :], P[..., 1, :], xp)
        if self.kind == "angle":
            return angle(P[..., 1, :] - P[..., 0, :], P[..., 3, :] - P[..., 2, :], xp)
        return polygon_area(P, xp)


def length(a, b, xp=np):
    d = b - a
    return xp.sqrt(xp.maximum(xp.sum(d * d, axis=-1), TINY))


def angle(u, v, xp=np):
    """The angle between two directions in degrees, by atan2 of the cross and dot products, which
    keeps its precision and its gradient near 0 and 180 degrees where arccos of the dot loses both."""
    c = xp.cross(u, v)
    s = xp.sqrt(xp.maximum(xp.sum(c * c, axis=-1), TINY))
    return xp.degrees(xp.arctan2(s, xp.sum(u * v, axis=-1)))


def polygon_area(P, xp=np):
    """The area of a planar polygon (..., n, 3) by the vector form of the shoelace rule: half the
    length of the sum of the cross products of consecutive corners."""
    nxt = xp.roll(P, -1, axis=-2)
    c = xp.sum(xp.cross(P, nxt), axis=-2)
    return 0.5 * xp.sqrt(xp.maximum(xp.sum(c * c, axis=-1), TINY))


def _chord(key: str, ends: Tuple[str, str], axis: str, plane: str, panjabi: str, how: str) -> Spec:
    return Spec(key, "length", ("%s.%s" % (key, ends[0]), "%s.%s" % (key, ends[1])), axis, plane, panjabi, how)


SPECS: Dict[str, Spec] = {s.key: s for s in [
    _chord("endplate", ("right", "left"), "x", "coronal", "EPWu",
           "the width along x of the body's top slab, the uppermost 12 per cent of its height, surface to surface"),
    _chord("endplate_depth", ("posterior", "anterior"), "y", "sagittal", "EPDu",
           "the depth along y of the top slab, from the body's posterior wall (the canal's anterior wall) to its "
           "anterior surface"),
    _chord("endplate_lower", ("right", "left"), "x", "coronal", "EPWl",
           "the width along x of the body's bottom slab"),
    _chord("endplate_lower_depth", ("posterior", "anterior"), "y", "sagittal", "EPDl",
           "the depth along y of the bottom slab from the posterior wall"),
    _chord("h_post", ("superior", "inferior"), "z", "sagittal", "VBHp",
           "the median height along z of the body's columns in its posterior fifth and its central half across"),
    _chord("canal_w", ("right", "left"), "x", "axial", "SCW",
           "the canal's width across its middle, the median over the slabs of the middle half of the body's height"),
    _chord("canal_ap", ("posterior", "anterior"), "y", "axial", "SCD",
           "the canal's depth at its midline, front to back, the median over the same slabs"),
    _chord("tp_span", ("right", "left"), "x", "coronal", "",
           "record only: the extent along x of the whole vertebra, or of SPINEPS's costal labels"),
    _chord("spinous_length", ("canal", "tip"), "", "sagittal", "",
           "record only: from the canal's posterior wall at the midline to the farthest voxel behind it within 10 mm "
           "of the midline, a straight line in three dimensions"),
]}

SEVEN = ["endplate", "endplate_depth", "endplate_lower", "endplate_lower_depth", "h_post", "canal_w", "canal_ap"]
EXTRA = ["tp_span", "spinous_length"]


def select(keys: Sequence[str]) -> List[Spec]:
    unknown = [k for k in keys if k not in SPECS]
    if unknown:
        raise ValueError("no measurement %r; the specs are %s" % (unknown, ", ".join(SPECS)))
    return [SPECS[k] for k in keys]


def landmarks(keys: Sequence[str]) -> List[str]:
    """The points the measurements need, in the order of the keys and of each one's points."""
    out: List[str] = []
    for s in select(keys):
        out += [p for p in s.points if p not in out]
    return out


def index_of(keys: Sequence[str]) -> Dict[str, List[int]]:
    """For each measurement, the indices of its points in landmarks(keys)."""
    names = landmarks(keys)
    return {s.key: [names.index(p) for p in s.points] for s in select(keys)}


def values(P, keys: Sequence[str], xp=np):
    """Every measurement's value from the landmarks P (..., len(landmarks(keys)), 3): (..., keys)."""
    at = index_of(keys)
    return xp.stack([SPECS[k].value(P[..., at[k], :], xp) for k in keys], axis=-1)

