#!/usr/bin/env python3
"""COBRA2026's Varian cases (centres F and G) as a realxray export in the Elekta export's layout.

Why: COBRA2026 (Thummerer et al. 2026, Zenodo 21322350, CC BY-NC 4.0) holds 225 living pelvic radiotherapy
patients imaged on Varian linacs, each with its kV cone-beam projections, the RTK geometry of every projection
and the planning CT deformably registered to the cone-beam scan (ct_def.mha). The Elekta part became the QA
loop's external arm through spinesurg-ct-nnunet's tools/realxray_cobra_export.py, which refuses Varian on a
manufacturer check and on the 0.28 by 1.12 mm pixels of one Varian imager. This tool is that exporter's method
written again for Varian, read from it and from its geometry solver (tools/cobra_varian_geometry.py there) and
never run from them, so that tools/realx_pairs.py can build the Varian arm the way it built the Elekta one.

The geometry is RTK's ThreeDCircularProjectionGeometry (geometry.xml, version 3). Each projection's matrix is
made here from its parameters by RTK's own composition (rtkThreeDCircularProjectionGeometry.cxx,
AddProjectionInRadians): P = T(sox - pox, soy - poy) M(-sdd, -sid) S(-sox, -soy) R, where R is ITK's Euler
rotation with the order Z, X, Y (R = Rz(-in plane) Rx(-out of plane) Ry(-gantry)), M the magnification
[[-sdd, 0, 0, 0], [0, -sdd, 0, 0], [0, 0, 1, -sid]], S and T translations; angles are degrees in the file and
distances millimetres, the matrix taking RTK world millimetres to detector millimetres. The matrix the file
ships beside the parameters must put every corner of a 600 mm cube about the isocentre within MATRIX_TOL of
where the made one does, or the case is refused: a reading of the convention that is wrong anywhere fails here,
before an image is touched.

The patient map. The CT (LPS, its origin at the isocentre) reaches RTK's world through a signed permutation
p_rtk = W (p - iso), searched on 2026-09-23 over the 16 that put the patient's long axis on the rotation axis
and found to be [[1, 0, 0], [0, 0, -1], [0, -1, 0]] on 96 Varian cases (cobra2026/varian/VARIAN_GEOMETRY.json).
It is tested again here on every case, as the Elekta export tested its own: the CT is rendered through each of
the 16 maps on four frames spread over the sweep, the body-edge normalised cross-correlation (NCC) of each
render with the real frame taken inside the exposed band, and a case is exported only when the solved map
ranks first and leads the next by MAP_MARGIN. A case that fails is refused, never repaired.

Per case: 24 frames spread over the sweep; each converted to attenuation a = -log(I / I0), I0 per frame from
the pixels whose rays cross no tissue of the registered CT, as the Elekta export did; cropped to a square of
the exposed band's height about the projected lumbosacral junction, since the loop reads square frames and
a C-arm's field is that size; resampled to 512 pixels and windowed by the Elekta export's display ladder
(percentiles 1, 5, 50, 95 and 99 of the body's attenuation onto grey 27, 47, 126, 216 and 239); flipped so
cranial is up. Each frame's meta carries K and the extrinsic to the CT's LPS frame for that PNG, in edge
coordinates (pixel i spans [i, i + 1)), its view angles, its own edge NCC, and the boxes of the TotalSegmentator
masks (the anomaly harvest's, run on this same ct_def) projected through it. Levels follow the two-labeller
rule: a structure's level is named only where TotalSegmentator and SPINEPS with VERIDAH name the same bone
alike (Dice 0.5 or more); the held-out rule is the Elekta export's (md5 of the case mod 10: 8 and 9 test).

    python tools/cobra_varian_export.py export --data <data root> --out <data root>/realxray/cobra_varian \
        --list <cases file> [--shard i --n-shards n]
    python tools/cobra_varian_export.py proof --data <data root> --out <folder>   # the proof renders' boxes again
    python tools/cobra_varian_export.py summary --out <data root>/realxray/cobra_varian

What leaves the grid is the summary's counts and distributions; the frames, masks and meta stay there.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import time
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import numpy as np

BUILDER = "cobra_varian_export (SchwingNet, 2026-11-01)"
DATASET = "cobra_varian"
SOLVED_MAP = np.array([[1, 0, 0], [0, 0, -1], [0, -1, 0]], np.float64)
MAP_MARGIN = 0.10
N_FRAMES = 24
N_PROBE = 4
BLOCK_MM = 4.0              # the render's block for the pose test, near the Elekta export's 3.2 mm, square in mm
STEP_MM = 1.0
MU_WATER = 0.0206           # 1/mm, water near 60 keV; the edge score is blind to the scale, the air test is not
MATRIX_TOL = 1e-6           # detector millimetres
SIZE = 512
MAX_PTS = 20000
MIN_VOX = 500
MIN_SIDE = 8.0
MIN_VIS = 0.5
AIR_WATER_CM = 0.5          # a ray through less than 5 mm water-equivalent and no bone of the CT is air
AIR_ERODE = 10
AIR_MIN_PX = 2000
BODY_ATT = 0.25             # the window's body region, as the Elekta export's v3
MIRROR_RATIO = 0.8          # the air scan mirrored must fit the air this much better to say the stored one is turned;
                            # a full bowtie is near symmetric, so the two differ by noise there
OR_PCT = (1, 5, 50, 95, 99)
OR_GREY = (27, 47, 126, 216, 239)
TS_LEVELS = ("T12", "L1", "L2", "L3", "L4", "L5")
VERSE_NAME = {19: "T12", 20: "L1", 21: "L2", 22: "L3", 23: "L4", 24: "L5", 25: "L6", 26: "sacrum", 28: "T13"}
CROP_ANCHORS = ("L4", "L5", "sacrum")
SPLITS = ("train", "val", "test")


def split_of(case):
    """The Elekta export's split: md5 of the case id mod 10, 0 to 6 train, 7 validation, 8 and 9 test."""
    h = int(hashlib.md5(case.encode()).hexdigest(), 16) % 10
    return "train" if h <= 6 else ("val" if h == 7 else "test")


# ---------------------------------------------------------------- RTK geometry

GEOMETRY_TAGS = {"SourceToIsocenterDistance": "sid", "SourceToDetectorDistance": "sdd", "GantryAngle": "gantry",
                 "OutOfPlaneAngle": "out_of_plane", "InPlaneAngle": "in_plane", "SourceOffsetX": "source_x",
                 "SourceOffsetY": "source_y", "ProjectionOffsetX": "offset_x", "ProjectionOffsetY": "offset_y",
                 "RadiusCylindricalDetector": "radius"}


def read_rtk_geometry(path):
    """Every projection's parameters, a value given once at the top standing for every projection that does not
    give its own, as RTK writes them, with the matrix the file ships beside them (or None)."""
    root = ET.parse(str(path)).getroot()
    if root.tag != "RTKThreeDCircularGeometry" or root.get("version") != "3":
        raise ValueError(f"not an RTK version 3 circular geometry: {root.tag} {root.get('version')}")
    common = {name: 0.0 for name in GEOMETRY_TAGS.values()}
    for child in root:
        if child.tag in GEOMETRY_TAGS:
            common[GEOMETRY_TAGS[child.tag]] = float(child.text)
    projections = []
    for node in root.findall("Projection"):
        p = dict(common, matrix=None)
        for child in node:
            if child.tag in GEOMETRY_TAGS:
                p[GEOMETRY_TAGS[child.tag]] = float(child.text)
            elif child.tag == "Matrix":
                p["matrix"] = np.array(child.text.split(), np.float64).reshape(3, 4)
        projections.append(p)
    return projections


def rotation_zxy(ax, ay, az):
    """ITK's Euler3DTransform with ComputeZYX off, angles in radians: R = Rz Rx Ry, Y applied first."""
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rz @ rx @ ry


def rtk_matrix(p):
    """The 3x4 matrix RTK composes for one projection: RTK world millimetres to detector millimetres."""
    rot = np.eye(4)
    rot[:3, :3] = rotation_zxy(-math.radians(p["out_of_plane"]), -math.radians(p["gantry"]), -math.radians(p["in_plane"]))
    shift_source = np.eye(4)
    shift_source[:2, 3] = (-p["source_x"], -p["source_y"])
    magnify = np.array([[-p["sdd"], 0, 0, 0], [0, -p["sdd"], 0, 0], [0, 0, 1, -p["sid"]]], np.float64)
    shift_detector = np.eye(3)
    shift_detector[:2, 2] = (p["source_x"] - p["offset_x"], p["source_y"] - p["offset_y"])
    return shift_detector @ magnify @ shift_source @ rot


def rtk_source(p):
    """The source in RTK's world: the rotated frame's (source x, source y, sid) turned back."""
    r = rotation_zxy(-math.radians(p["out_of_plane"]), -math.radians(p["gantry"]), -math.radians(p["in_plane"]))
    return r.T @ np.array([p["source_x"], p["source_y"], p["sid"]])


# the corners and centre of a cube of 600 mm about the isocentre, where every patient point of a case lies
CHECK_POINTS = np.array([[x, y, z] for x in (-300, 300) for y in (-300, 300) for z in (-300, 300)] + [[0, 0, 0]], float)


def matrices_of(projections):
    """The matrices made from the parameters, and the largest distance in detector millimetres between where a
    made and a shipped matrix put the points of CHECK_POINTS (None where the file ships no matrix)."""
    mats, worst = [], None
    for p in projections:
        m = rtk_matrix(p)
        if p["radius"] != 0.0:
            raise ValueError("a cylindrical detector; this tool knows the flat panel only")
        if p["matrix"] is not None:
            mine, theirs = np.c_[project(m, CHECK_POINTS)], np.c_[project(p["matrix"], CHECK_POINTS)]
            err = float(np.abs(mine - theirs).max())
            worst = err if worst is None else max(worst, err)
        mats.append(m)
    return mats, worst


def signed_perms():
    """Patient frame to RTK world: patient z onto the rotation axis y, patient x and y onto x and z, every sign:
    the 16 candidates the Elekta export and the solver searched."""
    out = []
    for xy_to in ((0, 2), (2, 0)):
        for sx in (1, -1):
            for sy in (1, -1):
                for sz in (1, -1):
                    pi = np.zeros((3, 3))
                    pi[xy_to[0], 0], pi[xy_to[1], 1], pi[1, 2] = sx, sy, sz
                    out.append(pi)
    return out


def world_map(pi, iso):
    """4x4 taking a CT point to RTK's world: p_rtk = pi (p - iso)."""
    w = np.eye(4)
    w[:3, :3] = pi
    w[:3, 3] = -pi @ iso
    return w


def pixel_matrix(ox, oy, sx, sy):
    """Detector millimetres to the stored image's pixels in edge coordinates: pixel i's centre lies at the
    detector's origin plus i spacings and spans [i, i + 1)."""
    return np.array([[1.0 / sx, 0.0, -ox / sx + 0.5], [0.0, 1.0 / sy, -oy / sy + 0.5], [0.0, 0.0, 1.0]])


def project(P, pts):
    q = np.asarray(pts, float) @ P[:, :3].T + P[:, 3]
    return q[:, 0] / q[:, 2], q[:, 1] / q[:, 2]


def facing(P, point):
    """P with the sign that gives the point positive depth; RTK's matrices give points before the source a
    negative one, and the projection does not change with the sign."""
    return -P if (P[2, :3] @ point + P[2, 3]) < 0 else P


def camera_from_matrix(P):
    """K (upper triangular, K[2, 2] = 1) and a rigid extrinsic with P = c K [R | t] for some c != 0."""
    from scipy.linalg import rq
    K, R = rq(P[:, :3])
    S = np.diag(np.sign(np.diag(K)))
    K, R = K @ S, S @ R
    if np.linalg.det(R) < 0:
        K, R = -K, -R
    t = np.linalg.solve(K, P[:, 3])
    K = K / K[2, 2]
    ext = np.eye(4)
    ext[:3, :3], ext[:3, 3] = R, t
    return K, ext


def view_of(P, iso):
    """The beam in the patient's frame: its angle from the anteroposterior view in the axial plane, its
    craniocaudal tilt and the side the source is on (LPS: +x left, +y posterior)."""
    C = -np.linalg.solve(P[:, :3], P[:, 3])
    d = (iso - C) / np.linalg.norm(iso - C)
    lat = float(np.degrees(np.arctan2(abs(d[0]), abs(d[1]))))
    cc = float(np.degrees(np.arcsin(np.clip(d[2], -1, 1))))
    if abs(d[1]) >= abs(d[0]):
        side = "anterior" if C[1] < iso[1] else "posterior"
    else:
        side = "left" if C[0] > iso[0] else "right"
    return {"lat_from_ap_deg": round(lat, 2), "cranial_caudal_deg": round(cc, 2), "source_side": side,
            "source_mm": np.round(C, 1).tolist(), "beam_dir_lps": np.round(d, 4).tolist()}


# ---------------------------------------------------------------- MetaImage, XIM and metadata.yaml

MET = {"MET_UCHAR": np.uint8, "MET_CHAR": np.int8, "MET_USHORT": np.uint16, "MET_SHORT": np.int16,
       "MET_UINT": np.uint32, "MET_INT": np.int32, "MET_FLOAT": np.float32, "MET_DOUBLE": np.float64}


def mha_header(path):
    hdr = {}
    with open(path, "rb") as f:
        while True:
            line = f.readline()
            if not line:
                raise ValueError(f"{path}: no ElementDataFile line")
            k, _, v = line.decode("latin-1").partition("=")
            hdr[k.strip()] = v.strip()
            if k.strip() == "ElementDataFile":
                break
        hdr["_data_offset"] = f.tell()
    if hdr["ElementDataFile"] != "LOCAL":
        raise ValueError(f"{path}: detached data file")
    hdr["_dims"] = [int(x) for x in hdr["DimSize"].split()]
    hdr["_spacing"] = [float(x) for x in hdr["ElementSpacing"].split()]
    hdr["_offset"] = [float(x) for x in hdr.get("Offset", hdr.get("Origin", "0 0 0")).split()]
    hdr["_direction"] = [float(x) for x in hdr.get("TransformMatrix", "1 0 0 0 1 0 0 0 1").split()]
    hdr["_compressed"] = hdr.get("CompressedData", "False") == "True"
    order = ">" if hdr.get("BinaryDataByteOrderMSB", "False") == "True" else "<"
    hdr["_dtype"] = np.dtype(MET[hdr["ElementType"]]).newbyteorder(order)
    return hdr


def mha_volume(path):
    """A whole 3-D image as an array indexed [z, y, x], with its header."""
    h = mha_header(path)
    shape = tuple(reversed(h["_dims"]))
    with open(path, "rb") as f:
        f.seek(h["_data_offset"])
        raw = f.read()
    data = zlib.decompress(raw) if h["_compressed"] else raw
    return np.frombuffer(data, h["_dtype"], count=int(np.prod(shape))).reshape(shape), h


def mha_frames(path, frames):
    """{k: 2-D array} of the wanted frames of a stack, a compressed one decompressed as a stream so a sweep of a
    gigabyte costs the frames kept."""
    h = mha_header(path)
    nc, nr, nk = h["_dims"]
    dt = h["_dtype"]
    size = nr * nc * dt.itemsize
    want = sorted({int(k) for k in frames})
    if any(k < 0 or k >= nk for k in want):
        raise ValueError(f"{path}: frame out of range (stack has {nk})")
    if not h["_compressed"]:
        mm = np.memmap(path, dt, "r", offset=h["_data_offset"], shape=(nk, nr, nc))
        return {k: np.array(mm[k]) for k in want}, h
    keep = {k: bytearray() for k in want}
    last = (max(want) + 1) * size
    dec = zlib.decompressobj()
    pos = 0
    with open(path, "rb") as f:
        f.seek(h["_data_offset"])
        while pos < last:
            chunk = f.read(1 << 24)
            if not chunk:
                break
            raw = dec.decompress(chunk)
            for k in want:
                s, e = max(k * size, pos), min((k + 1) * size, pos + len(raw))
                if s < e:
                    keep[k] += raw[s - pos: e - pos]
            pos += len(raw)
    out = {}
    for k in want:
        if len(keep[k]) != size:
            raise ValueError(f"{path}: frame {k} truncated")
        out[k] = np.frombuffer(bytes(keep[k]), dt).reshape(nr, nc)
    return out, h


def read_cbct_metadata(path):
    """The cbct section of a case's metadata.yaml, whose lines are 'key: value' under 'cbct:'; the standard
    library reads no YAML and the file needs no more than this."""
    out, section = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("-"):
            continue
        if not line.startswith(" "):
            section = line.split(":")[0].strip()
            continue
        if section != "cbct":
            continue
        key, _, value = line.strip().partition(":")
        value = value.strip()
        try:
            out[key] = float(value) if any(c in value for c in ".e") else int(value)
        except ValueError:
            out[key] = None if value in ("null", "~", "") else value
    return out


def read_xim(path):
    """A Varian XIM image (the format of the air scans under a case's Calibrations), as pylinac and RTK's
    rtkXimImageIO read it: the header, the pixels and the property list. A compressed image stores its first
    row and one pixel as 4-byte integers, then for every further pixel a 2-bit code in a lookup table saying
    whether its difference is 1, 2 or 4 bytes, the difference being pixel - left - above + upper left. The
    property list after the pixels must read whole, or the pixels were not read right."""
    import struct
    buf = Path(path).read_bytes()
    pos = 0

    def take(fmt):
        nonlocal pos
        size = struct.calcsize(fmt)
        vals = struct.unpack_from("<" + fmt, buf, pos)
        pos += size
        return vals

    ident = buf[:8].split(b"\x00")[0].decode("latin-1")
    pos = 8
    version, width, height, bits, nbytes, compressed = take("6i")
    hdr = {"format": ident, "version": version, "width": width, "height": height, "bits_per_pixel": bits,
           "bytes_per_pixel": nbytes, "compressed": compressed}
    n = width * height
    if compressed:
        (lut_size,) = take("i")
        lut = np.frombuffer(buf, np.uint8, lut_size, pos)
        pos += lut_size
        (_compressed_size,) = take("i")
        codes = np.stack([lut & 3, (lut >> 2) & 3, (lut >> 4) & 3, (lut >> 6) & 3], axis=1).ravel()[: n - width - 1]
        head = np.frombuffer(buf, "<i4", width + 1, pos).astype(np.int64)
        pos += 4 * (width + 1)
        widths = np.where(codes == 0, 1, np.where(codes == 1, 2, 4))
        starts = pos + np.concatenate([[0], np.cumsum(widths)[:-1]])
        diffs = np.empty(len(codes), np.int64)
        for w, dt in ((1, "i1"), (2, "<i2"), (4, "<i4")):
            sel = widths == w
            if sel.any():
                idx = starts[sel]
                raw = np.frombuffer(buf, np.uint8)[idx[:, None] + np.arange(w)[None, :]]
                diffs[sel] = raw.copy().view(dt).ravel()
        pos += int(widths.sum())
        (_uncompressed_size,) = take("i")
        pixels = undo_predictor(head, diffs, width, height)
    else:
        (size,) = take("i")
        dt = {1: "i1", 2: "<i2", 4: "<i4"}[nbytes]
        pixels = np.frombuffer(buf, dt, n, pos).astype(np.int64).reshape(height, width)
        pos += size
    (bins,) = take("i")
    pos += 4 * bins
    (count,) = take("i")
    props = {}
    for _ in range(count):
        (length,) = take("i")
        name = buf[pos: pos + length].decode("latin-1")
        pos += length
        (kind,) = take("i")
        if kind == 0:
            (value,) = take("i")
        elif kind == 1:
            (value,) = take("d")
        elif kind == 2:
            (length,) = take("i")
            value = buf[pos: pos + length].decode("latin-1")
            pos += length
        elif kind == 4:
            (length,) = take("i")
            value = list(take(f"{length // 8}d"))
        elif kind == 5:
            (length,) = take("i")
            value = list(take(f"{length // 4}i"))
        else:
            raise ValueError(f"{path}: property {name!r} of unknown kind {kind}")
        props[name] = value
    return pixels, hdr, props


def undo_predictor(head, diffs, width, height):
    """The pixels of a compressed XIM: p[i] = d[i] + p[i - 1] + p[i - w] - p[i - w - 1] in raster order from
    pixel w + 1, the first w + 1 given. With e[i] = p[i] - p[i - w] it is e[i] = e[i - 1] + d[i], a running
    sum, and each column is then a running sum of e down the rows."""
    n = width * height
    p = np.zeros(n, np.int64)
    p[: width + 1] = head
    e = np.zeros(n, np.int64)
    e[width] = p[width] - p[0]
    e[width + 1:] = e[width] + np.cumsum(diffs)
    rows = e.reshape(height, width)
    rows[0] = p[:width]
    return np.cumsum(rows, axis=0)


# ---------------------------------------------------------------- rendering and the pose test

def render(vol, org, sp, P, nr, nc, step=STEP_MM, budget=4_000_000):
    """Line integrals through the CT (indexed [z, y, x], LPS origin and spacing, identity direction) along the
    rays of an nr by nc grid whose P takes CT millimetres to the grid's edge coordinates with the CT in front:
    the attenuation (mu times length), the water-equivalent and bone centimetres the Elekta export's air test
    reads, which rays hit the CT's box, and which enter or leave it through tissue the scan does not hold."""
    from scipy.ndimage import map_coordinates
    Minv = np.linalg.inv(P[:, :3])
    src = -Minv @ P[:, 3]
    cols, rows = np.meshgrid(np.arange(nc) + 0.5, np.arange(nr) + 0.5)
    d = Minv @ np.stack([cols.ravel(), rows.ravel(), np.ones(cols.size)])
    d /= np.linalg.norm(d, axis=0, keepdims=True)
    nz, ny, nx = vol.shape
    lo, hi = org - 0.5 * sp, org + (np.array([nx, ny, nz]) - 0.5) * sp
    with np.errstate(divide="ignore", invalid="ignore"):
        t0, t1 = (lo[:, None] - src[:, None]) / d, (hi[:, None] - src[:, None]) / d
    tmin = np.maximum(np.nanmax(np.minimum(t0, t1), axis=0), 0.0)
    tmax = np.nanmin(np.maximum(t0, t1), axis=0)
    hit = tmax > tmin
    n = cols.size
    line, water, bone, trunc = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n, bool)
    idx_all = np.flatnonzero(hit)
    if idx_all.size:
        steps = int(np.ceil((tmax[idx_all] - tmin[idx_all]).max() / step)) + 1
        chunk = max(1, budget // steps)
        for a in range(0, idx_all.size, chunk):
            idx = idx_all[a: a + chunk]
            ts = tmin[idx, None] + np.arange(steps)[None, :] * step
            ok = ts <= tmax[idx, None]
            pts = src[:, None, None] + d[:, idx, None] * ts[None]
            coords = [(pts[2] - org[2]) / sp[2], (pts[1] - org[1]) / sp[1], (pts[0] - org[0]) / sp[0]]
            hu = map_coordinates(vol, [c.ravel() for c in coords], order=1, mode="constant", cval=-1000.0).reshape(ts.shape)
            hu = np.where(ok, hu, -1000.0)
            last = np.clip(ok.sum(1) - 1, 0, None)
            trunc[idx] = (hu[:, 0] > -500.0) | (hu[np.arange(len(idx)), last] > -500.0)
            line[idx] = MU_WATER * np.clip(1.0 + hu / 1000.0, 0.0, None).sum(1) * step
            water[idx] = np.clip((hu + 1000.0) / 1000.0, 0.0, 1.0).sum(1) * step / 10.0
            bone[idx] = np.clip(hu, 0.0, None).sum(1) / 1000.0 * step / 10.0
    shape = (nr, nc)
    return line.reshape(shape), water.reshape(shape), bone.reshape(shape), hit.reshape(shape), trunc.reshape(shape)


def blocks_for(sx, sy, block_mm=BLOCK_MM):
    """Block sizes in pixels (columns, rows) near block_mm square, so the edge score sees the same scale on an
    imager of 0.28 by 1.12 mm pixels as on one of 0.39 mm."""
    return max(1, int(round(block_mm / sx))), max(1, int(round(block_mm / sy)))


def block_mean(x, bx, by):
    h, w = x.shape[0] // by, x.shape[1] // bx
    return x[: h * by, : w * bx].reshape(h, by, w, bx).mean((1, 3))


def ncc(a, b, m):
    a, b = a[m] - a[m].mean(), b[m] - b[m].mean()
    return float((a * b).sum() / max(np.sqrt((a * a).sum() * (b * b).sum()), 1e-12))


def frame_scores(real_blocks, line, hit, trunc, band_blocks):
    """(edge NCC, log NCC) of a real frame's blocks against a render, as the Elekta export scores them: the
    gradient magnitude of the log signal against that of the render's log transmission, on rays that cross the
    CT whole and some tissue, inside the exposed band less two blocks at each blade (the blades are not in
    the CT)."""
    from scipy.ndimage import sobel
    h, w = min(real_blocks.shape[0], line.shape[0]), min(real_blocks.shape[1], line.shape[1])
    real, line, hit, trunc = real_blocks[:h, :w], line[:h, :w], hit[:h, :w], trunc[:h, :w]
    lr, lt = np.log(np.clip(real, 1, None)), -line
    gr, gt = np.hypot(sobel(lr, 0), sobel(lr, 1)), np.hypot(sobel(lt, 0), sobel(lt, 1))
    rows = np.arange(h)
    band = (rows >= band_blocks[0] + 2) & (rows + 1 <= band_blocks[1] - 2)
    base = hit & ~trunc & (real > 0) & band[:, None]
    edge_mask = base & (line > -math.log(0.9))
    edge = ncc(gr, gt, edge_mask) if edge_mask.sum() > 100 else -1.0
    log = ncc(lr, lt, base) if base.sum() > 100 else float("nan")
    return edge, log


def exposed_rows(I, c_row, min_step=0.4, margin=4):
    """[r0, r1) of the exposed band of a craniocaudally collimated frame, by the Elekta export's rule: the
    blades' shadow is a step down in each row's 90th-percentile signal, and the band is the run of rows about
    the central row above half-way (in log) between the exposed level and the shadow's, less a margin for the
    penumbra; a side with no step is left uncut."""
    L = np.log(np.clip(np.percentile(I, 90, axis=1), 1, None))
    nr = len(L)
    c0 = int(np.clip(round(c_row), 40, nr - 40))
    level = float(np.median(L[c0 - 20: c0 + 20]))
    r0, r1 = 0, nr
    top, bottom = float(np.median(L[:15])), float(np.median(L[-15:]))
    if level - top > min_step:
        low = np.where(L[:c0] < (level + top) / 2)[0]
        r0 = int(low.max()) + 1 + margin if low.size else 0
    if level - bottom > min_step:
        low = np.where(L[c0:] < (level + bottom) / 2)[0]
        r1 = c0 + int(low.min()) - margin if low.size else nr
    return r0, r1


def sweep_bands(raw):
    """One blade setting a sweep: a frame's band far from the sweep's median is a miss and takes the median."""
    m0, m1 = np.median([b[0] for b in raw.values()]), np.median([b[1] for b in raw.values()])
    return {k: (int(r0) if abs(r0 - m0) <= 10 else int(m0), int(r1) if abs(r1 - m1) <= 10 else int(m1))
            for k, (r0, r1) in raw.items()}


def map_scores(probe, reals, sims, mats, A, vol, org, sp, iso, nr, nc, bx, by, bands):
    """Every signed map's mean and smallest edge NCC over the probe frames, on the real frames and, where the
    authors' simulated projections exist, on theirs."""
    D = np.diag([1.0 / bx, 1.0 / by, 1.0])
    gh, gw = nr // by, nc // bx
    out = []
    for pi in signed_perms():
        real_e, sim_e = [], []
        for k in probe:
            P = facing(D @ A @ mats[k] @ world_map(pi, iso), iso)
            line, _, _, hit, trunc = render(vol, org, sp, P, gh, gw)
            band = (bands[k][0] / by, bands[k][1] / by)
            real_e.append(frame_scores(block_mean(reals[k].astype(np.float64), bx, by), line, hit, trunc, band)[0])
            if sims is not None:
                sim_e.append(frame_scores(block_mean(sims[k].astype(np.float64), bx, by), line, hit, trunc, band)[0])
        out.append({"rows": pi.astype(int).tolist(), "edge_real": round(float(np.mean(real_e)), 4),
                    "edge_real_min": round(float(np.min(real_e)), 4),
                    "edge_sim": round(float(np.mean(sim_e)), 4) if sim_e else None})
    return out


def map_verdict(scores, solved=SOLVED_MAP, margin=MAP_MARGIN):
    """(passes, record): the solved map must rank first on the real frames and lead the next by the margin."""
    ranked = sorted(scores, key=lambda s: -s["edge_real"])
    mine = next(s for s in scores if np.allclose(s["rows"], solved))
    others = [s for s in scores if s is not mine]
    other = max(s["edge_real"] for s in others)
    sims = [s["edge_sim"] for s in others if s["edge_sim"] is not None]
    rec = {"rows": np.asarray(solved).astype(int).tolist(), "edge_ncc": mine["edge_real"],
           "edge_ncc_min_frame": mine["edge_real_min"], "next_best": round(other, 4),
           "margin": round(mine["edge_real"] - other, 4), "best_is_solved": ranked[0] is mine,
           "best_rows": ranked[0]["rows"], "edge_sim": mine["edge_sim"],
           "next_best_sim": max(sims) if sims else None}
    return bool(rec["best_is_solved"] and rec["margin"] >= margin), rec


# ---------------------------------------------------------------- the bowtie's air scan and attenuation

def find_flood(case_dir, meta, nc, nr):
    """The air scan through the bowtie this sweep used: Calibrations/AIR-*/Current/FilterBowtie.xim whose
    folder names the sweep's kV and whose own header names its bowtie and kV and has the stack's size. The
    stored projections are the detector's raw signal (the air level divided by this scan is flat across the
    bowtie), so the scan is what turns them into attenuation. (image, record) or (None, why)."""
    kv = meta.get("TubeVoltage")
    bowtie = meta.get("Bowtie")
    seen = []
    for path in sorted((Path(case_dir) / "Calibrations").glob("AIR-*/Current/FilterBowtie.xim")):
        if f"{int(kv)}KV" not in path.parent.parent.name.upper().replace("-", ""):
            seen.append(f"{path.parent.parent.name}: another kV")
            continue
        pixels, hdr, props = read_xim(path)
        if (hdr["width"], hdr["height"]) != (nc, nr):
            seen.append(f"{path.parent.parent.name}: {hdr['width']}x{hdr['height']}")
            continue
        if props.get("KVCollimatorShape") != bowtie or abs(float(props.get("KVKiloVolts", -1)) - float(kv)) > 0.5:
            seen.append(f"{path.parent.parent.name}: bowtie {props.get('KVCollimatorShape')} at {props.get('KVKiloVolts')} kV")
            continue
        return pixels.astype(np.float64), {"file": str(path.relative_to(case_dir)), "bowtie": bowtie, "kv": kv,
                                           "image_flipped_flag": props.get("ImageFlipped")}
    return None, "no air scan for this bowtie and kV: " + ("; ".join(seen) or "none under Calibrations/AIR-*/Current")


def flood_spread(I, F, air):
    """The spread of log(I / F) over the air pixels with the scan as stored and mirrored left to right: true
    air divided by the right scan is flat, so the stored orientation must give the smaller spread."""
    ok = air & (F > 0) & (I > 0)
    if ok.sum() < AIR_MIN_PX:
        return None, None
    as_stored = np.log(I[ok] / F[ok])
    Fm = F[:, ::-1]
    ok_m = air & (Fm > 0) & (I > 0)
    mirrored = np.log(I[ok_m] / Fm[ok_m])
    return float(np.std(as_stored)), float(np.std(mirrored))


def attenuation(I, F, scale):
    """a = -log(I / (scale F)): the stored signal over the air scan brought to this frame's air level."""
    return -np.log(np.clip(I, 1, None) / (scale * np.clip(F, 1, None)))


def window_or(atten, region):
    """The Elekta export's display ladder: the region's percentiles 1, 5, 50, 95 and 99 onto grey 27, 47, 126,
    216 and 239, linear between and beyond the ends."""
    q = np.percentile(atten[region], OR_PCT)
    q = np.maximum.accumulate(q + np.arange(len(q)) * 1e-6)
    t = np.maximum.accumulate(np.asarray(OR_GREY, np.float64) + np.arange(len(q)) * 1e-3)
    out = np.interp(atten, q, t)
    lo_s = (t[1] - t[0]) / max(q[1] - q[0], 1e-9)
    hi_s = (t[-1] - t[-2]) / max(q[-1] - q[-2], 1e-9)
    out = np.where(atten < q[0], t[0] + (atten - q[0]) * lo_s, out)
    out = np.where(atten > q[-1], t[-1] + (atten - q[-1]) * hi_s, out)
    return np.clip(out, 0, 255)


def air_mask(water, bone, hit, bx, by, shape, band):
    """Full-resolution pixels whose ray crosses no tissue of the CT (under AIR_WATER_CM water-equivalent and no
    bone, or missing the CT), kept two blocks from the body against registration error and penumbra, inside
    the exposed band."""
    from scipy.ndimage import binary_erosion
    air = (~hit) | ((water < AIR_WATER_CM) & (bone < 0.02))
    air = binary_erosion(air, iterations=2, border_value=1)
    full = np.repeat(np.repeat(air, by, 0), bx, 1)
    full = np.pad(full, ((0, max(0, shape[0] - full.shape[0])), (0, max(0, shape[1] - full.shape[1]))), mode="edge")
    full = full[: shape[0], : shape[1]]
    full[: band[0]] = False
    full[band[1]:] = False
    return full


# ---------------------------------------------------------------- the masks and the two labellers

def lps_grid(img):
    """A NIfTI's LPS origin and spacing where its axes are the CT's (SimpleITK's NIfTI of an LPS image with an
    identity direction); None where they are not."""
    lps = np.diag([-1.0, -1.0, 1.0, 1.0]) @ img.affine
    lin = lps[:3, :3]
    if not np.allclose(lin, np.diag(np.diag(lin)), atol=1e-6) or (np.diag(lin) <= 0).any():
        return None
    return lps[:3, 3], np.diag(lin)


def same_grid(img, shape_xyz, org, sp, tol=0.01):
    grid = lps_grid(img)
    return grid is not None and tuple(img.shape[:3]) == tuple(shape_xyz) and np.allclose(grid[0], org, atol=tol) \
        and np.allclose(grid[1], sp, atol=1e-4)


def harvest_masks(path, class_map, shape_xyz, org, sp):
    """The anomaly harvest's TotalSegmentator labels for the sacrum and T12 to L5, as boolean volumes indexed
    [z, y, x]. TotalSegmentator 2.18 labels S1 apart from the rest of the sacrum, which SPINEPS's sacrum and
    the Elekta export's include, so the sacrum here is the two together."""
    import nibabel as nib
    img = nib.load(str(path))
    if not same_grid(img, shape_xyz, org, sp):
        raise ValueError("the TotalSegmentator labels are not on ct_def's grid")
    ids = {name: int(i) for i, name in class_map.items()}
    lab = np.asarray(img.dataobj).transpose(2, 1, 0)
    out = {"sacrum": np.isin(lab, [ids["sacrum"], ids["vertebrae_S1"]])}
    for lv in TS_LEVELS:
        out[lv] = lab == ids[f"vertebrae_{lv}"]
    s1 = lab == ids["vertebrae_S1"]
    return out, int(s1.sum())


def spineps_names(ts_masks, spineps_path, shape_xyz, org, sp):
    """For each TotalSegmentator structure, SPINEPS's name for the bone it overlaps most (VerSe ids, VERIDAH's
    names) and the Dice of the two: (name, dice) or (None, 0)."""
    import nibabel as nib
    img = nib.load(str(spineps_path))
    if not same_grid(img, shape_xyz, org, sp):
        raise ValueError("SPINEPS's mask is not on ct_def's grid")
    seg = np.asarray(img.dataobj).transpose(2, 1, 0)
    out = {}
    for name, mask in ts_masks.items():
        vals, counts = np.unique(seg[mask], return_counts=True)
        keep = [(c, v) for v, c in zip(vals.tolist(), counts.tolist()) if v in VERSE_NAME]
        if not keep or not mask.any():
            out[name] = (None, 0.0)
            continue
        c, v = max(keep)
        dice = 2.0 * c / (mask.sum() + (seg == v).sum())
        out[name] = (VERSE_NAME[v], round(float(dice), 4))
    return out


def level_record(name, spineps):
    """The two-labeller rule: a level is named where both labellers name the same bone alike, Dice 0.5 or more."""
    sp_name, dice = spineps.get(name, (None, 0.0)) if spineps else (None, 0.0)
    agree = sp_name == name and dice >= 0.5
    return {"level_ts": name, "level_spineps": sp_name, "level_agree": agree, "level": name if agree else None,
            "dice_ts_spineps": dice}


def structure_points(mask, org, sp, rng):
    """At most MAX_PTS of a mask's voxels in LPS millimetres, whether it touches the CT's edge, its voxels."""
    idx = np.argwhere(mask)
    touch = [ax for ax in range(3) if len(idx) and (idx[:, ax].min() == 0 or idx[:, ax].max() == mask.shape[ax] - 1)]
    n = len(idx)
    if n > MAX_PTS:
        idx = idx[rng.choice(n, MAX_PTS, replace=False)]
    return org + idx[:, ::-1] * sp, not touch, n


# ---------------------------------------------------------------- one case

def case_inputs(data, case):
    data = Path(data)
    return {"case_dir": data / "cobra2026" / "cases" / case,
            "ts": data / "anomaly_harvest" / "cobra" / "ts" / f"{case}.nii.gz",
            "class_map": data / "anomaly_harvest" / "cobra" / "class_map.json",
            "lstv": data / "cobra2026" / "lstv" / f"{case}.json",
            "solver": data / "cobra2026" / "varian" / "geom" / f"{case}.json"}


def spineps_trusted(lstv_path):
    """The SPINEPS mask the transitional screen read, where its ids are names: the screen checked them against
    the centroid file (the raw-instance-id defect of 2026-09-23 named a sacrum C4). (path or None, why not)."""
    if not Path(lstv_path).is_file():
        return None, "no transitional screen record"
    rec = json.loads(Path(lstv_path).read_text())
    check = rec.get("ctd_check") or {}
    if not (rec.get("naming") == "ctd" and check.get("ok") is True and check.get("id_matches_ctd") is True):
        return None, "SPINEPS ids not checked against the centroids"
    mask = Path(rec.get("mask") or "")
    return (mask, None) if mask.is_file() else (None, "the screen's SPINEPS mask is not on disk")


def solver_status(path):
    """What the solver of 2026-09-23 (spinesurg-ct-nnunet tools/cobra_varian_geometry.py) found for the case: its
    status where it found the solved map, the map it found where another, or that it never tried the case."""
    if not Path(path).is_file():
        return "not tried"
    rec = json.loads(Path(path).read_text())
    if rec.get("status") == "ok" and np.allclose(rec.get("axis_map", []), SOLVED_MAP):
        return "ok"
    return f"{rec.get('status')}: {rec.get('axis_map')}"


def sample_frames(nk, n=N_FRAMES):
    return sorted({int(k) % nk for k in np.round(np.arange(n) * nk / n)})


def crop_window(anchor_uv, band, nc, nr, sx, sy):
    """A square of the exposed band's height (in millimetres) about the projected lumbosacral junction, inside
    the detector: (c0, r0, width, height) in full-resolution pixels."""
    side = min((band[1] - band[0]) * sy, nc * sx)
    w, h = int(round(side / sx)), int(round(side / sy))
    c0 = int(np.clip(round(anchor_uv[0] - w / 2.0), 0, nc - w))
    r0 = int(np.clip(round(anchor_uv[1] - h / 2.0), band[0], max(band[0], band[1] - h)))
    return c0, r0, w, h


def png_matrix(P_full, crop, flip):
    """The full-resolution edge-coordinate P carried onto the 512-pixel PNG: crop, scale and, where cranial
    would be down, the vertical flip."""
    c0, r0, w, h = crop
    T = np.array([[SIZE / w, 0.0, -c0 * SIZE / w], [0.0, SIZE / h, -r0 * SIZE / h], [0.0, 0.0, 1.0]])
    F = np.array([[1.0, 0, 0], [0, -1.0, SIZE], [0, 0, 1.0]]) if flip else np.eye(3)
    return F @ T @ P_full


def cranial_down(P, iso):
    """Whether a point 50 mm superior of the isocentre (LPS +z) lands lower on the image than the isocentre."""
    v0 = project(P, iso[None])[1][0]
    v1 = project(P, (iso + np.array([0.0, 0.0, 50.0]))[None])[1][0]
    return bool(v1 > v0)


def boxes_of(P, structures, levels, drops):
    """Each structure's box on the PNG, the 2nd to 98th percentile of its projected voxels clipped to the image,
    kept where half its voxels fall inside and both sides are MIN_SIDE pixels or more; a vertebra the CT does
    not hold whole is skipped."""
    boxes, lines = [], []
    for name, s in structures.items():
        if s["pts"] is None:
            continue
        cls = 1 if name == "sacrum" else 0
        if not s["complete"] and cls == 0:
            drops["incomplete_in_ct"] = drops.get("incomplete_in_ct", 0) + 1
            continue
        x, y = project(P, s["pts"])
        inside = (x >= 0) & (x < SIZE) & (y >= 0) & (y < SIZE)
        vf = float(inside.mean())
        x0, x1 = [float(np.clip(v, 0, SIZE)) for v in np.percentile(x, [2, 98])]
        y0, y1 = [float(np.clip(v, 0, SIZE)) for v in np.percentile(y, [2, 98])]
        if vf < MIN_VIS:
            drops["visible_frac<0.5"] = drops.get("visible_frac<0.5", 0) + 1
            continue
        if x1 - x0 < MIN_SIDE or y1 - y0 < MIN_SIDE:
            drops["side<8px"] = drops.get("side<8px", 0) + 1
            continue
        boxes.append(dict(cls=cls, **levels[name], box=[round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                          visible_frac=round(vf, 4), px=int(round((x1 - x0) * (y1 - y0))), fov_frac=s.get("fov_frac"),
                          complete_in_ct=s["complete"]))
        lines.append(f"{cls} {(x0 + x1) / 2 / SIZE:.6f} {(y0 + y1) / 2 / SIZE:.6f} {(x1 - x0) / SIZE:.6f} {(y1 - y0) / SIZE:.6f}")
    return boxes, lines


def excluded(rec, why):
    return dict(rec, status="excluded", reason=why)


def export_case(case, data, out):
    """One case's frames, meta and record, or the record of why it is refused."""
    from PIL import Image
    t0 = time.time()
    inp = case_inputs(data, case)
    cdir = inp["case_dir"]
    split = split_of(case)
    rec = {"case": case, "split": split, "centre": case[0], "status": "ok", "builder": BUILDER}
    md = read_cbct_metadata(cdir / "metadata.yaml")
    rec["metadata"] = {k: md.get(k) for k in ("Manufacturer", "Detector", "Bowtie", "Fan", "Trajectory", "Frames",
                                              "ImagerResX", "ImagerResY", "ImagerSizeX", "ImagerSizeY", "DetectorOffsetX",
                                              "TubeVoltage", "TubeCurrent", "PulseLength", "KVFilter", "ScatterGrid")}
    if md.get("Manufacturer") != "Varian":
        return excluded(rec, f"manufacturer {md.get('Manufacturer')}, not Varian")
    projections = read_rtk_geometry(cdir / "geometry.xml")
    mats, worst = matrices_of(projections)
    rec["geometry"] = {"projections": len(projections), "matrix_disagreement": worst, "sid": projections[0]["sid"],
                       "sdd": projections[0]["sdd"]}
    if worst is None or worst > MATRIX_TOL:
        return excluded(rec, f"the RTK parameters do not make the shipped matrices (worst {worst})")
    ph = mha_header(cdir / "projections.mha")
    nc, nr, nk = ph["_dims"]
    if nk != len(mats) or not np.allclose(ph["_direction"], np.eye(3).ravel()):
        return excluded(rec, f"{nk} projections for {len(mats)} matrices, or a turned stack")
    (ox, oy, _), (sx, sy, _) = ph["_offset"], ph["_spacing"]
    vol, ch = mha_volume(cdir / "ct_def.mha")
    if not np.allclose(ch["_direction"], np.eye(3).ravel()):
        return excluded(rec, "ct_def's direction is not the identity")
    vol = vol.astype(np.float32)
    org, sp = np.array(ch["_offset"], np.float64), np.array(ch["_spacing"], np.float64)
    fh = mha_header(cdir / "fov_cbct.mha")
    iso = np.array(fh["_offset"]) + np.array(fh["_direction"]).reshape(3, 3) @ ((np.array(fh["_dims"], float) - 1) / 2.0 * np.array(fh["_spacing"]))
    rec.update(nproj=nk, detector=[nc, nr], det_px_mm=[sx, sy], iso=np.round(iso, 3).tolist(), ct_shape_zyx=list(vol.shape),
               ct_spacing=sp.tolist())
    if not inp["ts"].is_file():
        return excluded(rec, "no TotalSegmentator labels in the anomaly harvest")
    class_map = json.loads(inp["class_map"].read_text())
    masks, s1_voxels = harvest_masks(inp["ts"], class_map, ch["_dims"], org, sp)
    mask_path, why_not = spineps_trusted(inp["lstv"])
    spineps = spineps_names(masks, mask_path, ch["_dims"], org, sp) if mask_path else None
    rec["labellers"] = {"totalsegmentator": "anomaly harvest, 2.18.0, on ct_def", "s1_voxels_merged_into_sacrum": s1_voxels,
                        "spineps": "used" if spineps else why_not,
                        "spineps_mask": mask_path.parent.name + "/" + mask_path.name if mask_path else None}
    rng = np.random.default_rng(int(hashlib.md5(case.encode()).hexdigest()[:8], 16))
    structures, levels = {}, {}
    for name, mask in masks.items():
        pts, complete, n = structure_points(mask, org, sp, rng)
        s = {"voxels": n, "complete": complete, "pts": pts if n >= MIN_VOX else None,
             "reason": None if n >= MIN_VOX else f"absent (< {MIN_VOX} voxels)"}
        if n >= MIN_VOX:
            s["centroid"] = np.round(pts.mean(0), 2).tolist()
            ci = np.round((pts - org) / sp).astype(int)[:, ::-1]
            s["mean_hu"] = round(float(vol[ci[:, 0], ci[:, 1], ci[:, 2]].mean()), 1)
        structures[name] = s
        levels[name] = level_record(name, spineps)
    if structures["sacrum"]["pts"] is None:
        return excluded(rec, "no TotalSegmentator sacrum")
    rec["structures"] = {k: dict({kk: vv for kk, vv in v.items() if kk != "pts"}, name=k, cls=1 if k == "sacrum" else 0, **levels[k])
                         for k, v in structures.items()}
    anchors = [structures[n]["pts"].mean(0) for n in CROP_ANCHORS if structures[n]["pts"] is not None]
    anchor = np.mean(anchors, axis=0)

    frames = sample_frames(nk)
    reals, _ = mha_frames(cdir / "projections.mha", frames)
    probe = [frames[i] for i in (0, len(frames) // 4, len(frames) // 2, 3 * len(frames) // 4)]
    sims = None
    simp = cdir / "projections_simulated.mha"
    if simp.is_file() and mha_header(simp)["_dims"] == ph["_dims"]:
        sims, _ = mha_frames(simp, probe)
    A = pixel_matrix(ox, oy, sx, sy)
    bx, by = blocks_for(sx, sy)
    W = world_map(SOLVED_MAP, iso)
    raw_bands = {k: exposed_rows(reals[k].astype(np.float64), project(A @ mats[k] @ W, iso[None])[1][0]) for k in frames}
    bands = sweep_bands(raw_bands)
    if np.median([b[1] - b[0] for b in bands.values()]) < 0.2 * nr:
        return excluded(rec, "no exposed band found")
    rec["collimation"] = {"exposed_rows_median": [int(np.median([b[0] for b in bands.values()])), int(np.median([b[1] for b in bands.values()]))],
                          "rows": nr}

    scores = map_scores(probe, reals, sims, mats, A, vol, org, sp, iso, nr, nc, bx, by, bands)
    passed, rec["axis_map"] = map_verdict(scores)
    rec["axis_map"].update(probe_frames=probe, block_px=[bx, by], solver_2026_09_23=solver_status(inp["solver"]))
    rec["map_scores"] = scores
    print(f"{case}: axis map edge NCC {rec['axis_map']['edge_ncc']:+.3f}, next {rec['axis_map']['next_best']:+.3f}, "
          f"margin {rec['axis_map']['margin']:+.3f}, authors' simulation {rec['axis_map']['edge_sim']} "
          f"({time.time() - t0:.0f} s)", flush=True)
    if not passed:
        return excluded(rec, f"axis map not confirmed: edge NCC {rec['axis_map']['edge_ncc']:.3f}, best other "
                             f"{rec['axis_map']['next_best']:.3f} (margin under {MAP_MARGIN}), best rows {rec['axis_map']['best_rows']}")

    flood, flood_rec = find_flood(cdir, md, nc, nr)
    if flood is None:
        return excluded(rec, flood_rec)
    D = np.diag([1.0 / bx, 1.0 / by, 1.0])
    fr = {}
    for k in frames:
        P_full = facing(A @ mats[k] @ W, iso)
        line, water, bone, hit, trunc = render(vol, org, sp, D @ P_full, nr // by, nc // bx)
        I = reals[k].astype(np.float64)
        edge, logc = frame_scores(block_mean(I, bx, by), line, hit, trunc, (bands[k][0] / by, bands[k][1] / by))
        air = air_mask(water, bone, hit, bx, by, I.shape, bands[k]) & (I > 0) & (flood > 0)
        n_air = int(air.sum())
        spread = flood_spread(I, flood, air)
        scale = float(np.median(I[air] / flood[air])) if n_air >= AIR_MIN_PX else None
        fr[k] = dict(P=P_full, edge=edge, log=logc, n_air=n_air, scale=scale, spread=spread)
    spreads = [f["spread"] for f in fr.values() if f["spread"][0] is not None]
    flood_rec["air_spread_as_stored"] = round(float(np.median([s[0] for s in spreads])), 4) if spreads else None
    flood_rec["air_spread_mirrored"] = round(float(np.median([s[1] for s in spreads])), 4) if spreads else None
    rec["flood"] = flood_rec
    if spreads and flood_rec["air_spread_mirrored"] < MIRROR_RATIO * flood_rec["air_spread_as_stored"]:
        return excluded(rec, "the air scan fits the frames' air better mirrored than as stored "
                             f"(spread {flood_rec['air_spread_mirrored']} against {flood_rec['air_spread_as_stored']}): "
                             "it is not the scan these frames were taken with, or not in their orientation")
    have = [f["scale"] for f in fr.values() if f["scale"] is not None]
    case_scale = float(np.median(have)) if have else None

    out = Path(out)
    for sub in ("images", "labels"):
        (out / sub / split).mkdir(parents=True, exist_ok=True)
    (out / "meta").mkdir(parents=True, exist_ok=True)
    for old in list((out / "meta").glob(f"{case}_*.json")):
        for p in (out / "images" / split / f"{old.stem}.png", out / "labels" / split / f"{old.stem}.txt", old):
            if p.exists():
                p.unlink()
    drops = {}
    rec["frames"] = []
    for k in frames:
        f = fr[k]
        I = reals[k].astype(np.float64)
        if f["scale"] is not None:
            scale, how = f["scale"], f"this frame: the median of I / F over {f['n_air']} pixels whose rays cross no tissue"
        elif case_scale is not None:
            scale, how = case_scale, f"the case's median over {len(have)} frames with air (this frame shows under {AIR_MIN_PX} air pixels)"
        else:
            ratio = I / np.clip(flood, 1, None)
            scale, how = float(np.percentile(ratio[I > 0], 99.9)), "the 99.9th percentile of I / F (no frame of the case shows air)"
        au, av = project(f["P"], anchor[None])
        crop = crop_window((au[0], av[0]), bands[k], nc, nr, sx, sy)
        c0, r0, w, h = crop
        a = attenuation(I[r0: r0 + h, c0: c0 + w], flood[r0: r0 + h, c0: c0 + w], scale)
        field = (I[r0: r0 + h, c0: c0 + w] > 0) & (flood[r0: r0 + h, c0: c0 + w] > 0)
        a_png = np.asarray(Image.fromarray(a.astype(np.float32), mode="F").resize((SIZE, SIZE), Image.BILINEAR), np.float64)
        f_png = np.asarray(Image.fromarray(field.astype(np.uint8) * 255).resize((SIZE, SIZE), Image.NEAREST)) > 0
        body = (a_png >= BODY_ATT) & f_png
        region, region_why = (body, "body") if body.sum() >= max(2000, int(0.02 * f_png.sum())) else (f_png, "field")
        u8 = np.clip(np.round(window_or(a_png, region)), 0, 255).astype(np.uint8)
        flip = cranial_down(png_matrix(f["P"], crop, False), iso)
        if flip:
            u8 = u8[::-1].copy()
        P_png = png_matrix(f["P"], crop, flip)
        K, ext = camera_from_matrix(P_png)
        q = K @ (ext @ np.array([*iso, 1.0]))[:3]
        xs, ys = project(P_png, iso[None])
        if abs(q[0] / q[2] - xs[0]) > 1e-3 or abs(q[1] / q[2] - ys[0]) > 1e-3:
            raise SystemExit(f"{case}/{k}: K and ext disagree with the projection matrix")
        directions = {}
        for nm, e_ in (("patient_left", [50.0, 0, 0]), ("posterior", [0, 50.0, 0]), ("superior", [0, 0, 50.0])):
            x1, y1 = project(P_png, (iso + e_)[None])
            directions[nm] = [round(float(x1[0] - xs[0]), 2), round(float(y1[0] - ys[0]), 2)]
        view = dict(gantry_deg=round(projections[k]["gantry"], 3), **view_of(mats[k] @ W, iso), image_px_per_50mm_at_iso=directions)
        boxes, lines = boxes_of(P_png, structures, levels, drops)
        stem = f"{case}_{k:04d}"
        Image.fromarray(u8).save(out / "images" / split / f"{stem}.png")
        (out / "labels" / split / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""))
        meta = {
            "dataset": DATASET, "case": case, "frame": f"{k:04d}", "split": split,
            "device": {"make": "Varian", "model": "on-board kV imager of a linac", "detector": md.get("Detector"), "bowtie": md.get("Bowtie"),
                       "kvp": md.get("TubeVoltage"), "ma": md.get("TubeCurrent"), "ms": md.get("PulseLength"), "fan": md.get("Fan"),
                       "trajectory": md.get("Trajectory"), "kv_filter": md.get("KVFilter"), "scatter_grid": md.get("ScatterGrid"),
                       "sid_mm": projections[k]["sid"], "sdd_mm": projections[k]["sdd"], "centre": case[0]},
            "source_image": f"{cdir / 'projections.mha'}#frame={k}", "stored_value": "linear (raw detector signal, bowtie in the beam)",
            "window_region": region_why,
            "conversion": ("a = -log(I / (s F)): I the stored uint16 signal clipped below at 1, F the air scan through the same bowtie "
                           f"({flood_rec['file']}), s = {how}. Cropped to rows [{r0}, {r0 + h}) and columns [{c0}, {c0 + w}) of the "
                           f"{nr}-row by {nc}-column detector, a square of the exposed band's height about the projected lumbosacral "
                           f"junction, resampled bilinear from {sx:g} x {sy:g} mm to {SIZE} x {SIZE} pixels of {w * sx / SIZE:.4f} mm; the "
                           f"display ladder (percentiles {list(OR_PCT)} onto {list(OR_GREY)}) over the {region_why} region"
                           f"{f' (attenuation >= {BODY_ATT})' if region_why == 'body' else ''}. Bone bright." + (" Flipped vertically so cranial is up." if flip else "")),
            "i0_scale": round(scale, 5), "i0_source": how, "air_px": f["n_air"], "px_mm": round(w * sx / SIZE, 5), "size": [SIZE, SIZE],
            "flip_v": flip, "crop_full_res": {"rows": [r0, r0 + h], "cols": [c0, c0 + w]},
            "view": view,
            "pose": {"source": "machine geometry (RTK parameters, checked against the shipped matrices)", "K": np.round(K, 6).tolist(),
                     "ext": np.round(ext, 6).tolist(),
                     "K_convention": "x = K @ (ext @ [p, 1])[:3], divide by x[2]; p in mm in ct_def.mha's frame (LPS, origin at the "
                                     "isocentre); x in pixels of THIS png with pixel (i, j) centred at (i + 0.5, j + 0.5)",
                     "axis_map_rows": SOLVED_MAP.astype(int).tolist(), "axis_map_margin": rec["axis_map"]["margin"],
                     "qc_edge_ncc": round(f["edge"], 4), "qc_log_ncc": None if f["log"] != f["log"] else round(f["log"], 4)},
            "boxes": boxes,
            "label_source": "TotalSegmentator 2.18.0 (anomaly harvest, task total; S1 merged into the sacrum) on ct_def.mha (planning CT "
                            "deformably registered to this CBCT), projected through pose; levels agreed with SPINEPS+VERIDAH",
            "notes": "box = 2nd-98th percentile extent of <= 20k projected mask voxels, clipped; vertebrae the CT does not contain whole "
                     "are skipped; level = the name both labellers agree on (Dice >= 0.5), else null.",
        }
        (out / "meta" / f"{stem}.json").write_text(json.dumps(meta, indent=1))
        rec["frames"].append(dict(stem=stem, gantry=round(projections[k]["gantry"], 2), lat=view["lat_from_ap_deg"], side=view["source_side"],
                                  edge=round(f["edge"], 4), log=None if f["log"] != f["log"] else round(f["log"], 4),
                                  scale_frame=f["scale"] is not None, air_px=f["n_air"], flip=flip, n_boxes=len(boxes),
                                  sacrum=any(b["cls"] == 1 for b in boxes), crop=[c0, r0, w, h]))
    rec["drops"] = drops
    rec["seconds"] = round(time.time() - t0, 1)
    edges = [x["edge"] for x in rec["frames"]]
    print(f"{case} [{split}]: {len(rec['frames'])} frames, {sum(x['n_boxes'] for x in rec['frames'])} boxes, sacrum in "
          f"{sum(x['sacrum'] for x in rec['frames'])}; frame edge NCC median {np.median(edges):.3f} min {np.min(edges):.3f}; "
          f"{rec['seconds']:.0f} s", flush=True)
    return rec


def case_list(a):
    cases = list(a.cases or [])
    if a.list:
        cases += [x.strip() for x in Path(a.list).read_text().splitlines() if x.strip()]
    cases = sorted(dict.fromkeys(cases))
    return [c for i, c in enumerate(cases) if i % a.n_shards == a.shard]


def cmd_export(a):
    out = Path(a.out)
    (out / "cases").mkdir(parents=True, exist_ok=True)
    failed = 0
    for case in case_list(a):
        dst = out / "cases" / f"{case}.json"
        if a.resume and dst.exists():
            continue
        try:
            rec = export_case(case, a.data, out)
        except Exception as exc:  # noqa: BLE001 -- one case's failure is recorded and the shard goes on
            import traceback
            failed += 1
            rec = {"case": case, "split": split_of(case), "centre": case[0], "status": "error", "reason": repr(exc)[:500],
                   "traceback": traceback.format_exc()[-2000:]}
            print(f"{case}: ERROR {exc!r}", flush=True)
        if rec["status"] != "ok":
            print(f"{case}: {rec['status'].upper()} -- {rec.get('reason')}", flush=True)
            for old in list((out / "meta").glob(f"{case}_*.json")) if (out / "meta").exists() else []:
                for p in (out / "images" / rec["split"] / f"{old.stem}.png", out / "labels" / rec["split"] / f"{old.stem}.txt", old):
                    if p.exists():
                        p.unlink()
        dst.write_text(json.dumps(rec, indent=1))
    return 0 if failed == 0 else 2


# ---------------------------------------------------------------- the summary that leaves the grid

def quantiles(values, qs=(0, 5, 25, 50, 75, 95, 100)):
    v = np.asarray([x for x in values if x is not None and x == x], float)
    return {f"p{q}": round(float(np.percentile(v, q)), 4) for q in qs} | {"n": int(len(v))} if len(v) else {"n": 0}


def views_of(lat):
    lat = abs(float(lat)) % 180.0
    lat = min(lat, 180.0 - lat)
    return "ap" if lat <= 15.0 else ("lat" if lat >= 75.0 else "oblique")


def solver_of(rec, solved):
    """The solver of 2026-09-23's word on a case: the record's own, else whether the case is on the list of the
    cases that solver confirmed (the first batch was run from that list before records carried the word)."""
    word = (rec.get("axis_map") or {}).get("solver_2026_09_23") if isinstance(rec.get("axis_map"), dict) else None
    return word or ("ok" if rec["case"] in solved else "not tried")


def summarise(out, solved_list=None):
    """Counts and distributions only: no frame, no path of a case, no header value."""
    out = Path(out)
    recs = [json.loads(p.read_text()) for p in sorted((out / "cases").glob("*.json"))]
    ok = [r for r in recs if r["status"] == "ok"]
    solved = set(Path(solved_list).read_text().split()) if solved_list else set()
    frames = [f for r in ok for f in r["frames"]]
    metas = [json.loads(p.read_text()) for p in sorted((out / "meta").glob("*.json"))]
    names = ["sacrum", *TS_LEVELS]
    s = {"dataset": DATASET, "builder": BUILDER, "frames_per_case": N_FRAMES, "map_margin": MAP_MARGIN,
         "split_rule": "int(md5(case).hexdigest(), 16) % 10: 0-6 train, 7 val, 8-9 test",
         "cases": {"attempted": len(recs), "ok": len(ok),
                   "refused": [{"case": r["case"], "status": r["status"], "why": r.get("reason")} for r in recs if r["status"] != "ok"]},
         "per_split": {sp: {"cases": sum(r["split"] == sp for r in ok), "frames": sum(m["split"] == sp for m in metas)} for sp in SPLITS},
         "per_centre": {c: {"cases": sum(r["centre"] == c for r in ok), "frames": sum(m["case"][0] == c for m in metas)} for c in "FG"},
         "by_chain": {},
         "axis_map": {"edge_ncc": quantiles([r["axis_map"]["edge_ncc"] for r in ok]),
                      "margin": quantiles([r["axis_map"]["margin"] for r in ok]),
                      "edge_ncc_authors_simulation": quantiles([r["axis_map"].get("edge_sim") for r in ok]),
                      "refused_margins": [{"case": r["case"], "margin": r["axis_map"]["margin"], "edge_ncc": r["axis_map"]["edge_ncc"]}
                                          for r in recs if r["status"] == "excluded" and r.get("axis_map") and isinstance(r["axis_map"], dict)]},
         "frame_edge_ncc": quantiles([f["edge"] for f in frames]) | {"below_0.5": sum(f["edge"] < 0.5 for f in frames)},
         "frame_log_ncc": quantiles([f["log"] for f in frames]),
         "views": {v: sum(views_of(f["lat"]) == v for f in frames) for v in ("ap", "lat", "oblique")},
         "frames_with_sacrum_box": sum(f["sacrum"] for f in frames),
         "boxes_by_level_agreed": {n: sum(b.get("level") == n for m in metas for b in m["boxes"]) for n in names},
         "boxes_by_level_ts": {n: sum(b.get("level_ts") == n for m in metas for b in m["boxes"]) for n in names},
         "frames_scale_from_own_air": sum(f["scale_frame"] for f in frames),
         "frames_flipped": sum(f["flip"] for f in frames),
         "flood_air_spread": {"as_stored": quantiles([r["flood"]["air_spread_as_stored"] for r in ok]),
                              "mirrored": quantiles([r["flood"]["air_spread_mirrored"] for r in ok])},
         "spineps_used": sum(r["labellers"]["spineps"] == "used" for r in ok),
         "levels_agreed_per_case": quantiles([sum(v.get("level_agree", False) for k, v in r["structures"].items() if k != "sacrum") for r in ok]),
         "by_solver_2026_09_23": {},
         "drops": {}}
    for r in recs:
        d = s["by_solver_2026_09_23"].setdefault(solver_of(r, solved), {"attempted": 0, "ok": 0})
        d["attempted"] += 1
        d["ok"] += r["status"] == "ok"
    for r in ok:
        m = r["metadata"]
        key = f"{m.get('Bowtie')} {m.get('ImagerSizeX')}x{m.get('ImagerSizeY')} at {m.get('ImagerResX')}x{m.get('ImagerResY')} mm"
        d = s["by_chain"].setdefault(key, {"cases": 0, "edge": []})
        d["cases"] += 1
        d["edge"].extend(f["edge"] for f in r["frames"])
        for k, v in (r.get("drops") or {}).items():
            s["drops"][k] = s["drops"].get(k, 0) + v
    for d in s["by_chain"].values():
        d["frame_edge_ncc_median"] = round(float(np.median(d.pop("edge"))), 4)
    (out / "summary.json").write_text(json.dumps(s, indent=1))
    return s


# ---------------------------------------------------------------- the proof renders' boxes, again

def cmd_proof(a):
    """The proof renders of 2026-09-23 drew SPINEPS body boxes through the shipped matrices and the solved map
    (cobra2026/varian/proof/overlay_summary.json). The same boxes are drawn here through the matrices this
    tool makes from the RTK parameters, sampling the mask voxels as that run did (one generator seeded 0 over
    the cases in order) and also from every voxel, and the largest difference in pixels is reported."""
    import nibabel as nib
    data = Path(a.data)
    varian = data / "cobra2026" / "varian"
    summary = json.loads((varian / "proof" / "overlay_summary.json").read_text())
    by_case = {}
    for row in summary:
        by_case.setdefault(row["case"], []).append(row)
    rng = np.random.default_rng(0)
    report = {"frames": 0, "boxes": 0, "max_diff_px_same_sampling": 0.0, "max_diff_px_all_voxels": 0.0, "cases": {}}
    for case in sorted(by_case):
        geom = json.loads((varian / "geom" / f"{case}.json").read_text())
        body = data / "spineps" / "bodies_cobra" / f"{case}_body_msk.nii.gz"
        if geom.get("status") != "ok" or not body.is_file():
            report["cases"][case] = {"skipped": "no solved geometry or no body mask"}
            continue
        cdir = data / "cobra2026" / "cases" / case
        projections = read_rtk_geometry(cdir / "geometry.xml")
        mats, worst = matrices_of(projections)
        ph = mha_header(cdir / "projections.mha")
        (ox, oy, _), (sx, sy, _) = ph["_offset"], ph["_spacing"]
        fh = mha_header(cdir / "fov_cbct.mha")
        iso = np.array(fh["_offset"]) + np.array(fh["_direction"]).reshape(3, 3) @ ((np.array(fh["_dims"], float) - 1) / 2.0 * np.array(fh["_spacing"]))
        W = world_map(np.array(geom["axis_map"], float), iso)
        A = pixel_matrix(ox, oy, sx, sy)
        img = nib.load(str(body))
        lps = np.diag([-1.0, -1.0, 1.0, 1.0]) @ img.affine
        bm = np.asarray(img.dataobj).transpose(2, 1, 0)
        sampled, whole = {}, {}
        for lid in [int(x) for x in np.unique(bm) if x > 0]:
            idx = np.argwhere(bm == lid)
            if len(idx) < 200:
                continue
            whole[lid] = (np.c_[idx[:, ::-1], np.ones(len(idx))] @ lps.T)[:, :3]
            if len(idx) > 20000:
                idx = idx[rng.choice(len(idx), 20000, replace=False)]
            sampled[lid] = (np.c_[idx[:, ::-1], np.ones(len(idx))] @ lps.T)[:, :3]
        diffs_s, diffs_w = [], []
        for row in by_case[case]:
            P = A @ mats[row["frame"]] @ W
            report["frames"] += 1
            for b in row["boxes"]:
                for pts, diffs in ((sampled, diffs_s), (whole, diffs_w)):
                    x, y = project(P, pts[b["level_id"]])
                    box = [*np.percentile(x, [2, 98]), *np.percentile(y, [2, 98])]
                    mine = [box[0], box[2], box[1], box[3]]
                    diffs.append(float(np.abs(np.array(mine) - np.array(b["box"])).max()))
                report["boxes"] += 1
        report["cases"][case] = {"matrix_disagreement": worst, "axis_map": geom["axis_map"], "frames": len(by_case[case]),
                                 "max_diff_px_same_sampling": round(max(diffs_s, default=0.0), 3),
                                 "max_diff_px_all_voxels": round(max(diffs_w, default=0.0), 3)}
        report["max_diff_px_same_sampling"] = max(report["max_diff_px_same_sampling"], max(diffs_s, default=0.0))
        report["max_diff_px_all_voxels"] = max(report["max_diff_px_all_voxels"], max(diffs_w, default=0.0))
    report["max_diff_px_same_sampling"] = round(report["max_diff_px_same_sampling"], 3)
    report["max_diff_px_all_voxels"] = round(report["max_diff_px_all_voxels"], 3)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "proof_check.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--data", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--cases", nargs="*")
    e.add_argument("--list")
    e.add_argument("--shard", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", 0)))
    e.add_argument("--n-shards", type=int, default=1)
    e.add_argument("--resume", action="store_true")
    p = sub.add_parser("proof")
    p.add_argument("--data", required=True)
    p.add_argument("--out", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--out", required=True)
    s.add_argument("--solved-list", help="the cases the solver of 2026-09-23 confirmed, for records made before they said so")
    a = ap.parse_args(argv)
    if a.cmd == "export":
        return cmd_export(a)
    if a.cmd == "proof":
        return cmd_proof(a)
    print(json.dumps(summarise(a.out, a.solved_list), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
