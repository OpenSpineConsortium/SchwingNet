"""COBRA2026's Varian export (tools/cobra_varian_export.py) on synthetic inputs with known answers: RTK's
projection matrix against a ray drawn through the detector plane by hand and against a matrix RTK itself wrote,
the geometry file read back, a Varian XIM image encoded here and decoded, the pose test choosing the map a
synthetic CT was rendered through and refusing one it was not, the frame's crop, scale and flip, the conversion
to attenuation through a bowtie's air scan, and the two-labeller rule; and the harvest's TotalSegmentator labels
as tools/realx_pairs.py reads them. numpy, scipy and Pillow are needed, which CI's python3 does not hold, so the
file is skipped there; run it with any python that has them:

    python3 -m unittest tests.test_cobra_varian_export -v
"""

import importlib.util
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISSING = [name for name in ("numpy", "scipy", "PIL") if importlib.util.find_spec(name) is None]
NIBABEL = importlib.util.find_spec("nibabel") is not None

if not MISSING:
    import numpy as np


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def params(**kw):
    base = dict(sid=1000.0, sdd=1500.0, gantry=0.0, out_of_plane=0.0, in_plane=0.0, source_x=0.0, source_y=0.0,
                offset_x=0.0, offset_y=0.0, radius=0.0, matrix=None)
    base.update(kw)
    return base


@unittest.skipIf(MISSING, f"needs numpy, scipy and Pillow ({', '.join(MISSING)} missing)")
class GeometryTest(unittest.TestCase):
    def setUp(self):
        self.V = load("cobra_varian_export")

    def test_the_source_runs_on_the_iec_circle(self):
        for g in (0.0, 37.0, 145.3, 270.0):
            p = params(gantry=g)
            want = 1000.0 * np.array([math.sin(math.radians(g)), 0.0, math.cos(math.radians(g))])
            self.assertTrue(np.allclose(self.V.rtk_source(p), want, atol=1e-9))
            self.assertTrue(np.allclose(self.V.rtk_matrix(p) @ np.r_[want, 1.0], 0.0, atol=1e-6))

    def test_the_matrix_is_the_ray_through_the_detector_plane(self):
        from scipy.spatial.transform import Rotation
        p = params(gantry=145.3, out_of_plane=4.0, in_plane=-7.5, source_x=3.0, source_y=-2.0, offset_x=-160.0, offset_y=1.5,
                   sid=1000.0, sdd=1540.0)
        # by hand: ITK's ZXY Euler rotation (scipy's intrinsic "ZXY") of the negated angles takes the world into the
        # frame where the source sits at (sox, soy, sid) and the detector is the plane z = sid - sdd; a point's image is
        # where the ray from the source through it meets that plane, less the projection offsets
        r = Rotation.from_euler("ZXY", [-math.radians(p["in_plane"]), -math.radians(p["out_of_plane"]), -math.radians(p["gantry"])]).as_matrix()
        src = np.array([p["source_x"], p["source_y"], p["sid"]])
        P = self.V.rtk_matrix(p)
        rng = np.random.default_rng(1)
        for X in rng.uniform(-200, 200, (20, 3)):
            x = r @ X
            t = p["sdd"] / (p["sid"] - x[2])
            want = src[:2] + t * (x[:2] - src[:2]) - np.array([p["offset_x"], p["offset_y"]])
            got = self.V.project(P, X[None])
            self.assertTrue(np.allclose([got[0][0], got[1][0]], want, atol=1e-9), (got, want))

    def test_a_matrix_rtk_wrote_is_made_again(self):
        # COBRA2026 case F003's first projection, its parameters and the matrix RTK wrote beside them in geometry.xml
        p = params(sid=1000.0, sdd=1540.0, gantry=145.302257112367, offset_x=-0.583769436531633, offset_y=0.0978428317776682)
        shipped = np.array([[1266.46866766578, 0, 876.1606328794, -583.769436531633],
                            [-0.0556967517100276, -1540, 0.0804430952861998, 97.8428317776682],
                            [0.569247135411916, 0, -0.822166466614473, -1000]])
        self.assertLess(np.abs(self.V.rtk_matrix(p) - shipped).max() / np.abs(shipped).max(), 1e-12)

    def test_the_geometry_file_reads_back_and_a_wrong_matrix_shows(self):
        body = ['<?xml version="1.0"?>', "<!DOCTYPE RTKGEOMETRY>", '<RTKThreeDCircularGeometry version="3">',
                "  <SourceToIsocenterDistance>1000</SourceToIsocenterDistance>",
                "  <SourceToDetectorDistance>1500</SourceToDetectorDistance>"]
        for g, ox in ((10.0, -160.0), (100.0, -159.5)):
            m = self.V.rtk_matrix(params(gantry=g, offset_x=ox))
            rows = "\n".join(" ".join(repr(float(v)) for v in row) for row in m)
            body += ["  <Projection>", f"    <GantryAngle>{g}</GantryAngle>", f"    <ProjectionOffsetX>{ox}</ProjectionOffsetX>",
                     f"    <Matrix>\n{rows}\n    </Matrix>", "  </Projection>"]
        body.append("</RTKThreeDCircularGeometry>")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "geometry.xml"
            path.write_text("\n".join(body))
            projections = self.V.read_rtk_geometry(path)
            self.assertEqual([p["gantry"] for p in projections], [10.0, 100.0])
            self.assertEqual(projections[1]["sdd"], 1500.0)
            self.assertEqual(projections[0]["out_of_plane"], 0.0)
            _, worst = self.V.matrices_of(projections)
            self.assertLess(worst, 1e-9)
            projections[1]["matrix"] = projections[1]["matrix"] * np.array([[1.0], [-1.0], [1.0]])
            _, worst = self.V.matrices_of(projections)
            self.assertGreater(worst, 100.0)          # the image turned upside down, in detector millimetres

    def test_the_camera_reproduces_an_improper_map(self):
        P = self.V.pixel_matrix(-198.0, -149.0, 0.388, 0.388) @ self.V.rtk_matrix(params(gantry=33.0, offset_x=-160.0)) \
            @ self.V.world_map(self.V.SOLVED_MAP, np.array([1.0, -2.0, 3.0]))
        K, ext = self.V.camera_from_matrix(P)
        self.assertAlmostEqual(K[2, 2], 1.0)
        self.assertAlmostEqual(np.linalg.det(ext[:3, :3]), 1.0, places=9)
        pts = np.random.default_rng(2).uniform(-150, 150, (10, 3))
        q = (K @ (ext @ np.c_[pts, np.ones(len(pts))].T)[:3]).T
        u, v = self.V.project(P, pts)
        self.assertTrue(np.allclose(q[:, 0] / q[:, 2], u) and np.allclose(q[:, 1] / q[:, 2], v))


def xim_bytes(pixels, props):
    """A compressed Varian XIM as the format lays it out, for the reader to decode."""
    h, w = pixels.shape
    p = pixels.astype(np.int64).ravel()
    i = np.arange(w + 1, h * w)
    d = p[i] - p[i - 1] - p[i - w] + p[i - w - 1]
    codes = np.where((d >= -128) & (d <= 127), 0, np.where((d >= -32768) & (d <= 32767), 1, 2))
    padded = np.zeros(-(-len(codes) // 4) * 4, np.uint8)
    padded[: len(codes)] = codes
    lut = (padded[0::4] | (padded[1::4] << 2) | (padded[2::4] << 4) | (padded[3::4] << 6)).astype(np.uint8)
    diffs = b"".join(struct.pack({0: "<b", 1: "<h", 2: "<i"}[c], int(v)) for c, v in zip(codes, d))
    head = struct.pack(f"<{w + 1}i", *p[: w + 1].tolist())
    out = b"VMF\x00\x00\x00\x00\x00" + struct.pack("<6i", 2, w, h, 16, 2, 1)
    out += struct.pack("<i", len(lut)) + lut.tobytes() + struct.pack("<i", len(head) + len(diffs)) + head + diffs
    out += struct.pack("<i", h * w * 2) + struct.pack("<i", 0)
    out += struct.pack("<i", len(props))
    for name, value in props.items():
        out += struct.pack("<i", len(name)) + name.encode()
        if isinstance(value, float):
            out += struct.pack("<id", 1, value)
        else:
            out += struct.pack("<ii", 2, len(value)) + value.encode()
    return out


@unittest.skipIf(MISSING, f"needs numpy, scipy and Pillow ({', '.join(MISSING)} missing)")
class XimTest(unittest.TestCase):
    def test_a_compressed_image_decodes_whole(self):
        V = load("cobra_varian_export")
        rng = np.random.default_rng(3)
        yy, xx = np.mgrid[0:40, 0:56]
        pixels = (3000 + 9000 * np.exp(-((xx - 30) / 12.0) ** 2) + rng.normal(0, 30, (40, 56))).astype(np.int64)
        pixels[10:12, 5:9] = 60000          # jumps that need two- and four-byte differences
        pixels[30, 40] = -70000
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "FilterBowtie.xim"
            path.write_bytes(xim_bytes(pixels, {"KVKiloVolts": 125.0, "KVCollimatorShape": "Half Fan V1"}))
            got, hdr, props = V.read_xim(path)
        self.assertEqual((hdr["width"], hdr["height"]), (56, 40))
        self.assertTrue(np.array_equal(got, pixels))
        self.assertEqual(props, {"KVKiloVolts": 125.0, "KVCollimatorShape": "Half Fan V1"})


def phantom(n=48, sp=5.0):
    """A CT with nothing symmetric about it: a water ellipsoid off the centre, a bone rod along z off both axes and a
    bone ball, in air; LPS with the isocentre at the origin."""
    org = -(n - 1) / 2.0 * sp * np.ones(3)
    z, y, x = np.mgrid[0:n, 0:n, 0:n] * sp + org[::-1, None, None, None]
    vol = np.full((n, n, n), -1000.0, np.float32)
    vol[((x - 10) / 70) ** 2 + ((y + 5) / 50) ** 2 + (z / 90) ** 2 <= 1] = 0.0
    vol[((x - 35) ** 2 + (y + 20) ** 2 <= 64) & (np.abs(z) < 80)] = 1000.0
    vol[(x + 25) ** 2 + (y - 20) ** 2 + (z - 40) ** 2 <= 225] = 1200.0
    return vol, org, np.array([sp, sp, sp])


@unittest.skipIf(MISSING, f"needs numpy, scipy and Pillow ({', '.join(MISSING)} missing)")
class PoseTest(unittest.TestCase):
    """The pose test on frames rendered from a phantom through a known map: it must choose that map, and refuse the
    solved map when the frames were made through another."""

    def frames_through(self, V, true_map, gantries, nc=200, nr=120, px=2.0):
        vol, org, sp = phantom()
        iso = np.zeros(3)
        ox, oy = -(nc - 1) / 2.0 * px, -(nr - 1) / 2.0 * px
        A = V.pixel_matrix(ox, oy, px, px)
        mats = {k: V.rtk_matrix(params(gantry=g)) for k, g in enumerate(gantries)}
        reals = {}
        for k in mats:
            P = V.facing(A @ mats[k] @ V.world_map(true_map, iso), iso)
            line, _, _, _, _ = V.render(vol, org, sp, P, nr, nc)
            reals[k] = 20000.0 * np.exp(-line)
        bands = {k: (0, nr) for k in mats}
        return V.map_scores(list(mats), reals, None, mats, A, vol, org, sp, iso, nr, nc, 2, 2, bands)

    def test_the_map_the_frames_were_made_through_wins(self):
        V = load("cobra_varian_export")
        ok, rec = V.map_verdict(self.frames_through(V, V.SOLVED_MAP, (0.0, 60.0, 135.0, 250.0)))
        self.assertTrue(ok, rec)
        self.assertGreater(rec["edge_ncc"], 0.95)
        self.assertGreaterEqual(rec["margin"], V.MAP_MARGIN)

    def test_frames_made_through_a_mirror_refuse_the_solved_map(self):
        V = load("cobra_varian_export")
        mirror = V.SOLVED_MAP @ np.diag([-1.0, 1.0, 1.0])      # the patient's left and right swapped
        ok, rec = V.map_verdict(self.frames_through(V, mirror, (0.0, 60.0, 135.0, 250.0)))
        self.assertFalse(ok, rec)
        self.assertEqual(rec["best_rows"], mirror.astype(int).tolist())


@unittest.skipIf(MISSING, f"needs numpy, scipy and Pillow ({', '.join(MISSING)} missing)")
class FrameTest(unittest.TestCase):
    def setUp(self):
        self.V = load("cobra_varian_export")

    def test_crop_scale_and_flip_carry_the_projection(self):
        V = self.V
        P = V.pixel_matrix(-429.94, -214.48, 0.28, 1.12) @ V.rtk_matrix(params(gantry=200.0, sdd=1540.0)) @ V.world_map(V.SOLVED_MAP, np.zeros(3))
        P = V.facing(P, np.zeros(3))
        crop = V.crop_window((1700.0, 190.0), (61, 316), 3072, 384, 0.28, 1.12)
        c0, r0, w, h = crop
        self.assertAlmostEqual(w * 0.28, h * 1.12, delta=0.3)      # square in millimetres
        self.assertTrue(0 <= c0 and c0 + w <= 3072 and r0 == 61 and r0 + h <= 316)
        pts = np.random.default_rng(4).uniform(-60, 60, (8, 3))
        u, v = V.project(P, pts)
        for flip in (False, True):
            uu, vv = V.project(V.png_matrix(P, crop, flip), pts)
            y = (v - r0) * V.SIZE / h
            self.assertTrue(np.allclose(uu, (u - c0) * V.SIZE / w))
            self.assertTrue(np.allclose(vv, V.SIZE - y if flip else y))
        flip = V.cranial_down(V.png_matrix(P, crop, False), np.zeros(3))
        self.assertFalse(V.cranial_down(V.png_matrix(P, crop, flip), np.zeros(3)))

    def test_a_crop_at_the_detector_edge_stays_on_it(self):
        c0, r0, w, h = self.V.crop_window((1020.0, 380.0), (0, 768), 1024, 768, 0.388, 0.388)
        self.assertEqual((c0, r0, w, h), (256, 0, 768, 768))

    def test_attenuation_through_the_air_scan(self):
        V = self.V
        cols = np.arange(300)
        F = np.tile(2000 + 18000 * np.exp(-((cols - 250) / 80.0) ** 2), (50, 1))
        L = np.zeros_like(F)
        L[:, 100:220] = 1.5
        I = 9.0 * F * np.exp(-L)
        air = L == 0
        scale = float(np.median(I[air] / F[air]))
        self.assertAlmostEqual(scale, 9.0)
        self.assertTrue(np.allclose(V.attenuation(I, F, scale), L, atol=1e-9))
        stored, mirrored = V.flood_spread(I, F, air)
        self.assertLess(stored, 1e-9)
        self.assertLess(stored, V.MIRROR_RATIO * mirrored)

    def test_the_display_ladder(self):
        a = np.linspace(0.0, 4.0, 10001)
        g = self.V.window_or(a, np.ones_like(a, bool))
        for p, grey in zip(self.V.OR_PCT, self.V.OR_GREY):
            self.assertAlmostEqual(float(np.interp(np.percentile(a, p), a, g)), grey, delta=0.05)

    def test_the_exposed_band(self):
        I = np.full((384, 600), 9000.0)
        I[:61] = 500.0
        I[316:] = 600.0
        self.assertEqual(self.V.exposed_rows(I, 190.0), (65, 312))
        self.assertEqual(self.V.exposed_rows(np.full((768, 100), 20000.0), 384.0), (0, 768))

    def test_the_cbct_section_of_the_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.yaml"
            path.write_text("cbct:\n  Bowtie: Half Fan V1\n  Detector: null\n  Frames: 894\n  ImagerResX: 0.388\n"
                            "  Manufacturer: Varian\nct:\n  Manufacturer: Siemens\n  PixelSpacing:\n  - 1.17\n")
            md = self.V.read_cbct_metadata(path)
        self.assertEqual(md, {"Bowtie": "Half Fan V1", "Detector": None, "Frames": 894, "ImagerResX": 0.388, "Manufacturer": "Varian"})

    def test_spineps_is_read_only_where_the_screen_checked_its_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            mask = Path(tmp) / "F035_seg-vert_msk.nii.gz"
            mask.write_bytes(b"")
            rec = Path(tmp) / "F035.json"
            good = {"naming": "ctd", "ctd_check": {"ok": True, "id_matches_ctd": True}, "mask": str(mask)}
            rec.write_text(json.dumps(good))
            self.assertEqual(self.V.spineps_trusted(rec), (mask, None))
            rec.write_text(json.dumps(dict(good, ctd_check={"ok": True, "id_matches_ctd": False})))
            self.assertIsNone(self.V.spineps_trusted(rec)[0])
            rec.write_text(json.dumps(dict(good, mask=str(Path(tmp) / "gone.nii.gz"))))
            self.assertIsNone(self.V.spineps_trusted(rec)[0])
            self.assertIsNone(self.V.spineps_trusted(Path(tmp) / "none.json")[0])

    def test_the_old_solvers_word_on_a_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "G042.json"
            self.assertEqual(self.V.solver_status(path), "not tried")
            path.write_text(json.dumps({"status": "ok", "axis_map": self.V.SOLVED_MAP.astype(int).tolist()}))
            self.assertEqual(self.V.solver_status(path), "ok")
            path.write_text(json.dumps({"status": "unsolved", "axis_map": [[0, 1, 0], [0, 0, -1], [1, 0, 0]]}))
            self.assertTrue(self.V.solver_status(path).startswith("unsolved"))
        self.assertEqual(self.V.solver_of({"case": "F003", "axis_map": {"edge_ncc": 0.7}}, {"F003"}), "ok")
        self.assertEqual(self.V.solver_of({"case": "F035", "axis_map": {"solver_2026_09_23": "not tried"}}, {"F003"}), "not tried")

    def test_the_held_out_rule_is_the_elekta_exports(self):
        import hashlib
        for case in ("F003", "G000", "G133", "F120"):
            h = int(hashlib.md5(case.encode()).hexdigest(), 16) % 10
            self.assertEqual(self.V.split_of(case) == "test", h >= 8)


@unittest.skipIf(MISSING or not NIBABEL, "needs numpy, scipy, Pillow and nibabel")
class LabellersTest(unittest.TestCase):
    def nifti(self, folder, name, data, sp=(1.5, 1.5, 3.0), org=(-30.0, -30.0, -45.0)):
        import nibabel as nib
        affine = np.diag([-sp[0], -sp[1], sp[2], 1.0])
        affine[:3, 3] = [-org[0], -org[1], org[2]]
        path = Path(folder) / name
        nib.save(nib.Nifti1Image(data, affine), str(path))
        return path

    def labels(self):
        """TotalSegmentator's ids on a 40 by 40 by 30 grid: L4 above L5, S1 above the rest of the sacrum."""
        lab = np.zeros((40, 40, 30), np.uint8)
        lab[15:25, 15:25, 22:27] = 28        # vertebrae_L4
        lab[15:25, 15:25, 15:20] = 27        # vertebrae_L5
        lab[12:28, 14:26, 10:13] = 26        # vertebrae_S1
        lab[12:28, 14:26, 2:10] = 25         # sacrum
        return lab

    def test_two_labellers_name_a_level_where_they_agree(self):
        V = load("cobra_varian_export")
        class_map = {"25": "sacrum", "26": "vertebrae_S1", "27": "vertebrae_L5", "28": "vertebrae_L4", "29": "vertebrae_L3",
                     "30": "vertebrae_L2", "31": "vertebrae_L1", "32": "vertebrae_T12"}
        ts = self.labels()
        spineps = np.zeros_like(ts)
        spineps[ts == 28] = 23                 # L4, the same name
        spineps[ts == 27] = 25                 # VERIDAH calls TotalSegmentator's L5 an L6
        spineps[(ts == 25) | (ts == 26)] = 26  # the sacrum with S1
        org, sp = np.array([-30.0, -30.0, -45.0]), np.array([1.5, 1.5, 3.0])
        with tempfile.TemporaryDirectory() as tmp:
            ts_path = self.nifti(tmp, "ts.nii.gz", ts)
            sp_path = self.nifti(tmp, "sp.nii.gz", spineps)
            masks, s1 = V.harvest_masks(ts_path, class_map, ts.shape, org, sp)
            names = V.spineps_names(masks, sp_path, ts.shape, org, sp)
            with self.assertRaises(ValueError):
                V.harvest_masks(ts_path, class_map, ts.shape, org + 5.0, sp)
        self.assertEqual(s1, int((ts == 26).sum()))
        self.assertEqual(int(masks["sacrum"].sum()), int(((ts == 25) | (ts == 26)).sum()))
        self.assertEqual(V.level_record("L4", names)["level"], "L4")
        self.assertEqual(V.level_record("sacrum", names)["level"], "sacrum")
        self.assertEqual(V.level_record("L5", names), {"level_ts": "L5", "level_spineps": "L6", "level_agree": False, "level": None,
                                                       "dice_ts_spineps": 1.0})
        self.assertIsNone(V.level_record("L3", names)["level"])
        self.assertIsNone(V.level_record("L4", None)["level"])

    def test_realx_pairs_reads_the_harvest_labels_with_s1_in_the_sacrum(self):
        realx = load("realx_pairs")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "cobra" / "ts"
            folder.mkdir(parents=True)
            (Path(tmp) / "cobra" / "class_map.json").write_text(json.dumps(
                {"25": "sacrum", "26": "vertebrae_S1", "27": "vertebrae_L5", "28": "vertebrae_L4", "29": "vertebrae_L3",
                 "30": "vertebrae_L2", "31": "vertebrae_L1", "32": "vertebrae_T12"}))
            path = self.nifti(folder, "F003.nii.gz", self.labels())
            labels, affine = realx.read_ts(path)
        ids = realx.S.VERSE_ID
        self.assertEqual(int((labels == ids["L4"]).sum()), 10 * 10 * 5)
        self.assertEqual(int((labels == ids["sacrum"]).sum()), 16 * 12 * 11)
        self.assertEqual(sorted(np.unique(labels).tolist()), [0, ids["L4"], ids["L5"], ids["sacrum"]])


if __name__ == "__main__":
    unittest.main()
