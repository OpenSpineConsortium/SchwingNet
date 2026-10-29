"""The gold tier census on the grid: one CPU job that reads what the grid holds and segments nothing.

Source: the thread "Complete gold tier 3 full-spine CT", 2026-10-29, for the owner's tap of 12:26 UTC on
"Send the 1 CPU job now": "The gate word's PR is merged once green and 1 CPU job is sent that reads only and
segments nothing". docs/research/gold3-ct/README.md section 7 names the job's parts; grid/gold3-census.sbatch
runs them in one job from its own copy of this file, tools/gold3_field.py and data/gold3-ct/, and the gate's
word `census gold3` queues it once. Confidential, like the rest of SchwingNet: what a part keeps stays under
its folder on the lab volume, and only the counts its lines print leave the grid, in the job's report.

The parts, each run as `python3 tools/gold3_census.py PART --data DATA_ROOT --rs RS --home HOME --out DIR`:

    ts142    the older list of 142 TotalSegmentator subjects, checked against its recorded sha256 and set beside
             the subjects rule 3 admits: in both, only in the old list, only in the field test's
    autopet  autoPET's CTs in TCIA's FDG-PET-CT-Lesions, matched to ENHANCE.PET's studies 0001 to 1014 by
             the grid of each, canonical shape and affine, since ENHANCE.PET names no TCIA patient; the map
             stays under DIR and gives the census's FDG rows the ENHANCE.PET study they repeat
    gold4    the field test (rule 3, the committed tables of data/gold3-ct/admission.json) over every SPINEPS
             mask the census's tier lists name: gold 4 where the field shows C2 to the sacrum, since a machine
             mask never raises a tier; counts by collection, VerSe and TotalSegmentator set beside the
             release masks' verdicts, the FDG rows that repeat an ENHANCE.PET study counted apart
    extent   every TotalSegmentator CT read whole: its grid against the facts, its padded planes (constant
             slices at either end of the head-foot axis) and the field test again with the CT's own planes
             in place of the cord's (named_study's planes); every verdict that changes, by subject
    held     the files held against the sums recorded here: ENHANCE.PET's vertebra and rib masks against
             SHA256SUMS, its CTs against the bucket's bytes and the facts' grids, VerSe's masks against the
             facts, TotalSegmentator's 54 files a subject against the facts' digest; the CTs' own sums are
             written under DIR and named in the report by a digest

Each part writes DIR/<part>.json, the detail that stays on the grid, and DIR/<part>.lines, the lines the
report carries: counts only, no path, no `name:value` without a space, at most LINE_CHARS characters.

The masks are read here by a NIfTI reader of numpy and the standard library, since the grid's train-cpu
environment has no nibabel and no scipy: it gives the header's affine, zooms and data type as nibabel 5.4.2
gives them (get_best_affine, the header's own fixes on load) and each label's voxels in the order bordercall's
holdings/fullspine_facts.py walks them, so the facts it makes are that reader's facts to the bit: on the
1,596 ENHANCE.PET vertebra masks the thread held on 2026-10-29, every grid, field and level fact it gave
equalled fullspine_facts' (bordercall c982f97, under nibabel 5.4.2), byte for byte as JSON. tests/
test_gold3_census.py holds the grid to nibabel's where nibabel is installed.
"""

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import re
import struct
import sys
import textwrap
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DATA = ROOT / "data/gold3-ct"
LINE_CHARS = 200
MM_DECIMALS, GRID_DECIMALS = 1, 6
# A mask is read a slab of about 16 million voxels at a time, as fullspine_facts reads it.
SLAB_VOXELS = 1 << 24
READ_BYTES = 1 << 22


def sibling(name):
    """A tool beside this one, loaded by path: tools/ is no package and never joins sys.path, since
    tools/profile.py would shadow the standard library's profile for anything imported after it."""
    file = TOOLS / f"{name}.py"
    found = sys.modules.get(name)
    if found is not None and getattr(found, "__file__", None) == str(file):
        return found
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------- a NIfTI-1 file, read as nibabel reads it


class NiftiError(ValueError):
    pass


# NIfTI-1's data types with a numeric numpy type (nibabel's nifti1._dtdefs); the others are not masks or CTs.
DATATYPES = {2: "u1", 4: "i2", 8: "i4", 16: "f4", 64: "f8", 256: "i1", 512: "u2", 768: "u4", 1024: "i8", 1280: "u8"}
XFORM_CODES = (0, 1, 2, 3, 4, 5)
SINGLE_MAGIC = b"n+1"
SINGLE_VOX_OFFSET = 352
QUATERNION_THRESHOLD = np.finfo(np.float32).eps * 3


class HashingReader:
    """A file read through, its bytes counted and hashed as they pass, so a CT is hashed in the same read
    that decompresses it."""

    def __init__(self, raw):
        self.raw, self.sha256, self.bytes = raw, hashlib.sha256(), 0

    def read(self, size=-1):
        data = self.raw.read(size)
        self.sha256.update(data)
        self.bytes += len(data)
        return data

    def finish(self):
        """The whole file's sha256 and size, once whatever the read left behind has passed too."""
        while self.read(READ_BYTES):
            pass
        return self.sha256.hexdigest(), self.bytes


def endian_of(block):
    """nibabel's guessed_endian, on this little-endian machine as on the grid's: dim[0] from 1 to 7 read
    little-endian says little-endian; 0 says big-endian only where sizeof_hdr reads 348 that way; anything
    else says big-endian. nibabel then fixes any sizeof_hdr, so the magic, not sizeof_hdr, is what refuses."""
    if struct.unpack("<i", block[:4])[0] == 540 or struct.unpack(">i", block[:4])[0] == 540:
        raise NiftiError("a NIfTI-2 header, which this reader does not read")
    dim0 = struct.unpack("<h", block[40:42])[0]
    if dim0 == 0:
        return ">" if struct.unpack(">i", block[:4])[0] == 348 else "<"
    return "<" if 1 <= dim0 <= 7 else ">"


def header_of(block):
    """The fields of a 348-byte header that the facts read, with nibabel's fixes on load (check_fix):
    zero spatial pixdims set to 1 and negative ones to their size, qfac set to 1 unless it is 1 or -1, an
    unknown qform or sform code set to 0. What nibabel refuses on load (its problem level 40 and over) is
    refused too: a magic that is not NIfTI-1's, and a single file's voxel offset below 352. Two cases
    nibabel would read are refused here as well, since every file the census reads is one .nii or .nii.gz:
    the pair magic ni1, whose voxels are in another file, and an offset of 0, which nibabel reads from the
    file's first byte, so that the voxels would be the header's own bytes."""
    if len(block) < 348:
        raise NiftiError("a header shorter than 348 bytes")
    e = endian_of(block)
    dim = list(struct.unpack(e + "8h", block[40:56]))
    datatype = struct.unpack(e + "h", block[70:72])[0]
    pixdim = np.frombuffer(block[76:108], dtype=e + "f4").astype(np.float32)
    spatial = pixdim[1:4]
    spatial[spatial == 0] = 1
    pixdim[1:4] = np.abs(spatial)
    if pixdim[0] not in (-1, 1):
        pixdim[0] = 1
    magic = block[344:347]
    if magic != SINGLE_MAGIC or block[347:348] != b"\0":
        raise NiftiError("a header whose magic is not a single NIfTI-1 file's")
    offset = float(np.frombuffer(block[108:112], dtype=e + "f4")[0])
    if not np.isfinite(offset) or offset < SINGLE_VOX_OFFSET:
        raise NiftiError("a single file's voxel offset below 352")
    qform_code, sform_code = struct.unpack(e + "2h", block[252:256])
    return {"endian": e, "dim": dim, "datatype": datatype, "pixdim": pixdim, "vox_offset": int(offset),
            "slope": np.frombuffer(block[112:116], dtype=e + "f4")[0], "inter": np.frombuffer(block[116:120], dtype=e + "f4")[0],
            "qform_code": qform_code if qform_code in XFORM_CODES else 0,
            "sform_code": sform_code if sform_code in XFORM_CODES else 0,
            "quatern": np.frombuffer(block[256:268], dtype=e + "f4"), "qoffset": np.frombuffer(block[268:280], dtype=e + "f4"),
            "srow": np.frombuffer(block[280:328], dtype=e + "f4").reshape(3, 4), "magic": magic}


def quaternion(bcd):
    """nibabel's quaternions.fillpositive in the widest float, w taken positive."""
    xyz = np.asarray(list(bcd), dtype=np.longdouble)
    w2 = 1.0 - xyz @ xyz
    if np.abs(w2) < np.abs(QUATERNION_THRESHOLD):
        w = 0
    elif w2 < 0:
        raise NiftiError(f"a qform quaternion whose w squared is negative ({float(w2):e})")
    else:
        w = np.sqrt(w2)
    return np.r_[w, xyz]


def rotation(q):
    """nibabel's quaternions.quat2mat."""
    w, x, y, z = q
    nq = w * w + x * x + y * y + z * z
    if nq < np.finfo(float).eps:
        return np.eye(3)
    s = 2.0 / nq
    X, Y, Z = x * s, y * s, z * s
    wX, wY, wZ = w * X, w * Y, w * Z
    xX, xY, xZ = x * X, x * Y, x * Z
    yY, yZ, zZ = y * Y, y * Z, z * Z
    return np.array([[1.0 - (yY + zZ), xY - wZ, xZ + wY],
                     [xY + wZ, 1.0 - (xX + zZ), yZ - wX],
                     [xZ - wY, yZ + wX, 1.0 - (xX + yY)]])


def qform_affine(h):
    vox = h["pixdim"][1:4].copy()
    vox[-1] *= h["pixdim"][0]
    out = np.eye(4)
    out[0:3, 0:3] = np.dot(rotation(quaternion(h["quatern"])), np.diag(vox))
    out[0:3, 3] = h["qoffset"]
    return out


def base_affine(h):
    """nibabel's shape_zoom_affine for an Analyze-style header: the image's centre at the origin, x flipped."""
    ndim = h["dim"][0]
    shape = np.asarray(h["dim"][1:ndim + 1])[:3].astype(float)
    zooms = np.array(h["pixdim"][1:ndim + 1])[:3]
    zooms[0] *= -1
    aff = np.eye(4)
    aff[:3, :3] = np.diag(zooms)
    aff[:3, -1] = -(shape - 1) / 2.0 * zooms
    return aff


def best_affine(h):
    """nibabel's get_best_affine: the sform where its code says so, else the qform, else the base affine."""
    if h["sform_code"] != 0:
        out = np.eye(4)
        out[:3, :] = h["srow"]
        return out
    if h["qform_code"] != 0:
        return qform_affine(h)
    return base_affine(h)


def shape_of(h):
    ndim = h["dim"][0]
    if not 3 <= ndim <= 7:
        raise NiftiError(f"a volume of {ndim} dimensions")
    shape = tuple(int(n) for n in h["dim"][1:ndim + 1])
    if any(n < 1 for n in shape):
        raise NiftiError(f"a shape with an empty axis {shape}")
    if any(n != 1 for n in shape[3:]):
        raise NiftiError(f"more than one volume in the file {shape}")
    return shape[:3]


def dtype_of(h):
    code = DATATYPES.get(h["datatype"])
    if code is None:
        raise NiftiError(f"data type {h['datatype']}, which is no numeric type of NIfTI-1")
    return np.dtype(h["endian"] + code)


def scaling_of(h):
    """nibabel's get_slope_inter: none where the slope is 0 or not finite."""
    slope, inter = float(h["slope"]), float(h["inter"])
    if slope == 0 or not np.isfinite(slope):
        return None, None
    if not np.isfinite(inter):
        raise NiftiError(f"a valid slope with an intercept of {inter}")
    return slope, inter


class Volume:
    """One NIfTI-1 file open for one pass: its header, affine and grid, and its voxels a slab at a time along
    the slowest axis, as nibabel's array proxy gives them (scaled where the header says so)."""

    def __init__(self, path, hashed=False):
        self.path = str(path)
        self.file = open(self.path, "rb")
        try:
            self._open(hashed)
        except BaseException:
            self.file.close()
            raise

    def _open(self, hashed):
        self.hashing = HashingReader(self.file) if hashed else None
        raw = self.hashing or self.file
        start = self.file.read(2) if not hashed else raw.read(2)
        if not hashed:
            self.file.seek(0)
        self.stream = gzip.GzipFile(fileobj=_Prefixed(start, raw) if hashed else raw) if start == b"\x1f\x8b" \
            else (_Prefixed(start, raw) if hashed else raw)
        block = self._read(348)
        self.header = header_of(block)
        self.used = 348
        self.shape = shape_of(self.header)
        self.dtype = dtype_of(self.header)
        self.affine = best_affine(self.header)
        self.zooms = tuple(self.header["pixdim"][1:self.header["dim"][0] + 1])[:3]
        self.scaling = scaling_of(self.header)

    def _read(self, size):
        data = self.stream.read(size)
        while len(data) < size:
            more = self.stream.read(size - len(data))
            if not more:
                raise NiftiError(f"the file ends {size - len(data)} bytes early")
            data += more
        return data

    def slabs(self):
        """(start, slab) along axis 2, each slab at most SLAB_VOXELS voxels or one plane, in file order."""
        skip = max(0, self.header["vox_offset"] - self.used)
        while skip:
            skip -= len(self._read(min(skip, READ_BYTES)))
        plane = self.shape[0] * self.shape[1]
        step = max(1, SLAB_VOXELS // plane)
        for start in range(0, self.shape[2], step):
            stop = min(start + step, self.shape[2])
            raw = self._read(plane * (stop - start) * self.dtype.itemsize)
            slab = np.frombuffer(raw, dtype=self.dtype).reshape((self.shape[0], self.shape[1], stop - start), order="F")
            if stop == self.shape[2]:
                self.drained()
            yield start, self.scaled(slab)

    def drained(self):
        """A gzip stream read to its end, so gzip checks its CRC32 and length and a damaged file raises
        BadGzipFile rather than giving changed voxels; bytes past the voxels, rare in NIfTI, are read and
        dropped."""
        if isinstance(self.stream, gzip.GzipFile):
            while self.stream.read(READ_BYTES):
                pass

    def scaled(self, slab):
        """nibabel's apply_read_scaling: the raw values where the scaling is (1, 0), else in float64."""
        slope, inter = self.scaling
        if slope is None or (slope, inter) == (1, 0):
            return slab
        out = slab.astype(np.float64)
        if slope != 1.0:
            out = out * slope
        if inter != 0.0:
            out = out + inter
        return out

    def finish(self):
        """The file's sha256 and size, where it was opened to be hashed; the file is closed either way."""
        try:
            return self.hashing.finish() if self.hashing else None
        finally:
            self.file.close()

    def close(self):
        self.file.close()


class _Prefixed:
    """A stream whose first bytes were already read to tell gzip from a plain file."""

    def __init__(self, head, rest):
        self.head, self.rest = head, rest

    def read(self, size=-1):
        if not self.head:
            return self.rest.read(size)
        if size is None or size < 0:
            out, self.head = self.head + self.rest.read(), b""
            return out
        out, self.head = self.head[:size], self.head[size:]
        if len(out) < size:
            out += self.rest.read(size - len(out))
        return out


def header_only(path):
    """A file's grid alone, read from its first bytes: shape, affine, zooms and data type."""
    volume = Volume(path)
    try:
        return {"shape": list(volume.shape), "affine": volume.affine, "zooms": volume.zooms, "dtype": volume.dtype}
    finally:
        volume.close()


# ---------------------------------------------------------------- the facts, as fullspine_facts gives them


OPPOSITE = {"L": "R", "R": "L", "A": "P", "P": "A", "S": "I", "I": "S"}


def rounded(value, decimals):
    return round(float(value), decimals) + 0.0


def rounded_list(values, decimals):
    return [rounded(v, decimals) for v in values]


def io_orientation(affine):
    """nibabel 5.4.2's io_orientation without its tolerance argument: each voxel axis's world axis and sign."""
    affine = np.asarray(affine)
    q, p = affine.shape[0] - 1, affine.shape[1] - 1
    rzs = affine[:q, :p]
    zooms = np.sqrt(np.sum(rzs * rzs, axis=0))
    zooms[zooms == 0] = 1
    rs = rzs / zooms
    P, S, Qs = np.linalg.svd(rs, full_matrices=False)
    tol = S.max() * max(rs.shape) * np.finfo(S.dtype).eps
    keep = S > tol
    R = np.dot(P[:, keep], Qs[keep])
    ornt = np.ones((p, 2), dtype=np.int8) * np.nan
    for in_ax in np.argsort(np.min(-(R ** 2), axis=0), kind="stable"):
        col = R[:, in_ax]
        if not np.allclose(col, 0):
            out_ax = np.argmax(np.abs(col))
            ornt[in_ax, 0] = out_ax
            ornt[in_ax, 1] = -1 if col[out_ax] < 0 else 1
            R[out_ax, :] = 0
    return ornt


def axcodes_of(affine):
    """nibabel's aff2axcodes with RAS's labels."""
    labels = list(zip("LPI", "RAS"))
    out = []
    for axis, direction in io_orientation(affine):
        if np.isnan(axis):
            out.append(None)
            continue
        out.append(labels[int(np.round(axis))][1 if direction == 1 else 0])
    return tuple(out)


def head_foot_axis(affine):
    return int(np.argmax(np.abs(np.asarray(affine)[2, :3])))


def field_edges(shape, affine):
    row = np.asarray(affine, float)[2]
    corners = np.array([[i, j, k, 1.0] for i in (-0.5, shape[0] - 0.5) for j in (-0.5, shape[1] - 0.5)
                        for k in (-0.5, shape[2] - 0.5)])
    heights = corners @ row
    return float(heights.max()), float(heights.min())


def grid_facts(volume):
    return {"shape": [int(n) for n in volume.shape],
            "zooms": rounded_list(volume.zooms, GRID_DECIMALS),
            "affine": [rounded_list(row, GRID_DECIMALS) for row in np.asarray(volume.affine, float)],
            "axcodes": "".join(axcodes_of(volume.affine)),
            "head_foot_axis": head_foot_axis(volume.affine),
            "dtype": str(volume.dtype)}


def field_facts(volume):
    top, bottom = field_edges(volume.shape, volume.affine)
    return {"top": rounded(top, MM_DECIMALS), "bottom": rounded(bottom, MM_DECIMALS)}


def world_points(points, affine):
    affine = np.asarray(affine, float)
    return points @ affine[:3, :3].T + affine[:3, 3]


def faces_touched(points, shape, affine):
    out = []
    for axis, code in enumerate(axcodes_of(affine)):
        if points[:, axis].min() == 0:
            out.append(OPPOSITE[code])
        if points[:, axis].max() == shape[axis] - 1:
            out.append(code)
    return sorted(out)


def label_facts(points, affine, shape):
    """A level's facts as fullspine_facts gives them, less its pieces, which the field test does not read."""
    world = world_points(points, affine)
    return {"voxels": int(len(points)), "faces": faces_touched(points, shape, affine),
            "top_mm": rounded(world[:, 2].max(), MM_DECIMALS),
            "bottom_mm": rounded(world[:, 2].min(), MM_DECIMALS),
            "centroid_mm": rounded_list(world.mean(0), MM_DECIMALS)}


def slab_points(start, slab):
    """(values, indices) of one slab's labelled voxels in Fortran order, its indices in the whole volume."""
    if slab.dtype.kind == "f":
        slab = np.rint(slab).astype(np.int32)
    flat = slab.ravel(order="F")
    where = np.flatnonzero(flat)
    points = np.stack(np.unravel_index(where, slab.shape, order="F"), axis=1).astype(np.int32)
    points[:, 2] += start
    return flat[where], points


def voxel_points(volume):
    """{label: (n, 3) int32 indices} of every nonzero label, in the order fullspine_facts' voxel_points gives."""
    parts = {}
    for start, slab in volume.slabs():
        values, points = slab_points(start, slab)
        for label in np.unique(values):
            parts.setdefault(int(label), []).append(points[values == label])
    return {label: np.concatenate(chunks) for label, chunks in sorted(parts.items())}


# ---------------------------------------------------------------- what every part shares


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def n(value):
    return f"{value:,}"


def grouped(hexdigest):
    """The first 16 hex digits of a digest in groups of four, short enough that no masking takes them for a
    key and long enough to tell two sums files apart."""
    return " ".join(hexdigest[i:i + 4] for i in range(0, 16, 4))


def sha256_of(path):
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(READ_BYTES), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def file_sums(path):
    """(sha256, bytes) of one file, or the kind of error that stopped the read, for a worker."""
    try:
        return sha256_of(path)
    except OSError as error:
        return type(error).__name__, None


def error_kind(error):
    """An error's kind without its message, which may name a path."""
    return type(error).__name__


def walk_files(root, keep):
    """{name: [paths]} of the files under root whose name keep() admits, symbolic links to folders not followed."""
    found = defaultdict(list)
    for folder, _, names in os.walk(root):
        for name in names:
            if keep(name):
                found[name].append(os.path.join(folder, name))
    return found


def first_root(*candidates):
    return next((Path(c) for c in candidates if c and Path(c).is_dir()), None)


def wrapped(head, items, width=LINE_CHARS - 2):
    """Lines of at most width characters: head, then the items comma-separated, continued under the same head."""
    lines, line = [], head
    for item in items:
        piece = (", " if line != head else " ") + item
        if len(line) + len(piece) > width:
            lines.append(line)
            line = head + " " + item
        else:
            line += piece
    lines.append(line)
    return lines


def write_sums(path, sums):
    """A sums file in sha256sum's layout, sorted by name in C order; its own sha256."""
    text = "".join(f"{sha}  {name}\n" for name, sha in sorted(sums.items()))
    Path(path).write_text(text, encoding="ascii")
    return hashlib.sha256(text.encode("ascii")).hexdigest()


class Part:
    """One part's lines for the report and its detail for the grid."""

    def __init__(self, name, out):
        self.name, self.out, self.lines, self.detail = name, Path(out), [], {}

    def say(self, text):
        """Lines of at most LINE_CHARS with the report's "- " before them, a longer one wrapped at its words."""
        for line in text.splitlines():
            self.lines.extend(textwrap.wrap(line, width=LINE_CHARS - 2, subsequent_indent="  ") or [""])

    def save(self):
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / f"{self.name}.json").write_text(json.dumps(self.detail, indent=1, sort_keys=True, default=str) + "\n")
        (self.out / f"{self.name}.lines").write_text("".join(line + "\n" for line in self.lines), encoding="ascii", errors="replace")


def pool(workers):
    return ProcessPoolExecutor(max_workers=max(1, workers))


def admission():
    return read_json(DATA / "admission.json")


def admitted_ids(member):
    return {s["id"] for s in admission()["studies"] if s["member"] == member and s["verdict"] == "admitted"}


# ---------------------------------------------------------------- ts142: the older list beside rule 3's


TS_ID = re.compile(r"\bs\d{4}\b")


def part_ts142(args):
    part = Part("ts142", args.out)
    record = read_json(DATA / "totalsegmentator.json")
    path = Path(args.home) / "model_night/ts_clean_subjects.txt"
    if not path.is_file():
        part.say("ts142: the older list is not where its record names it, under the home folder's model_night")
        part.save()
        return part
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    old = set(TS_ID.findall(data.decode("ascii", "replace")))
    studies = {s["id"]: s for s in admission()["studies"] if s["member"] == "totalsegmentator"}
    new = {i for i, s in studies.items() if s["verdict"] == "admitted"}
    both, old_only, new_only, unknown = old & new, old - new, new - old, old - set(studies)
    part.detail = {"sha256": sha, "matches_record": sha == record["subject_list"]["sha256"], "ids": sorted(old),
                   "both": sorted(both), "old_only": sorted(old_only), "new_only": sorted(new_only), "unknown": sorted(unknown)}
    part.say(f"ts142: the older list names {n(len(old))} subjects (its record says {n(record['count'])}); its sha256 "
             + ("matches the record" if sha == record["subject_list"]["sha256"] else f"is {grouped(sha)}, not the record's"))
    part.say(f"ts142: in both {n(len(both))}; only in the older list {n(len(old_only))}; only among rule 3's "
             f"{n(len(new))} admitted {n(len(new_only))}; ids not among the release's {n(len(studies))} subjects {n(len(unknown))}")
    reasons = [f"{i} (head {studies[i]['head']}, foot {studies[i]['foot']})" for i in sorted(old_only - unknown)]
    for line in wrapped("ts142: only in the older list, with rule 3's ends:", reasons) if reasons else []:
        part.say(line)
    for line in wrapped("ts142: only among rule 3's admitted:", sorted(new_only)) if new_only else []:
        part.say(line)
    part.save()
    return part


# ---------------------------------------------------------------- autopet: autoPET's CTs matched to ENHANCE.PET's studies


PETCT = re.compile(r"PETCT_[0-9a-f]+", re.IGNORECASE)
NOT_CT_TOKENS = {"seg", "pet", "suv", "mask", "label", "pt", "msk"}
# Two grids are one when every corner voxel's centre lies within this of the other's: the facts round an
# affine to a millionth, so a CT and its mask agree far inside it, and two scans of one person never do.
MATCH_MM = 0.01
RESIDUAL_BINS = (0.1, 1.0, 10.0)


def canonical_grid(shape, affine):
    """(shape, affine) with the voxel axes turned to RAS's order and sense, so a grid stored LAS and the same
    grid stored RAS compare equal: each axis taken to the world axis io_orientation gives it, and flipped
    with its origin moved to the far end where its sense is negative."""
    affine = np.asarray(affine, float)
    out, sizes, origin = np.eye(4), [0, 0, 0], affine[:3, 3].copy()
    for axis, (world, sense) in enumerate(io_orientation(affine)):
        column = affine[:3, axis]
        if sense < 0:
            origin = origin + column * (shape[axis] - 1)
            column = -column
        out[:3, int(world)] = column
        sizes[int(world)] = int(shape[axis])
    out[:3, 3] = origin
    return tuple(sizes), out


def corner_centres(shape, affine):
    corners = np.array([[i, j, k, 1.0] for i in (0, shape[0] - 1) for j in (0, shape[1] - 1) for k in (0, shape[2] - 1)])
    return corners @ np.asarray(affine, float).T


def grid_residual(first, second):
    """How far apart two canonical grids of one shape put their corner voxels, in mm."""
    return float(np.abs(corner_centres(first[0], first[1]) - corner_centres(second[0], second[1])).max())


def looks_like_ct(name):
    if not name.endswith((".nii.gz", ".nii")):
        return False
    tokens = set(re.split(r"[_.\-]+", name.lower()))
    return bool(tokens & {"ct", "ctres"}) and not tokens & NOT_CT_TOKENS


def fdg_cases(data):
    """[(case, ct path)] of FDG-PET-CT-Lesions' CTs as NIfTI and what listed them: the acquisition screen's
    cases.csv, as tools/anomaly_pack.py reads a harvest collection, else a walk of the set's folder."""
    harvest = Path(data) / "anomaly_harvest"
    for screen in sorted(harvest.glob("*fdg*")) if harvest.is_dir() else []:
        table = screen / "cases.csv"
        if table.is_file():
            with open(table, encoding="utf-8", newline="") as handle:
                listed = [(r.get("case", ""), r.get("ct", "")) for r in csv.DictReader(handle)]
            return [(case, ct) for case, ct in listed if ct], "the acquisition screen's cases.csv"
    root = Path(data) / "tcia_fdg_pet_ct_lesions"
    if not root.is_dir():
        return [], "nothing (no screen's cases.csv and no set folder)"
    found = walk_files(root, looks_like_ct)
    return [(os.path.relpath(path, root), path) for name in sorted(found) for path in sorted(found[name])], \
        "a walk of the set's folder"


def ct_grid(path):
    """One CT's grid as read and turned canonical, or the kind of error that stopped it: any error, since a
    damaged file can raise what no list foresees (zlib.error is no OSError) and one file must never end the
    part."""
    try:
        grid = header_only(path)
        shape, affine = list(grid["shape"]), np.asarray(grid["affine"], float)
        return {"shape": shape, "affine": affine.tolist(), "canonical": canonical_grid(shape, affine)}
    except Exception as error:  # noqa: BLE001
        return {"error": error_kind(error)}


def autopet_rows():
    """ENHANCE.PET's autoPET studies as its facts give them, each on its published mask's grid."""
    return [r for r in read_jsonl(DATA / "enhance-pet/facts.jsonl") if r.get("site") == "autoPET" and "repaired_from" not in r]


def person_of(*texts):
    for text in texts:
        found = PETCT.search(text or "")
        if found:
            return "PETCT_" + found.group(0)[6:].lower()
    return None


def nearest_ct(study_grid, by_shape, grids):
    """(residual mm, index) of every CT of the study's shape, nearest first."""
    shape, _ = study_grid
    return sorted((grid_residual(study_grid, grids[i]), i) for i in by_shape.get(shape, []))


def match_studies(rows, cases, grids):
    by_shape = defaultdict(list)
    for index, grid in enumerate(grids):
        if grid is not None:
            by_shape[grid[0]].append(index)
    matches, bins = {}, Counter()
    for row in rows:
        near = nearest_ct(canonical_grid(row["mask"]["shape"], row["mask"]["affine"]), by_shape, grids)
        if not near:
            bins["no CT of the same shape"] += 1
            continue
        residual, index = near[0]
        within = sum(1 for r, _ in near if r <= MATCH_MM)
        if within == 1:
            case, ct = cases[index]
            matches[row["id"]] = {"case": case, "ct": ct, "residual_mm": residual, "person": person_of(case, ct)}
            bins["matched"] += 1
        elif within > 1:
            bins["within the match of several CTs"] += 1
        else:
            bins[next((f"nearest within {b:g} mm" for b in RESIDUAL_BINS if residual <= b), "nearest farther than 10 mm")] += 1
    return matches, bins


def part_autopet(args):
    part = Part("autopet", args.out)
    cases, source = fdg_cases(args.data)
    with pool(args.workers) as ex:
        read = list(ex.map(ct_grid, [ct for _, ct in cases], chunksize=8))
    grids = [None if "error" in g else g["canonical"] for g in read]
    errors = Counter(g["error"] for g in read if "error" in g)
    rows = autopet_rows()
    matches, bins = match_studies(rows, cases, grids)
    reused = Counter(m["ct"] for m in matches.values())
    gold = {s["id"] for s in admission()["studies"] if s["member"] == "enhance_pet" and s["verdict"] == "admitted"}
    persons = {m["person"] for m in matches.values() if m["person"]}
    gold_persons = {m["person"] for i, m in matches.items() if m["person"] and i in gold}
    part.detail = {"source": source, "cases": len(cases), "unreadable": dict(errors), "bins": dict(bins),
                   "matches": matches, "ct_of_case": {case: ct for case, ct in cases}}
    part.say(f"autopet: FDG-PET-CT-Lesions CTs as NIfTI {n(len(cases))}, listed by {source}; unreadable {n(sum(errors.values()))}"
             + (f" ({', '.join(f'{k} {v}' for k, v in sorted(errors.items()))})" if errors else ""))
    part.say(f"autopet: ENHANCE.PET autoPET studies {n(len(rows))}; " + ", ".join(f"{k} {n(v)}" for k, v in sorted(bins.items())))
    part.say(f"autopet: CTs matched by more than one study {n(sum(1 for c in reused.values() if c > 1))}; matched studies "
             f"whose case and file name hold no PETCT key {n(sum(1 for m in matches.values() if not m['person']))}")
    part.say(f"autopet: persons of the matched studies {n(len(persons))}; of the matched gold 3 studies "
             f"{n(len(gold_persons))} (members.json gives 865 to 900 for autoPET's gold 3)")
    part.save()
    return part


# ---------------------------------------------------------------- gold4: the field test over the census's SPINEPS masks


TIER_FILES = ("tier1.tsv", "tier2.tsv")
TIER_COLUMNS = ("tier", "collection", "case_id", "person_key", "spineps_vert", "spineps_ids")
# The census masks' ids are VerSe's (tools/bordercall_corpus.py NAMES): 26 and 29 are both the sacrum.
VERSE_NAMES = {**{i: f"C{i}" for i in range(1, 8)}, **{7 + i: f"T{i}" for i in range(1, 13)},
               **{19 + i: f"L{i}" for i in range(1, 7)}, 26: "sacrum", 28: "T13", 29: "sacrum"}
MEMBER_OF_COLLECTION = (("verse", "verse"), ("totalseg", "totalsegmentator"), ("ts_", "totalsegmentator"))
VERSE_ID = re.compile(r"(verse\d+|gl\d+)", re.IGNORECASE)
COLLECTION_LINES = 40
_TABLES = {}


def census_rows(rs):
    """Every row of the census's two tier lists that names a SPINEPS mask, once per mask, in a fixed order."""
    rows, seen = [], set()
    for name in TIER_FILES:
        path = Path(rs) / "ruleclass/tiers" / name
        if not path.is_file():
            continue
        with open(path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                mask = row.get("spineps_vert") or ""
                if mask and mask not in seen:
                    seen.add(mask)
                    rows.append({k: row.get(k) or "" for k in TIER_COLUMNS})
    rows.sort(key=lambda r: (r["tier"], r["collection"], r["case_id"]))
    return rows


def tables():
    if "head" not in _TABLES:
        _TABLES.update(admission()["tables"])
    return _TABLES


def member_of(collection):
    low = collection.lower()
    return next((member for prefix, member in MEMBER_OF_COLLECTION if low.startswith(prefix)), None)


def member_id(member, case):
    """The release id a census case of VerSe or TotalSegmentator names, in admission.json's spelling."""
    if member == "totalsegmentator":
        found = TS_ID.search(case.replace("TS_", " "))
        return found.group(0) if found else None
    found = VERSE_ID.search(case)
    return found.group(1).lower() if found else None


def level_facts(volume):
    """{level name: facts} of a census mask, VerSe's ids read as names, and how many ids it holds outside them."""
    named, outside = defaultdict(list), 0
    for label, points in voxel_points(volume).items():
        name = VERSE_NAMES.get(label)
        if name is None:
            outside += 1
        else:
            named[name].append(points)
    return {name: label_facts(np.concatenate(parts), volume.affine, volume.shape) for name, parts in named.items()}, outside


def gold4_one(row):
    """One census mask through the field test; the reason it was set aside, or the error that stopped it."""
    if row["spineps_ids"] == "raw":
        return {"set_aside": "raw ids, which only spinesurg-ct-nnunet's guard relabels"}
    if not os.path.isfile(row["spineps_vert"]):
        return {"set_aside": "no mask file at the path the census lists"}
    try:
        volume = Volume(row["spineps_vert"])
        try:
            levels, outside = level_facts(volume)
            grid, field = grid_facts(volume), field_facts(volume)
        finally:
            volume.close()
    # Any error, counted by its kind: a damaged file can raise what no list foresees, and one of 17,000
    # masks must never end the part.
    except Exception as error:  # noqa: BLE001
        return {"error": error_kind(error)}
    G = sibling("gold3_field")
    try:
        study = G.named_study({"member": "census", "id": row["case_id"], "grid": grid, "field_mm": field,
                               "levels": levels, "context": {}}, row["person_key"] or None, None, None)
        judged = G.judge(study, tables())
    # One mask the field test cannot judge is counted by the kind of error, never stops the other 17,000.
    except Exception as error:  # noqa: BLE001
        return {"error": f"the field test refused it, {error_kind(error)}"}
    return {k: judged[k] for k in ("verdict", "head", "foot", "complete", "flags")} | {"outside_ids": outside}


def is_fdg(collection):
    """FDG-PET-CT-Lesions under any of the census's spellings: its 1,014 studies are ENHANCE.PET's autoPET site
    under TCIA's names, so none of them is new to the dataset whatever the match finds."""
    return "fdg" in collection.lower()


def folded(collection):
    return "idc" if collection.lower().startswith("idc_") else collection


def fdg_studies(out):
    """{census case: ENHANCE.PET study} from the autopet part's match, where it ran."""
    path = Path(out) / "autopet.json"
    if not path.is_file():
        return None
    detail = read_json(path)
    ct_of = detail.get("ct_of_case", {})
    study_of_ct = {m["ct"]: study for study, m in detail.get("matches", {}).items()}
    return {case: study_of_ct[ct] for case, ct in ct_of.items() if ct in study_of_ct}


def gold4_counts(rows, results, repeats):
    by = defaultdict(Counter)
    persons = defaultdict(set)
    agree = defaultdict(Counter)
    released = {(s["member"], s["id"]): s["verdict"] for s in admission()["studies"]}
    ends, flags, new = Counter(), Counter(), {"studies": 0, "persons": set()}
    for row, result in zip(rows, results):
        collection, member = folded(row["collection"]), member_of(row["collection"])
        by[collection]["rows"] += 1
        if "set_aside" in result or "error" in result:
            by[collection]["set aside" if "set_aside" in result else "unreadable"] += 1
            continue
        by[collection][result["verdict"]] += 1
        if result["verdict"] == "admitted":
            persons[collection].add(row["person_key"] or f"case:{row['collection']}:{row['case_id']}")
        if member:
            ident = member_id(member, row["case_id"])
            agree[member][(released.get((member, ident), "no row"), result["verdict"])] += 1
            continue
        if is_fdg(row["collection"]) and repeats and row["case_id"] in repeats:
            agree["enhance_pet"][(released.get(("enhance_pet", repeats[row["case_id"]]), "no row"), result["verdict"])] += 1
        if result["verdict"] != "admitted":
            continue
        if is_fdg(row["collection"]):
            matched = repeats is not None and row["case_id"] in repeats
            by[collection]["admitted, matched to its ENHANCE.PET study by grid" if matched else "admitted, unmatched"] += 1
            continue
        new["studies"] += 1
        new["persons"].add(row["person_key"] or f"case:{row['collection']}:{row['case_id']}")
        ends[(result["head"], result["foot"])] += 1
        flags.update(result["flags"])
    return by, persons, agree, ends, flags, new


def say_gold4(part, rows, results, counts):
    by, persons, agree, ends, flags, new = counts
    reasons = Counter(r.get("set_aside") or r.get("error") for r in results if "set_aside" in r or "error" in r)
    part.say(f"gold4: census masks {n(len(rows))} (tier lists' rows with a SPINEPS mask, each mask once); read "
             f"{n(sum(1 for r in results if 'verdict' in r))}; " + ", ".join(f"{k} {n(v)}" for k, v in sorted(reasons.items())))
    part.say(f"gold4: new to the dataset, gold 4 by rule 3's field test (VerSe, TotalSegmentator and FDG-PET-CT-Lesions, "
             f"which is ENHANCE.PET's autoPET, apart): {n(new['studies'])} studies, {n(len(new['persons']))} persons by the census's person key")
    order = sorted(by, key=lambda c: (-by[c]["admitted"], c))
    for collection in order[:COLLECTION_LINES]:
        c = by[collection]
        part.say(f"gold4: {collection} rows {n(c['rows'])}, admitted {n(c['admitted'])} of {n(len(persons[collection]))} "
                 f"persons, look {n(c['look'])}, not admitted {n(c['not_admitted'])}, set aside {n(c['set aside'])}, "
                 f"unreadable {n(c['unreadable'])}" + (f", of the admitted matched to their ENHANCE.PET study by grid "
                 f"{n(c['admitted, matched to its ENHANCE.PET study by grid'])}" if is_fdg(collection) else ""))
    rest = order[COLLECTION_LINES:]
    if rest:
        part.say(f"gold4: {n(len(rest))} more collections, rows {n(sum(by[c]['rows'] for c in rest))}, admitted "
                 f"{n(sum(by[c]['admitted'] for c in rest))}")
    part.say("gold4: the new gold 4's ends (head, foot): " + ", ".join(f"{h} {f} {n(v)}" for (h, f), v in sorted(ends.items())))
    part.say("gold4: the new gold 4's flags: " + (", ".join(f"{k} {n(v)}" for k, v in sorted(flags.items())) or "none"))
    for member in sorted(agree):
        part.say(f"gold4: {member}'s SPINEPS masks against its release masks' verdicts (release, SPINEPS): "
                 + ", ".join(f"{a} {b} {n(v)}" for (a, b), v in sorted(agree[member].items())))


def part_gold4(args):
    part = Part("gold4", args.out)
    rows = census_rows(args.rs)
    if not rows:
        part.say("gold4: no census tier list with a SPINEPS mask under the lab volume's ruleclass tiers")
        part.save()
        return part
    with pool(args.workers) as ex:
        results = list(ex.map(gold4_one, rows, chunksize=4))
    repeats = fdg_studies(args.out)
    counts = gold4_counts(rows, results, repeats)
    say_gold4(part, rows, results, counts)
    if repeats is None:
        part.say("gold4: the autopet part's match was not there, so no FDG row is matched to its ENHANCE.PET study")
    part.detail = {"rows": [{**row, **result} for row, result in zip(rows, results)]}
    part.save()
    return part


# ---------------------------------------------------------------- extent: TotalSegmentator's CTs read whole


TS_SUBJECT = re.compile(r"^s\d{4}$")
CHANGES_LISTED = 40
TS_SEGMENTATION = re.compile(r"^(vertebrae_.*|sacrum|rib_(left|right)_\d+|hip_(left|right)|skull|spinal_cord)\.nii\.gz$")


def ts_root(args):
    """(root, whether it is the canonical one) of TotalSegmentator's subjects on the grid."""
    canonical = Path(args.data) / "totalsegmentator_v300"
    if canonical.is_dir():
        return canonical, True
    copy = first_root(Path(args.home) / "data/TotalSegmentator_v3")
    return copy, False


def ts_subjects(root):
    """{subject: its folder} of every folder named like s0000 that holds a ct.nii.gz, the first found."""
    found = {}
    if root is None:
        return found
    for folder, dirs, files in os.walk(root):
        name = os.path.basename(folder)
        if TS_SUBJECT.match(name) and "ct.nii.gz" in files:
            found.setdefault(name, folder)
            dirs[:] = []
    return found


def column_centre(row):
    centres = [e["centroid_mm"] for e in row["levels"].values() if e["voxels"] >= sibling("gold3_field").LEVEL_MIN_VOXELS]
    return np.mean(np.asarray(centres, float), axis=0) if centres else None


def plane_ranges(volume, axis):
    """Each plane's lowest and highest value along one voxel axis, read slab by slab."""
    size = volume.shape[axis]
    low, high = np.full(size, np.inf), np.full(size, -np.inf)
    for start, slab in volume.slabs():
        others = tuple(a for a in range(3) if a != axis)
        if axis == 2:
            low[start:start + slab.shape[2]] = slab.min(axis=others)
            high[start:start + slab.shape[2]] = slab.max(axis=others)
        else:
            low = np.minimum(low, slab.min(axis=others))
            high = np.maximum(high, slab.max(axis=others))
    return low, high


def plane_height(affine, axis, index, centre):
    """The head-foot height of plane `index` along `axis` where it crosses the column's centre."""
    affine = np.asarray(affine, float)
    voxel = np.linalg.solve(affine[:3, :3], np.asarray(centre, float) - affine[:3, 3])
    voxel[axis] = index
    return float(affine[2, :3] @ voxel + affine[2, 3])


def extent_one(job):
    """One CT read whole and hashed: its grid, its constant planes at either end of the head-foot axis and
    the heights, at the column, of the first plane past them at each end."""
    sid, path, centre = job
    # Any error, counted by its kind, as in gold4_one: one CT must never end the part.
    try:
        volume = Volume(path, hashed=True)
    except Exception as error:  # noqa: BLE001
        return {"id": sid, "error": error_kind(error)}
    try:
        grid = grid_facts(volume)
        axis = grid["head_foot_axis"]
        low, high = plane_ranges(volume, axis)
        sha, size = volume.finish()
    except Exception as error:  # noqa: BLE001
        volume.close()
        return {"id": sid, "error": error_kind(error)}
    varied = np.flatnonzero(low != high)
    out = {"id": sid, "grid": grid, "sha256": sha, "bytes": size, "planes": int(len(low))}
    if not len(varied):
        return out | {"error": "every plane constant"}
    first, last = int(varied[0]), int(varied[-1])
    centre = centre if centre is not None else corner_centres(volume.shape, volume.affine).mean(0)[:3]
    try:
        heights = [rounded(plane_height(volume.affine, axis, i, centre), MM_DECIMALS) for i in (first, last)]
    except Exception as error:  # noqa: BLE001  (a singular affine, which no height can be read through)
        return out | {"error": f"no plane height, {error_kind(error)}"}
    return out | {"flat_low": first, "flat_high": len(low) - 1 - last, "low_mm": heights[0], "high_mm": heights[1]}


def own_planes(read):
    """(top, foot) as named_study takes them: the height of the head-most and foot-most planes the image
    reaches, at the column, where constant planes pad the grid beyond them; else None at that end."""
    upward = read["grid"]["affine"][2][read["grid"]["head_foot_axis"]] > 0
    high = read["high_mm"] if read["flat_high"] else None
    low = read["low_mm"] if read["flat_low"] else None
    return (high, low) if upward else (low, high)


def same_grid(read, row):
    return read["grid"]["shape"] == row["grid"]["shape"] and np.allclose(read["grid"]["affine"], row["grid"]["affine"], atol=2e-6)


def compare_planes(ours, cords, slack):
    """'same', 'cord only', 'CT only', 'differ' or 'neither' for one end."""
    if ours is None and cords is None:
        return "neither"
    if ours is None or cords is None:
        return "CT only" if cords is None else "cord only"
    return "same" if abs(ours - cords) <= slack else "differ"


def rejudge(row, read, subjects, verdicts):
    G = sibling("gold3_field")
    planes = own_planes(read)
    entry = subjects.get(row["id"], {})
    study = G.named_study(row, f"totalsegmentator:{row['id']}", entry.get("age"), entry.get("institute") or None, planes=planes)
    judged = G.judge(study, tables())
    cord = G.image_planes(row)
    slack = G.plane_slack(row["grid"])
    was = verdicts.get(row["id"])
    return {"verdict": judged["verdict"], "head": judged["head"], "foot": judged["foot"], "planes": planes,
            "was": was, "ends": [compare_planes(planes[i], cord[i], slack) for i in (0, 1)]}


def part_extent(args):
    part = Part("extent", args.out)
    root, canonical = ts_root(args)
    folders = ts_subjects(root)
    rows = {r["id"]: r for r in read_jsonl(DATA / "totalsegmentator/facts.jsonl") if "error" not in r}
    verdicts = {s["id"]: [s["verdict"], s["head"], s["foot"]] for s in admission()["studies"] if s["member"] == "totalsegmentator"}
    jobs = [(sid, os.path.join(folders[sid], "ct.nii.gz"), column_centre(rows[sid]) if sid in rows else None) for sid in sorted(folders)]
    with pool(args.workers) as ex:
        reads = list(ex.map(extent_one, jobs, chunksize=2))
    subjects = read_json(DATA / "totalsegmentator/subjects.json")["subjects"]
    judged, grids, ends, changes = {}, Counter(), Counter(), []
    for read in reads:
        row = rows.get(read["id"])
        if row is None or "error" in read:
            continue
        grids["same grid as the facts" if same_grid(read, row) else "another grid than the facts"] += 1
        if read["id"] not in verdicts:
            continue
        try:
            result = rejudge(row, read, subjects, verdicts)
        except Exception as error:  # noqa: BLE001  (one subject the test cannot judge is counted, never stops the rest)
            grids[f"not judged again, {error_kind(error)}"] += 1
            continue
        judged[read["id"]] = result
        ends.update(f"{end} {state}" for end, state in zip(("top", "foot"), result["ends"]))
        now = [result["verdict"], result["head"], result["foot"]]
        if now != result["was"]:
            changes.append(f"{read['id']} {' '.join(result['was'])} to {' '.join(now)}")
    sums = {f"{r['id']}/ct.nii.gz": r["sha256"] for r in reads if "sha256" in r}
    digest = write_sums(Path(args.out) / "totalsegmentator-ct.sha256", sums)
    errors = Counter(r["error"] for r in reads if "error" in r)
    part.detail = {"root_is_canonical": canonical, "reads": reads, "judged": judged}
    part.say(f"extent: TotalSegmentator CTs found {n(len(folders))} of the facts' {n(len(rows))} subjects, on the "
             + ("data root's canonical copy" if canonical else "grid home's copy, not the canonical root" if root else "grid nowhere"))
    part.say(f"extent: read whole and hashed {n(len(sums))}; " + ", ".join(f"{k} {n(v)}" for k, v in sorted({**grids, **errors}.items())))
    part.say(f"extent: CTs with constant planes at the grid's last slices {n(sum(1 for r in reads if r.get('flat_high')))}, "
             f"at its first {n(sum(1 for r in reads if r.get('flat_low')))}")
    part.say("extent: the CT's own planes against the cord's and the column's (image_planes), by end: "
             + ", ".join(f"{k} {n(v)}" for k, v in sorted(ends.items())))
    part.say(f"extent: re-judged with the CT's own planes {n(len(judged))}; verdicts or ends that change {n(len(changes))}")
    # The first few by subject, the rest in extent.json, so the report stays within what the gate prints.
    for line in wrapped("extent: changed (verdict, head, foot):", changes[:CHANGES_LISTED]) if changes else []:
        part.say(line)
    if len(changes) > CHANGES_LISTED:
        part.say(f"extent: {n(len(changes) - CHANGES_LISTED)} more changes, each by subject in the detail that stays on the grid")
    part.say(f"extent: the CTs' sums, sha256sum's layout by subject, written beside the report; their digest {grouped(digest)}")
    part.save()
    return part


# ---------------------------------------------------------------- held: the files against the sums recorded here


def recorded_sums(path):
    out = {}
    for line in Path(path).read_text(encoding="ascii").splitlines():
        sha, _, name = line.partition("  ")
        if name:
            out[name] = sha
    return out


def hashed_all(paths, workers):
    with pool(workers) as ex:
        return dict(zip(paths, ex.map(file_sums, paths, chunksize=8)))


def tally(found, recorded):
    """found: {name: [sha256...]} of the grid's files; recorded: {name: set of sha256}."""
    out = Counter()
    for name, shas in recorded.items():
        got = found.get(name, [])
        out["match" if any(s in shas for s in got) else "other bytes" if got else "not found"] += 1
    out["on the grid and not recorded"] = sum(1 for name in found if name not in recorded)
    return out


def say_tally(part, what, counts):
    part.say(f"held: {what}: " + ", ".join(f"{k} {n(v)}" for k, v in sorted(counts.items())))


def held_enhance_labels(args, part):
    root = Path(args.data) / "aws_enhance_pet_labels/raw"
    recorded = {name: {sha} for name, sha in recorded_sums(DATA / "enhance-pet/SHA256SUMS").items()}
    files = walk_files(root, lambda name: name.endswith(".nii.gz")) if root.is_dir() else {}
    paths = [p for ps in files.values() for p in ps if Path(p).parent.name in ("Vertebrae", "Ribs")]
    sums = hashed_all(paths, args.workers)
    found = defaultdict(list)
    for path, (sha, _) in sums.items():
        found[f"{Path(path).parent.name}/{Path(path).name}"].append(sha)
    say_tally(part, "ENHANCE.PET's vertebra and rib masks on the data root, against SHA256SUMS", tally(found, recorded))


def held_enhance_cts(args, part):
    root = Path(args.data) / "aws_enhance_pet_ct/raw"
    bucket = read_json(DATA / "enhance-pet/bucket.json")["studies"]
    rows = {r["id"]: r for r in read_jsonl(DATA / "enhance-pet/facts.jsonl") if "repaired_from" not in r}
    files = walk_files(root, lambda name: name.endswith(".nii.gz") and name[:-7] in rows) if root.is_dir() else {}
    paths = {name[:-7]: sorted(ps)[0] for name, ps in files.items()}
    with pool(args.workers) as ex:
        sums = dict(zip(paths, ex.map(file_sums, paths.values(), chunksize=4)))
        heads = dict(zip(paths, ex.map(ct_grid, paths.values(), chunksize=8)))
    counts = Counter()
    for sid in rows:
        if sid not in paths:
            counts["not found"] += 1
            continue
        sha, size = sums[sid]
        counts["bytes as the bucket lists" if size == bucket[sid][0] else "other bytes than the bucket lists"] += 1
        head, mask = heads[sid], rows[sid]["mask"]
        same = "error" not in head and head["shape"] == mask["shape"] and np.allclose(head["affine"], mask["affine"], atol=2e-6)
        counts["on its masks' grid" if same else "off its masks' grid"] += 1
    digest = write_sums(Path(args.out) / "enhance-pet-ct.sha256",
                        {f"{sid}.nii.gz": sums[sid][0] for sid in paths if sums[sid][1] is not None})
    say_tally(part, f"ENHANCE.PET's {n(len(rows))} CTs on the data root, against the bucket's bytes and the masks' grids", counts)
    part.say(f"held: ENHANCE.PET's CT sums written beside the report; their digest {grouped(digest)}")


# members.json's canonical root for VerSe, under the data root.
VERSE_ROOT = "versefusion/raw/VerSeFusion_data/raw"


def verse_recorded():
    """({mask file name: set of sha256}, how many mask files the facts read) of VerSe's both releases: a file
    of one name and the same bytes in each release is one entry of the first and two of the second."""
    out, entries = defaultdict(set), 0
    for row in read_jsonl(DATA / "verse/facts.jsonl"):
        for files in (row.get("files", {}), row.get("other_release", {}).get("file", {})):
            for name, entry in files.items():
                out[name].add(entry["sha256"])
                entries += 1
    return out, entries


def held_verse(args, part):
    root = Path(args.data) / VERSE_ROOT
    recorded, entries = verse_recorded()
    files = walk_files(root, lambda name: name in recorded) if root.is_dir() else {}
    sums = hashed_all([p for ps in files.values() for p in ps], args.workers)
    found = defaultdict(list)
    for path, (sha, _) in sums.items():
        found[Path(path).name].append(sha)
    say_tally(part, f"VerSe's {n(entries)} recorded mask files ({n(len(recorded))} names) on the data root's VerSeFusion "
                    "copy, by name and sha256", tally(found, recorded))


def ts_digest(folder):
    seg = Path(folder) / "segmentations"
    if not seg.is_dir():
        return {"error": "no segmentations folder"}
    files = {}
    for name in sorted(os.listdir(seg)):
        if TS_SEGMENTATION.match(name):
            sha, size = file_sums(seg / name)
            if size is None:
                return {"error": sha}
            files[name] = {"sha256": sha, "bytes": size}
    return sibling("gold3_field").sums_digest(files)


def held_totalseg(args, part):
    root, canonical = ts_root(args)
    folders = ts_subjects(root)
    rows = {r["id"]: r["files"] for r in read_jsonl(DATA / "totalsegmentator/facts.jsonl")}
    with pool(args.workers) as ex:
        digests = dict(zip(sorted(folders), ex.map(ts_digest, [folders[s] for s in sorted(folders)], chunksize=8)))
    counts = Counter()
    for sid, files in rows.items():
        got = digests.get(sid)
        if got is None:
            counts["not found"] += 1
        elif "error" in got:
            counts[got["error"]] += 1
        else:
            counts["match" if got == files else f"{got['count']} files and other sums" if got["count"] != files["count"] else "other sums"] += 1
    where = "the data root's canonical copy" if canonical else "the grid home's copy, not the canonical root, so not held" if root else "nowhere"
    say_tally(part, f"TotalSegmentator's {n(len(rows))} subjects' 54 mask files on {where}, against the facts' digest", counts)


def part_held(args):
    part = Part("held", args.out)
    for check in (held_enhance_labels, held_enhance_cts, held_verse, held_totalseg):
        # Each check reads its own files, so one that fails is said and the next still runs.
        try:
            check(args, part)
        except Exception as error:  # noqa: BLE001
            part.say(f"held: {check.__name__.replace('_', ' ')} stopped, {error_kind(error)}")
    part.save()
    return part


# ---------------------------------------------------------------- the command line


PARTS = {"ts142": part_ts142, "autopet": part_autopet, "gold4": part_gold4, "extent": part_extent, "held": part_held}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("part", choices=sorted(PARTS))
    parser.add_argument("--data", required=True, help="the data root")
    parser.add_argument("--rs", required=True, help="the lab volume's go2432 folder, which holds ruleclass/tiers")
    parser.add_argument("--home", required=True, help="the grid home, which holds model_night and the copies")
    parser.add_argument("--out", required=True, help="where each part writes its detail and its lines")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args(argv)
    part = PARTS[args.part](args)
    for line in part.lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
