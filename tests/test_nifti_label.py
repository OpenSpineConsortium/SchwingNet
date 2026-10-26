"""tools/nifti_label.py (#391, stage 3, pack): NIfTI-1 label masks built by struct, read by the
standard library, held to their CT's grid, classified in two translate passes, rewritten to the
canonical ids as uint8, and written byte for byte the same twice. The float mask's numpy half runs
where numpy is installed (the train environment); its no-numpy half runs everywhere by blocking
the import."""

import gzip
import importlib.util
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

try:
    import numpy
except ImportError:
    numpy = None

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nifti_label_tool", ROOT / "tools" / "nifti_label.py")
nifti_label = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = nifti_label
spec.loader.exec_module(nifti_label)

LabelRefused = nifti_label.LabelRefused

# The VerSe alphabet to the 28 canonical ids, as tools/anomaly_pack.py carries it: C1-C7 and T1-T12
# keep their numbers, T13 (28) becomes 20, L1-L5 shift up one, L6 becomes 26, the sacrum 27, and
# CTSP's retired S1 (29) is the sacrum too. The coccyx (27), the ribs and the subregions (30-68)
# and metal (80) are dropped to background.
VERSE = {**{i: i for i in range(1, 20)}, 28: 20, **{20 + i: 21 + i for i in range(5)},
         25: 26, 26: 27, 29: 27}
DROPPED = {27} | set(range(30, 69)) | {80}

BITPIX = {2: 8, 256: 8, 4: 16, 512: 16, 8: 32, 768: 32, 1024: 64, 1280: 64, 16: 32, 64: 64, 128: 24}
FORMAT = {2: "B", 256: "b", 4: "h", 512: "H", 8: "i", 768: "I", 1024: "q", 1280: "Q", 16: "f", 64: "d"}
EXTENSION = struct.pack("<2i", 16, 4) + b"\x00" * 8
SMALL = (16, 16, 8)


def write_nifti(path, dims, datatype, data, order="<", slope=1.0, inter=0.0, gz=True, ext=b"",
                pixdim=(1.0, 1.0, 1.0), srows=None, codes=(0, 0), quatern=(0.0, 0.0, 0.0),
                qoffset=(0.0, 0.0, 0.0), magic=b"n+1\x00", qfac=1.0):
    """A NIfTI-1 file built by struct: data is bytes written as they are, or values packed by datatype."""
    head = bytearray(348)
    struct.pack_into(order + "i", head, 0, 348)
    struct.pack_into(order + "8h", head, 40, len(dims), *dims, *([1] * (7 - len(dims))))
    struct.pack_into(order + "2h", head, 70, datatype, BITPIX[datatype])
    struct.pack_into(order + "8f", head, 76, qfac, *pixdim, *([1.0] * (7 - len(pixdim))))
    struct.pack_into(order + "3f", head, 108, float(352 + len(ext)), slope, inter)
    head[148:160] = b"built by the"
    struct.pack_into(order + "2h", head, 252, *codes)
    struct.pack_into(order + "3f", head, 256, *quatern)
    struct.pack_into(order + "3f", head, 268, *qoffset)
    if srows is None:
        srows = (pixdim[0], 0, 0, 0, 0, pixdim[1], 0, 0, 0, 0, pixdim[2], 0)
    struct.pack_into(order + "12f", head, 280, *srows)
    head[344:348] = magic
    if not isinstance(data, (bytes, bytearray)):
        data = struct.pack(order + str(len(data)) + FORMAT[datatype], *data)
    raw = bytes(head) + (b"\x01\x00\x00\x00" if ext else b"\x00\x00\x00\x00") + ext + bytes(data)
    if gz:
        with gzip.open(path, "wb") as out:
            out.write(raw)
    else:
        Path(path).write_bytes(raw)
    return Path(path)


def voxels_of(dims):
    return dims[0] * dims[1] * dims[2]


def pattern(dims, ids, fill=0):
    """A mask of fill with each id laid down in turn over a stretch of voxels, the ids visible."""
    body = bytearray([fill]) * voxels_of(dims)
    stretch = max(1, len(body) // (len(ids) + 1))
    for n, v in enumerate(ids):
        start = (n + 1) * stretch
        body[start:start + stretch // 2] = bytes([v]) * (stretch // 2)
    return bytes(body)


class Volumes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def ct(self, dims=SMALL, **grid):
        """A CT's header on the given grid; its voxels never matter."""
        path = write_nifti(self.dir / "ct.nii.gz", dims, 4, bytes(2 * voxels_of(dims)), **grid)
        return nifti_label.read_header(path)

    def mask(self, name, dims, datatype, data, **extra):
        return write_nifti(self.dir / name, dims, datatype, data, **extra)

    def refused(self, reason, call, *args, **kwargs):
        with self.assertRaises(LabelRefused) as held:
            call(*args, **kwargs)
        self.assertEqual(held.exception.reason, reason, str(held.exception))
        return held.exception


class ReadingTest(Volumes):
    def test_uint8_translates_at_c_speed_and_keeps_the_header(self):
        body = pattern(SMALL, [1, 20, 25, 26])
        src = self.mask("m.nii.gz", SMALL, 2, body, ext=EXTENSION)
        dst = self.dir / "out.nii.gz"
        done = nifti_label.rewrite(src, dst, VERSE, DROPPED, self.ct())
        self.assertEqual(done.ids_in, (1, 20, 25, 26))
        self.assertEqual(done.ids_out, (1, 21, 26, 27))
        self.assertEqual((done.dropped_counts, done.metal_voxels, done.metal_ml), ({}, 0, 0.0))
        self.assertEqual((done.voxels, done.dims), (voxels_of(SMALL), SMALL))
        self.assertLess(done.seconds, 2.0)
        written, data = nifti_label.read_volume(dst)
        self.assertEqual(data, body.translate(nifti_label.translate_table(VERSE)))
        before = nifti_label.read_header(src)
        self.assertEqual((written.datatype, written.bitpix, written.scl_slope, written.scl_inter), (2, 8, 1.0, 0.0))
        self.assertEqual((written.dims, written.pixdim, written.vox_offset), (before.dims, before.pixdim, 368))
        # the descrip and the extension ride through untouched; only the four fields above change
        self.assertEqual(written.head[148:160], b"built by the")
        self.assertEqual(written.head[348:368], before.head[348:368])
        self.assertEqual(written.head[352:368], EXTENSION)
        patched = bytearray(before.head)
        struct.pack_into("<2h", patched, 70, 2, 8)
        struct.pack_into("<2f", patched, 112, 1.0, 0.0)
        self.assertEqual(written.head, bytes(patched))

    def test_int16_low_bytes_are_taken_when_the_high_bytes_are_zero(self):
        values = list(range(27)) + [0] * (voxels_of(SMALL) - 27)
        h, data = nifti_label.read_volume(self.mask("m.nii.gz", SMALL, 4, values))
        self.assertEqual((h.order, h.datatype, h.bitpix), ("<", 4, 16))
        self.assertEqual(nifti_label.label_bytes(h, data), bytes(values))

    def test_int16_with_a_high_byte_set_is_refused(self):
        values = [0] * voxels_of(SMALL)
        values[5] = 256
        h, data = nifti_label.read_volume(self.mask("m.nii.gz", SMALL, 4, values))
        self.refused("high_bytes", nifti_label.label_bytes, h, data)
        values[5] = -1
        h, data = nifti_label.read_volume(self.mask("n.nii.gz", SMALL, 4, values))
        self.refused("high_bytes", nifti_label.label_bytes, h, data)

    def test_big_endian_int16_takes_the_other_slice(self):
        values = [0, 7, 19, 26] + [0] * (voxels_of(SMALL) - 4)
        h, data = nifti_label.read_volume(self.mask("m.nii.gz", SMALL, 4, values, order=">"))
        self.assertEqual(h.order, ">")
        self.assertEqual(data[1:8:2], b"\x00\x07\x13\x1a")
        self.assertEqual(nifti_label.label_bytes(h, data), bytes(values))
        values[1] = 256
        h, data = nifti_label.read_volume(self.mask("n.nii.gz", SMALL, 4, values, order=">"))
        self.refused("high_bytes", nifti_label.label_bytes, h, data)

    def test_int32_and_uint32(self):
        values = [0, 1, 2, 255] + [0] * (voxels_of(SMALL) - 4)
        for datatype in (8, 768, 1024, 1280):
            with self.subTest(datatype=datatype):
                h, data = nifti_label.read_volume(self.mask(f"{datatype}.nii.gz", SMALL, datatype, values))
                self.assertEqual(nifti_label.label_bytes(h, data), bytes(values))
        values[2] = 65536
        for datatype in (8, 768):
            with self.subTest(datatype=datatype, high=True):
                h, data = nifti_label.read_volume(self.mask(f"{datatype}-high.nii.gz", SMALL, datatype, values))
                self.refused("high_bytes", nifti_label.label_bytes, h, data)
        # uint16 is the same rule as int16
        h, data = nifti_label.read_volume(self.mask("u16.nii.gz", SMALL, 512, [0, 1, 26] + [0] * (voxels_of(SMALL) - 3)))
        self.assertEqual(nifti_label.label_bytes(h, data)[:3], b"\x00\x01\x1a")

    def test_float_data_is_refused_without_numpy_and_taken_when_integral(self):
        values = [0.0, 1.0, 26.0] + [0.0] * (voxels_of(SMALL) - 3)
        h, data = nifti_label.read_volume(self.mask("f.nii.gz", SMALL, 16, values))
        # an import of numpy raises ImportError while sys.modules holds None for it
        with mock.patch.dict(sys.modules, {"numpy": None}):
            held = self.refused("float_data", nifti_label.label_bytes, h, data)
        self.assertIn("numpy", held.detail)
        if numpy is None:
            self.skipTest("numpy is in the train environment; the integral half runs there")
        self.assertEqual(nifti_label.label_bytes(h, data), bytes([0, 1, 26] + [0] * (voxels_of(SMALL) - 3)))

    @unittest.skipUnless(numpy is not None, "numpy is in the train environment")
    def test_float_data_through_numpy_takes_integers_in_range_and_refuses_the_rest(self):
        good = [0.0, 1.0, 26.0, 255.0] + [0.0] * (voxels_of(SMALL) - 4)
        for datatype, order in ((16, "<"), (64, "<"), (16, ">"), (64, ">")):
            with self.subTest(datatype=datatype, order=order):
                h, data = nifti_label.read_volume(self.mask(f"{datatype}{ord(order)}.nii.gz", SMALL, datatype, good, order=order))
                self.assertEqual(nifti_label.label_bytes(h, data), bytes([0, 1, 26, 255] + [0] * (voxels_of(SMALL) - 4)))
        for bad in (1.5, 256.0, -1.0, float("nan"), float("inf")):
            with self.subTest(bad=bad):
                values = list(good)
                values[2] = bad
                h, data = nifti_label.read_volume(self.mask("bad.nii.gz", SMALL, 64, values))
                held = self.refused("float_data", nifti_label.label_bytes, h, data)
                self.assertIn("1 values", held.detail)

    def test_scaled_data_is_refused(self):
        values = bytes([0, 1, 2] + [0] * (voxels_of(SMALL) - 3))
        h, data = nifti_label.read_volume(self.mask("s.nii.gz", SMALL, 2, values, slope=2.0))
        self.refused("scaled", nifti_label.label_bytes, h, data)
        h, data = nifti_label.read_volume(self.mask("i.nii.gz", SMALL, 2, values, slope=1.0, inter=1.0))
        self.refused("scaled", nifti_label.label_bytes, h, data)
        # a slope of 0 is NIfTI's "no scaling", as 1 is
        h, data = nifti_label.read_volume(self.mask("z.nii.gz", SMALL, 2, values, slope=0.0))
        self.assertEqual(nifti_label.label_bytes(h, data), values)

    def test_4d_singleton_is_3d_and_4d_two_channels_is_not(self):
        self.assertEqual(nifti_label.voxel_count((4, 4, 4, 4, 1, 1, 1, 1)), 64)
        self.assertEqual(nifti_label.voxel_count((3, 4, 4, 4, 1, 1, 1, 1)), 64)
        # FleXray squeezes every trailing singleton (nifti.py:53-56), so a 5D volume of singletons is 3D too
        self.assertEqual(nifti_label.voxel_count((5, 4, 4, 4, 1, 1, 1, 1)), 64)
        self.refused("not_3d", nifti_label.voxel_count, (4, 4, 4, 4, 2, 1, 1, 1))
        self.refused("not_3d", nifti_label.voxel_count, (2, 4, 4, 1, 1, 1, 1, 1))
        self.refused("not_3d", nifti_label.voxel_count, (3, 4, 0, 4, 1, 1, 1, 1))
        values = bytes([1] * 64)
        h, data = nifti_label.read_volume(self.mask("4d.nii.gz", (4, 4, 4, 1), 2, values))
        self.assertEqual(nifti_label.label_bytes(h, data), values)
        h, data = nifti_label.read_volume(self.mask("4d2.nii.gz", (4, 4, 4, 2), 2, values * 2))
        self.refused("not_3d", nifti_label.label_bytes, h, data)

    def test_short_data_is_refused_as_length_and_extra_bytes_are_left(self):
        h, data = nifti_label.read_volume(self.mask("short.nii.gz", SMALL, 2, bytes(voxels_of(SMALL) - 1)))
        self.refused("length", nifti_label.label_bytes, h, data)
        h, data = nifti_label.read_volume(self.mask("long.nii.gz", SMALL, 4, bytes(2 * voxels_of(SMALL)) + b"\x07\x07"))
        self.assertEqual(len(nifti_label.label_bytes(h, data)), voxels_of(SMALL))

    def test_an_unlisted_datatype_is_refused(self):
        h, data = nifti_label.read_volume(self.mask("rgb.nii.gz", SMALL, 128, bytes(3 * voxels_of(SMALL))))
        held = self.refused("datatype", nifti_label.label_bytes, h, data)
        self.assertIn("128", held.detail)

    def test_plain_nii_and_gz_read_alike(self):
        values = pattern(SMALL, [1, 2, 3])
        gz = self.mask("a.nii.gz", SMALL, 2, values, ext=EXTENSION, codes=(0, 1))
        plain = self.mask("b.nii", SMALL, 2, values, ext=EXTENSION, codes=(0, 1), gz=False)
        self.assertEqual(nifti_label.read_header(gz), nifti_label.read_header(plain))
        self.assertEqual(nifti_label.read_volume(gz)[1], nifti_label.read_volume(plain)[1])
        # the first two bytes decide, not the name
        misnamed_gz = self.mask("c.nii", SMALL, 2, values, gz=True)
        misnamed_plain = self.mask("d.nii.gz", SMALL, 2, values, gz=False)
        self.assertEqual(nifti_label.read_volume(misnamed_gz)[1], values)
        self.assertEqual(nifti_label.read_volume(misnamed_plain)[1], values)

    def test_a_file_that_is_no_nifti_raises_not_nifti(self):
        cases = {
            "short": b"\x1f\x8b" + b"\x00" * 10,
            "wrong-size": bytes(348).replace(b"\x00", b"\x01", 4),
        }
        for name, raw in cases.items():
            with self.subTest(name=name):
                path = self.dir / name
                path.write_bytes(raw)
                with self.assertRaises(nifti_label.NotNifti):
                    nifti_label.read_header(path)
        with self.subTest(name="two-file pair"):
            pair = self.mask("pair.nii.gz", SMALL, 2, bytes(voxels_of(SMALL)), magic=b"ni1\x00")
            with self.assertRaises(nifti_label.NotNifti):
                nifti_label.read_header(pair)
        with self.subTest(name="truncated before vox_offset"):
            whole = self.mask("whole.nii", SMALL, 2, bytes(voxels_of(SMALL)), ext=EXTENSION, gz=False)
            cut = self.dir / "cut.nii"
            cut.write_bytes(whole.read_bytes()[:360])
            with self.assertRaises(nifti_label.NotNifti):
                nifti_label.read_header(cut)
        with self.subTest(name="broken gzip"):
            broken = self.dir / "broken.nii.gz"
            broken.write_bytes(b"\x1f\x8b\x08\x00" + b"\xff" * 400)
            with self.assertRaises(nifti_label.NotNifti):
                nifti_label.read_header(broken)
        with self.subTest(name="missing"):
            with self.assertRaises(OSError):
                nifti_label.read_header(self.dir / "absent.nii.gz")


class GridTest(Volumes):
    def test_shape_mismatch_is_refused(self):
        src = self.mask("m.nii.gz", SMALL, 2, pattern(SMALL, [1, 2]))
        dst = self.dir / "out.nii.gz"
        held = self.refused("shape_mismatch", nifti_label.rewrite, src, dst, VERSE, DROPPED, self.ct((16, 16, 9)))
        self.assertIn("(16, 16, 8)", held.detail)
        self.assertFalse(dst.exists())
        self.assertFalse((self.dir / "out.nii.gz.part").exists())

    def test_affine_mismatch_is_refused_and_the_same_grid_passes(self):
        rows = (0.8, 0, 0, -120.5, 0, 0.8, 0, -200.25, 0, 0, 1.5, -850.0)
        body = pattern(SMALL, [1, 2])
        ct = self.ct(codes=(1, 1), srows=rows, quatern=(0.0, 1.0, 0.0), qoffset=(-120.5, -200.25, -850.0))
        off = list(rows)
        off[3] += 0.01
        src = self.mask("off.nii.gz", SMALL, 2, body, codes=(0, 1), srows=tuple(off))
        self.refused("affine_mismatch", nifti_label.rewrite, src, self.dir / "o.nii.gz", VERSE, DROPPED, ct)
        near = list(rows)
        near[3] += 0.0001
        src = self.mask("near.nii.gz", SMALL, 2, body, codes=(0, 1), srows=tuple(near))
        done = nifti_label.rewrite(src, self.dir / "n.nii.gz", VERSE, DROPPED, ct)
        self.assertEqual(done.ids_out, (1, 2))
        # the qform fallback: no sform on either side, the quaternion and offsets compared
        q = dict(codes=(1, 0), quatern=(0.0, 1.0, 0.0), qoffset=(-120.5, -200.25, -850.0), pixdim=(0.8, 0.8, 1.5))
        ct_q = self.ct(**q)
        src = self.mask("q.nii.gz", SMALL, 2, body, **q)
        self.assertEqual(nifti_label.rewrite(src, self.dir / "q-out.nii.gz", VERSE, DROPPED, ct_q).ids_out, (1, 2))
        moved = dict(q, qoffset=(-120.5, -200.25, -849.99))
        src = self.mask("q-moved.nii.gz", SMALL, 2, body, **moved)
        self.refused("affine_mismatch", nifti_label.rewrite, src, self.dir / "qm.nii.gz", VERSE, DROPPED, ct_q)
        flipped = dict(q, qfac=-1.0)
        src = self.mask("q-flipped.nii.gz", SMALL, 2, body, **flipped)
        self.refused("affine_mismatch", nifti_label.rewrite, src, self.dir / "qf.nii.gz", VERSE, DROPPED, ct_q)
        # mixed codes: the mask by its sform against a CT that has only a qform is refused whatever the numbers
        src = self.mask("mixed.nii.gz", SMALL, 2, body, codes=(0, 1), srows=rows)
        held = self.refused("affine_mismatch", nifti_label.rewrite, src, self.dir / "mx.nii.gz", VERSE, DROPPED, ct_q)
        self.assertEqual(held.detail, "mask by sform, ct by qform")
        # no codes at all: the spacing alone
        ct_p = self.ct(pixdim=(0.8, 0.8, 1.5))
        src = self.mask("p.nii.gz", SMALL, 2, body, pixdim=(0.8, 0.8, 1.5))
        self.assertEqual(nifti_label.rewrite(src, self.dir / "p-out.nii.gz", VERSE, DROPPED, ct_p).ids_out, (1, 2))
        src = self.mask("p-off.nii.gz", SMALL, 2, body, pixdim=(0.8, 0.8, 2.0))
        self.refused("affine_mismatch", nifti_label.rewrite, src, self.dir / "po.nii.gz", VERSE, DROPPED, ct_p)
        self.assertTrue(nifti_label.same_grid(("sform", 1.0, 2.0), ("sform", 1.0, 2.0009)))
        self.assertFalse(nifti_label.same_grid(("sform", 1.0, 2.0), ("sform", 1.0, 2.002)))
        self.assertFalse(nifti_label.same_grid(("sform", 1.0, 2.0), ("qform", 1.0, 2.0)))
        self.assertFalse(nifti_label.same_grid(("pixdim", 1.0, float("nan"), 1.0), ("pixdim", 1.0, float("nan"), 1.0)))


class IdsTest(Volumes):
    def test_unknown_id_is_refused_without_a_marker_and_an_input_255_is_an_unknown_id(self):
        body = bytearray(pattern(SMALL, [1, 2]))
        body[-1] = 99
        held = self.refused("unknown_id", nifti_label.classify, bytes(body), VERSE, DROPPED)
        self.assertEqual(held.detail, "99")
        body[-1] = 255
        body[0] = 200
        held = self.refused("unknown_id", nifti_label.classify, bytes(body), VERSE, DROPPED)
        self.assertEqual(held.detail, "200, 255")
        src = self.mask("m.nii.gz", SMALL, 2, bytes(body))
        self.refused("unknown_id", nifti_label.rewrite, src, self.dir / "o.nii.gz", VERSE, DROPPED, self.ct())
        self.assertFalse((self.dir / "o.nii.gz").exists())

    def test_dropped_ids_and_metal_become_background_and_are_counted(self):
        body = bytearray(pattern(SMALL, [1]))
        body[0:10] = bytes([27]) * 10
        body[10:15] = bytes([40]) * 5
        body[15:35] = bytes([80]) * 20
        body[35:38] = bytes([68]) * 3
        body = bytes(body)
        ids = nifti_label.classify(body, VERSE, DROPPED)
        self.assertEqual(ids, ((1, 27, 40, 68, 80), {27: 10, 40: 5, 68: 3, 80: 20}, 20))
        table = nifti_label.translate_table(VERSE)
        self.assertEqual(len(table), 256)
        self.assertEqual((table[0], table[27], table[40], table[80], table[29], table[28], table[26]), (0, 0, 0, 0, 27, 20, 27))
        grid = dict(pixdim=(0.5, 0.5, 2.0))
        src = self.mask("m.nii.gz", SMALL, 2, body, **grid)
        done = nifti_label.rewrite(src, self.dir / "o.nii.gz", VERSE, DROPPED, self.ct(**grid))
        self.assertEqual((done.ids_in, done.ids_out), ((1, 27, 40, 68, 80), (1,)))
        self.assertEqual((done.dropped_counts, done.metal_voxels), ({27: 10, 40: 5, 68: 3, 80: 20}, 20))
        self.assertAlmostEqual(done.metal_ml, 20 * 0.5 / 1000.0)
        out = nifti_label.read_volume(self.dir / "o.nii.gz")[1]
        self.assertEqual(out[:38], bytes(38))
        self.assertEqual(set(out), {0, 1})

    def test_29_becomes_sacrum(self):
        body = bytearray(pattern(SMALL, [24, 26]))
        body[0:8] = bytes([29]) * 8
        body = bytes(body)
        done = nifti_label.rewrite(self.mask("m.nii.gz", SMALL, 2, body), self.dir / "o.nii.gz", VERSE, DROPPED, self.ct())
        self.assertEqual((done.ids_in, done.ids_out), ((24, 26, 29), (25, 27)))
        out = nifti_label.read_volume(self.dir / "o.nii.gz")[1]
        self.assertEqual(out[:8], bytes([27]) * 8)
        self.assertEqual(out.count(bytes([27])), 8 + body.count(bytes([26])))

    def test_a_mask_with_nothing_but_dropped_ids_is_refused_as_empty(self):
        body = bytearray(voxels_of(SMALL))
        body[0:4] = bytes([80]) * 4
        body[4:6] = bytes([27]) * 2
        src = self.mask("m.nii.gz", SMALL, 2, bytes(body))
        self.refused("empty", nifti_label.rewrite, src, self.dir / "o.nii.gz", VERSE, DROPPED, self.ct())
        self.assertFalse((self.dir / "o.nii.gz").exists())
        self.refused("empty", nifti_label.rewrite, self.mask("z.nii.gz", SMALL, 2, bytes(voxels_of(SMALL))),
                     self.dir / "z-out.nii.gz", VERSE, DROPPED, self.ct())

    def test_classify_touches_the_whole_mask_in_two_translate_passes(self):
        dims = (200, 150, 100)
        body = bytearray(voxels_of(dims))
        body[1000:400000] = bytes([20]) * 399000
        body[-1] = 40
        body = bytes(body)
        started = time.monotonic()
        ids = nifti_label.classify(body, VERSE, DROPPED)
        self.assertEqual(ids, ((20, 40), {40: 1}, 0))
        last_unknown = body[:-1] + b"\x63"
        held = self.refused("unknown_id", nifti_label.classify, last_unknown, VERSE, DROPPED)
        self.assertEqual(held.detail, "99")
        self.assertLess(time.monotonic() - started, 5.0)
        src = self.mask("big.nii.gz", dims, 2, body)
        done = nifti_label.rewrite(src, self.dir / "big-out.nii.gz", VERSE, DROPPED, self.ct(dims))
        self.assertEqual((done.ids_in, done.ids_out, done.dropped_counts, done.voxels), ((20, 40), (21,), {40: 1}, 3000000))
        out = nifti_label.read_volume(self.dir / "big-out.nii.gz")[1]
        self.assertEqual((len(out), out[-1], out[1000], out.count(bytes([21]))), (3000000, 0, 21, 399000))
        self.assertLess(done.seconds, 10.0)


class WritingTest(Volumes):
    def test_the_written_file_is_byte_identical_on_a_second_write(self):
        body = pattern(SMALL, [1, 2, 3])
        h = nifti_label.read_header(self.mask("m.nii.gz", SMALL, 2, body, ext=EXTENSION))
        first, second = self.dir / "one.nii.gz", self.dir / "two.nii.gz"
        nifti_label.write_label(first, h, body)
        time.sleep(0.01)
        nifti_label.write_label(second, h, body)
        raw = first.read_bytes()
        self.assertEqual(raw, second.read_bytes())
        # gzip's header: no mtime (bytes 4 to 8), no name (the FNAME flag off), deflate
        self.assertEqual(raw[:4], b"\x1f\x8b\x08\x00")
        self.assertEqual(raw[4:8], b"\x00\x00\x00\x00")
        # no .part is left behind: the write lands by os.replace
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["m.nii.gz", "one.nii.gz", "two.nii.gz"])
        written, data = nifti_label.read_volume(first)
        self.assertEqual(data, body)
        self.assertEqual(written.head[352:368], EXTENSION)

    def test_a_reason_outside_the_closed_set_is_a_programming_error(self):
        with self.assertRaises(ValueError):
            LabelRefused("something_else")
        self.assertEqual(str(LabelRefused("empty")), "empty")
        self.assertEqual(str(LabelRefused("unknown_id", "99")), "unknown_id: 99")
        self.assertEqual(nifti_label.REASONS, {"not_3d", "datatype", "high_bytes", "float_data", "scaled", "length",
                                               "shape_mismatch", "affine_mismatch", "unknown_id", "empty"})


if __name__ == "__main__":
    unittest.main()
