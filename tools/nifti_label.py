"""NIfTI-1 label masks read, checked and rewritten to one byte a voxel by the standard library (#391, stage 3, pack).

tools/anomaly_pack.py's rewrite step carries every SPINEPS or release mask of the selection into the
pack's landing as a uint8 NIfTI-1 whose ids are the 28 canonical ones, and refuses the masks it
cannot vouch for. The reader here is gzip, struct and bytes.translate, because the pack job runs
under $PYDRV without nibabel, and a mask is a byte string with a header: a 100-400 MB mask is
classified in two translate passes and a few memchr probes, well under the time nibabel takes to
build an int32 copy of it. numpy is imported lazily, and only for a float mask, where the train
environment holds it; a float mask is taken when every value is an integer in 0..255 and refused
otherwise, since a float label file is either an integer mask stored wastefully or not a mask.

What the module gives tools/anomaly_pack.py:
    read_header(path)            the header up to vox_offset, one gzip block for the CT census
    grid_of / same_grid          the affine nibabel would choose, compared within 1e-3
    voxel_count(dims)            the voxels of a 3D volume, or one with singleton later dims
    label_bytes(header, data)    one byte a voxel from a uint8, int16, int32, int64 or float mask
    classify(data, map, dropped) the ids present, the dropped ones counted, the metal counted
    translate_table / rewrite    the mask rewritten against its CT's header, counted and timed
    write_label(path, h, data)   a uint8 NIfTI-1, gzip level 6 with no mtime, so a second write
                                 is byte for byte the first

A refusal is LabelRefused with .reason from REASONS, a closed set the stage counts by, and a
.detail that names counts and ids, never a path or a case, since the stage's stderr and report
carry counts only. A file that is no single-file NIfTI-1 at all raises NotNifti, a ValueError.
"""

import gzip
import os
import struct
import time
import zlib
from collections import namedtuple

HEADER_SIZE = 348
MAGIC = b"n+1\x00"
# TPTBox's Metal id, which SPINEPS writes into otherwise named masks: background in the pack,
# counted per mask and in millilitres, since the census could not explain the larger deposits.
METAL = 80
# The reasons a mask is refused, closed so that the stage's report counts the same names every run.
REASONS = frozenset((
    "not_3d", "datatype", "high_bytes", "float_data", "scaled", "length",
    "shape_mismatch", "affine_mismatch", "unknown_id", "empty",
))
# NIfTI-1 datatype codes and the bytes each takes per voxel; a code outside this table is refused.
UINT8, INT16, INT32, FLOAT32, FLOAT64, INT8, UINT16, UINT32, INT64, UINT64 = (
    2, 4, 8, 16, 64, 256, 512, 768, 1024, 1280)
BYTES_PER_VOXEL = {UINT8: 1, INT8: 1, INT16: 2, UINT16: 2, INT32: 4, UINT32: 4,
                   INT64: 8, UINT64: 8, FLOAT32: 4, FLOAT64: 8}
FLOAT_TYPES = (FLOAT32, FLOAT64)

Header = namedtuple("Header", "order dims datatype bitpix vox_offset scl_slope scl_inter pixdim "
                              "qform_code sform_code quatern qoffset srows head")
Ids = namedtuple("Ids", "ids_in dropped_counts metal_voxels")
Rewritten = namedtuple("Rewritten", "ids_in ids_out dropped_counts metal_voxels metal_ml voxels dims seconds")


class LabelRefused(Exception):
    """A mask the stage will not pack: .reason is one of REASONS, .detail counts and ids only."""

    def __init__(self, reason, detail=""):
        if reason not in REASONS:
            raise ValueError(f"{reason} is not a refusal reason the stage counts")
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class NotNifti(ValueError):
    """The bytes are no single-file NIfTI-1 volume: a short file, another format, a two-file pair,
    or a gzip stream that ends or breaks before vox_offset."""


def open_volume(path):
    """The file open for reading, inflated when its first two bytes say gzip; the name decides nothing."""
    with open(path, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rb")
    return open(path, "rb")


def parse_header(head):
    """The fields of a 348-byte NIfTI-1 header, in the byte order sizeof_hdr reveals."""
    if len(head) < HEADER_SIZE:
        raise NotNifti("shorter than a NIfTI-1 header")
    if head[:4] == struct.pack("<i", HEADER_SIZE):
        order = "<"
    elif head[:4] == struct.pack(">i", HEADER_SIZE):
        order = ">"
    else:
        raise NotNifti("sizeof_hdr is not 348")
    if head[344:HEADER_SIZE] != MAGIC:
        raise NotNifti("the magic is not n+1: a two-file pair or no NIfTI-1 at all")
    dims = struct.unpack(order + "8h", head[40:56])
    datatype, bitpix = struct.unpack(order + "2h", head[70:74])
    pixdim = struct.unpack(order + "8f", head[76:108])
    vox_offset, scl_slope, scl_inter = struct.unpack(order + "3f", head[108:120])
    qform_code, sform_code = struct.unpack(order + "2h", head[252:256])
    quatern = struct.unpack(order + "3f", head[256:268])
    qoffset = struct.unpack(order + "3f", head[268:280])
    srows = struct.unpack(order + "12f", head[280:328])
    # A NaN or negative offset fails the comparison, so int() never sees it.
    if not vox_offset >= HEADER_SIZE:
        raise NotNifti("vox_offset points inside the header")
    return Header(order, dims, datatype, bitpix, int(vox_offset), scl_slope, scl_inter, pixdim,
                  qform_code, sform_code, quatern, qoffset, srows, bytes(head[:HEADER_SIZE]))


def header_from(handle):
    """The header read from an open volume up to vox_offset, extensions included, so the data is next."""
    try:
        head = handle.read(HEADER_SIZE)
        fields = parse_header(head)
        head += handle.read(fields.vox_offset - HEADER_SIZE)
    except (EOFError, gzip.BadGzipFile, zlib.error) as broken:
        raise NotNifti("the gzip stream ends or breaks before vox_offset") from broken
    if len(head) < fields.vox_offset:
        raise NotNifti("the file ends before vox_offset")
    return fields._replace(head=head)


def read_header(path):
    """The header alone, which costs one gzip block for a CT whose voxels the census never inflates."""
    with open_volume(path) as handle:
        return header_from(handle)


def read_volume(path):
    """The header and every byte after vox_offset, inflated."""
    with open_volume(path) as handle:
        return header_from(handle), handle.read()


def grid_of(h):
    """The grid nibabel's affine is built from, named so that two sides must agree on the choice:
    the sform rows when sform_code is set, else the qform's qfac, spacing, quaternion and offsets,
    else the spacing alone."""
    if h.sform_code > 0:
        return ("sform",) + tuple(h.srows)
    if h.qform_code > 0:
        qfac = -1.0 if h.pixdim[0] < 0 else 1.0
        return ("qform", qfac) + tuple(h.pixdim[1:4]) + tuple(h.quatern) + tuple(h.qoffset)
    return ("pixdim",) + tuple(h.pixdim[1:4])


def same_grid(a, b, tol=1e-3):
    """Whether two grids made the same choice and agree within tol, the census's tolerance."""
    if a[0] != b[0] or len(a) != len(b):
        return False
    return all(abs(x - y) <= tol for x, y in zip(a[1:], b[1:]))


def voxel_count(dims):
    """The voxels of a volume whose dim says 3, or more with every later dim 1, the volumes FleXray
    squeezes to three; anything else is not_3d."""
    rank = dims[0]
    later = dims[4:1 + rank] if 4 <= rank <= 7 else ()
    if not 3 <= rank <= 7 or any(d != 1 for d in later) or any(d <= 0 for d in dims[1:4]):
        raise LabelRefused("not_3d", f"dim {tuple(dims)}")
    return dims[1] * dims[2] * dims[3]


def label_bytes(h, data):
    """One byte a voxel: a uint8 or int8 mask as it is, a wider integer mask by its low bytes once
    every high byte is zero, a float mask through numpy when every value is an integer in 0..255."""
    voxels = voxel_count(h.dims)
    if h.scl_slope not in (0.0, 1.0) or h.scl_inter != 0.0:
        raise LabelRefused("scaled", f"slope {h.scl_slope}, inter {h.scl_inter}")
    width = BYTES_PER_VOXEL.get(h.datatype)
    if width is None:
        raise LabelRefused("datatype", f"code {h.datatype}")
    if len(data) < voxels * width:
        raise LabelRefused("length", f"{len(data)} bytes for {voxels} voxels of {width}")
    if len(data) > voxels * width:
        data = data[:voxels * width]
    if h.datatype in FLOAT_TYPES:
        return float_label_bytes(h, data, voxels)
    if width == 1:
        return data
    return low_bytes(h.order, data, width)


def low_bytes(order, data, width):
    """The low byte of every voxel, once each other byte lane holds nothing; a set high byte is a
    value past 255 or a negative one, neither a label."""
    low = 0 if order == "<" else width - 1
    for lane in range(width):
        if lane == low:
            continue
        high = data[lane::width]
        if high.count(b"\x00") != len(high):
            raise LabelRefused("high_bytes", f"a value past 255 or below 0 in byte lane {lane} of {width}")
    return data[low::width]


def float_label_bytes(h, data, voxels):
    """A float mask through numpy, imported here alone so the module loads where numpy is absent."""
    try:
        import numpy
    except ImportError:
        raise LabelRefused("float_data", "numpy is not installed; the train environment holds it") from None
    kind = "f4" if h.datatype == FLOAT32 else "f8"
    values = numpy.frombuffer(data, dtype=numpy.dtype(h.order + kind), count=voxels)
    whole = numpy.isfinite(values) & (values >= 0) & (values <= 255) & (values == numpy.floor(values))
    if not bool(whole.all()):
        raise LabelRefused("float_data", f"{int(voxels - whole.sum())} values are no integer in 0..255")
    return values.astype(numpy.uint8).tobytes()


def classify(data, mapping, dropped):
    """The ids present in a one-byte mask: the mapped ones probed in the data, the dropped ones
    counted in what two translate passes leave. The first pass deletes every mapped id and the
    background, which is nearly the whole mask, so the rest is small; the second deletes the dropped
    ids and METAL from the rest, and any byte left is an id nobody named, which refuses the mask."""
    dropped = set(dropped) | {METAL}
    rest = data.translate(None, bytes(sorted(set(mapping) | {0})))
    unknown = rest.translate(None, bytes(sorted(dropped)))
    if unknown:
        seen = sorted(set(unknown[:1 << 20]))
        raise LabelRefused("unknown_id", ", ".join(str(v) for v in seen))
    ids_in = {v for v in mapping if v and bytes((v,)) in data}
    dropped_counts = {}
    for v in sorted(dropped):
        count = rest.count(bytes((v,)))
        if count:
            dropped_counts[v] = count
    ids_in |= set(dropped_counts)
    return Ids(tuple(sorted(ids_in)), dropped_counts, dropped_counts.get(METAL, 0))


def translate_table(mapping):
    """The 256-byte table for bytes.translate: a mapped id to its canonical id, everything else,
    the background, the dropped ids and METAL among them, to 0."""
    return bytes(mapping.get(v, 0) for v in range(256))


def voxel_ml(pixdim):
    """One voxel in millilitres, from the three spacings in millimetres."""
    return abs(pixdim[1] * pixdim[2] * pixdim[3]) / 1000.0


def check_against_ct(h, ct_header):
    """A mask is packed only on its CT's grid: the same first three dims and the same affine choice
    within tolerance, since FleXray pairs image and label by index alone."""
    dims = tuple(h.dims[1:4])
    ct_dims = tuple(ct_header.dims[1:4])
    if dims != ct_dims:
        raise LabelRefused("shape_mismatch", f"mask {dims}, ct {ct_dims}")
    mask_grid, ct_grid = grid_of(h), grid_of(ct_header)
    if not same_grid(mask_grid, ct_grid):
        raise LabelRefused("affine_mismatch", f"mask by {mask_grid[0]}, ct by {ct_grid[0]}")


def rewrite(src, dst, mapping, dropped, ct_header):
    """A mask read, held to its CT, classified, translated to the canonical ids and written as uint8;
    what was in it, what came out, what was dropped and how long it took. Nothing is written for a
    refused mask, and the checks that need no voxel run before the voxels are inflated."""
    started = time.monotonic()
    with open_volume(src) as handle:
        h = header_from(handle)
        voxels = voxel_count(h.dims)
        check_against_ct(h, ct_header)
        data = handle.read()
    labels = label_bytes(h, data)
    ids = classify(labels, mapping, dropped)
    ids_out = tuple(sorted({mapping[v] for v in ids.ids_in if mapping.get(v)}))
    if not ids_out:
        raise LabelRefused("empty", "no foreground remains once the dropped ids leave")
    write_label(dst, h, labels.translate(translate_table(mapping)))
    metal_ml = ids.metal_voxels * voxel_ml(h.pixdim)
    return Rewritten(ids.ids_in, ids_out, ids.dropped_counts, ids.metal_voxels, metal_ml,
                     voxels, tuple(h.dims[1:4]), time.monotonic() - started)


def write_label(path, h, data):
    """The header copied with datatype uint8, no scaling and its extensions kept, then the bytes,
    deflated at level 6 with no name and no mtime, to path.part and then into place. Level 6, since
    level 9 on hundreds of megabytes of mostly zeros costs tens of seconds for a few percent."""
    head = bytearray(h.head)
    struct.pack_into(h.order + "2h", head, 70, UINT8, 8)
    struct.pack_into(h.order + "2f", head, 112, 1.0, 0.0)
    part = str(path) + ".part"
    with open(part, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as out:
            out.write(head)
            out.write(data)
    os.replace(part, path)
