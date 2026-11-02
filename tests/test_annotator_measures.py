"""The annotators' measures and the projection test (tools/annotator_measures.py): each measure reads alike in
three dimensions and in two where its points lie in a plane square to the ray, a length divided by its
magnification is its 3-D length, the segmental angle keeps its sign whichever side the image shows the plane from,
the vertebra's own axes give the view's angle, the oracle's construction gives no wedge, the projection test reads
a pair and its export's other frames and never a held-out person, and the gold tier's aggregates and ratios are
what their rows say. numpy is all the module needs, which CI's python3 does not hold, so the file is skipped there;
run it with any python that has numpy:

    python3 -m unittest tests.test_annotator_measures -v
"""

import csv
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISSING = [name for name in ("numpy",) if importlib.util.find_spec(name) is None]
BORDERCALL = ROOT.parent / "bordercall"


def load():
    spec = importlib.util.spec_from_file_location("annotator_measures_under_test", ROOT / "tools" / "annotator_measures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rotation_x(deg):
    import numpy as np
    a = math.radians(deg)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])


def vertebra(M, centre, R, width=45.0, depth=33.0, height=27.0, inset=2.0):
    """The eighteen points of a box-shaped vertebra placed as the oracle places them (each plate's four points at
    its slab's height, every chord along its frame axis), in the frame R (columns x right, y anterior, z up)."""
    import numpy as np
    top, bot = height / 2 - inset, -height / 2 + inset
    local = {"endplate.right": (width / 2, depth / 2, top), "endplate.left": (-width / 2, depth / 2, top),
             "endplate_depth.posterior": (0, 0, top), "endplate_depth.anterior": (0, depth, top),
             "endplate_lower.right": (width / 2 - 1, depth / 2, bot), "endplate_lower.left": (-width / 2 + 1, depth / 2, bot),
             "endplate_lower_depth.posterior": (0, 0, bot), "endplate_lower_depth.anterior": (0, depth + 1, bot),
             "h_post.superior": (0, 3, height / 2), "h_post.inferior": (0, 3, -height / 2),
             "canal_w.right": (11, -9, 0), "canal_w.left": (-11, -9, 0), "canal_ap.posterior": (0, -18, 0),
             "canal_ap.anterior": (0, 0, 0), "tp_span.right": (40, -9, 0), "tp_span.left": (-40, -9, 0),
             "spinous_length.canal": (0, -18, 0), "spinous_length.tip": (0, -48, -6)}
    pts = np.array([local[name] for name in M.G.LANDMARKS], float)
    return pts @ R.T + np.asarray(centre, float)


def column(M, lordosis=4.0, levels=5):
    """A column of levels stacked down z, each turned about x a further `lordosis` degrees."""
    import numpy as np
    out, centre = [], np.zeros(3)
    for i in range(levels):
        R = rotation_x(lordosis * i)
        out.append(vertebra(M, centre, R))
        centre = centre - R[:, 2] * 34.0
    return np.array(out)


def camera(source, forward, down, f=1500.0, c=256.0):
    """P for a source at `source` looking along `forward`, image rows running along `down`."""
    import numpy as np
    forward = np.asarray(forward, float) / np.linalg.norm(forward)
    down = np.asarray(down, float) - np.dot(down, forward) * forward
    down /= np.linalg.norm(down)
    right = np.cross(down, forward)
    Rc = np.vstack([right, down, forward])
    K = np.array([[f, 0, c], [0, f, c], [0, 0, 1.0]])
    return K @ np.hstack([Rc, (-Rc @ np.asarray(source, float)).reshape(3, 1)])


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class Terms(unittest.TestCase):
    def setUp(self):
        self.M = load()

    def test_shift_moves_rows_and_pads_with_nan(self):
        import numpy as np
        v = np.array([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(self.M.shift(v, 1)[:2], [2.0, 3.0])
        self.assertTrue(math.isnan(self.M.shift(v, 1)[2]))
        np.testing.assert_array_equal(self.M.shift(v, -1)[1:], [1.0, 2.0])
        self.assertTrue(np.isnan(self.M.shift(v, 5)).all())

    def test_axes_are_the_vertebras_own_and_right_handed(self):
        import numpy as np
        R = rotation_x(20.0)
        col = vertebra(self.M, (5, -3, 9), R)[None]
        ex, ey, ez = self.M.axes(col)
        np.testing.assert_allclose(np.column_stack([ex[0], ey[0], ez[0]]), R, atol=1e-12)

    def test_chords_are_the_specs_lengths(self):
        col = vertebra(self.M, (0, 0, 0), rotation_x(0.0))[None]
        self.assertAlmostEqual(float(self.M.EPWU(col)[0]), 45.0)
        self.assertAlmostEqual(float(self.M.EPDL(col)[0]), 34.0)
        self.assertAlmostEqual(float(self.M.VBHP(col)[0]), 27.0)
        self.assertAlmostEqual(float(self.M.HA(col)[0]), math.hypot(23.0, 1.0))
        self.assertAlmostEqual(float(self.M.HP(col)[0]), 23.0)

    def test_crush_and_below_read_the_neighbours(self):
        col = column(self.M, lordosis=0.0, levels=3)
        crush = self.M.BY_NAME["crush"].value3(col)
        self.assertTrue(math.isnan(crush[0]) and math.isnan(crush[2]))
        self.assertAlmostEqual(float(crush[1]), 1.0)
        below = self.M.BY_NAME["EPWu/below"].value3(col)
        self.assertAlmostEqual(float(below[0]), 1.0)
        self.assertTrue(math.isnan(below[2]))

    def test_the_oracles_construction_gives_no_wedge(self):
        import numpy as np
        checks = self.M.construction_checks(column(self.M))
        for key in ("upper_plate_z_spread_mm", "lower_plate_z_spread_mm", "depth_chords_angle_deg", "width_chords_angle_deg"):
            self.assertLess(float(np.nanmax(np.abs(checks[key]))), 1e-9, key)


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class Projection(unittest.TestCase):
    def setUp(self):
        self.M = load()
        self.col = column(self.M)
        self.mid = self.col.reshape(-1, 3).mean(axis=0)

    def lateral(self, side=1.0):
        return camera(self.mid + side * 1000.0 * __import__("numpy").array([1.0, 0, 0]), [-side, 0, 0], [0, 0, -1])

    def test_lateral_ratios_and_lengths_read_as_in_3d(self):
        import numpy as np
        P = self.lateral()
        source, Pn, focal = self.M.camera(P)
        col2 = self.M.G.project(Pn, self.col)
        for name in ("ha/hp", "EPDu/VBHp", "SCD/EPDu", "EPDl/EPDu", "crush", "VBHp/below"):
            m = self.M.BY_NAME[name]
            v3, v2 = m.value3(self.col), m.value2(self.col, col2)
            keep = np.isfinite(v3)
            np.testing.assert_allclose(v2[keep], v3[keep], atol=1e-9, err_msg=name)
        m = self.M.BY_NAME["EPDu"]
        mag = focal / self.M.middle_depth(m, self.col, Pn)
        np.testing.assert_allclose(m.value2(self.col, col2) / (mag * m.value3(self.col)), 1.0, atol=1e-9)

    def test_segmental_angle_keeps_its_sign_from_either_side(self):
        import numpy as np
        m = self.M.BY_NAME["seg_sag"]
        v3 = m.value3(self.col)
        np.testing.assert_allclose(v3[:-1], 4.0, atol=1e-9)
        for side in (1.0, -1.0):
            _, Pn, _ = self.M.camera(self.lateral(side))
            v2 = m.value2(self.col, self.M.G.project(Pn, self.col))
            np.testing.assert_allclose(v2[:-1], v3[:-1], atol=1e-6, err_msg=f"side {side}")

    def test_view_angles_name_the_lateral_and_the_ap(self):
        import numpy as np
        source, _, _ = self.M.camera(self.lateral())
        off_ap, off_lat = self.M.view_angles(self.col, source)
        self.assertLess(float(off_lat[2]), 1.0)
        self.assertGreater(float(off_ap[2]), 80.0)
        ap = camera(self.mid + 1000.0 * np.array([0, 1.0, 0]), [0, -1, 0], [0, 0, -1])
        source = self.M.camera(ap)[0]
        off_ap, off_lat = self.M.view_angles(self.col, source)
        # each level turns a further 4 degrees about x and sits higher or lower on the ray's fan, so its true AP
        # view is off the ray by the angle between the ray to its centre and its own y
        ey = self.M.axes(self.col)[1]
        ray = self.col.mean(axis=1) - source
        ray /= np.linalg.norm(ray, axis=1, keepdims=True)
        np.testing.assert_allclose(off_ap, np.degrees(np.arccos(np.abs(np.sum(ray * ey, axis=1)))), atol=1e-9)
        self.assertTrue(bool(np.all(np.diff(off_ap) > 1.0)))

    def test_an_ap_view_foreshortens_the_depth_and_keeps_the_width(self):
        import numpy as np
        ap = camera(self.mid + 1000.0 * np.array([0, 1.0, 0]), [0, -1, 0], [0, 0, -1])
        rows = self.M.as_arrays(self.M.frame_rows(self.col, ["L1", "L2", "L3", "L4", "L5"], ap, 512, "p", "s", "pair"))
        err = self.M.agreement("length", rows["v3"], rows["v2"], rows["mag"])
        width = rows["measure"] == [m.name for m in self.M.MEASURES].index("EPWu")
        depth = rows["measure"] == [m.name for m in self.M.MEASURES].index("EPDu")
        self.assertLess(float(np.abs(err[width][0])), 1e-9)
        self.assertLess(float(err[depth][0]), -0.9)


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class PairsAndExport(unittest.TestCase):
    def setUp(self):
        self.M = load()

    def make(self, root):
        """A built pair of one person with one frame, its export's meta for that frame and one oblique frame, and
        a held-out person whose meta must never be read."""
        import numpy as np
        col = column(self.M)
        mid = col.reshape(-1, 3).mean(axis=0)
        pairs, export = Path(root) / "pairs", Path(root) / "export"
        (export / "meta").mkdir(parents=True)
        pairs.mkdir()
        K = np.array([[1500.0, 0, 192], [0, 1500.0, 192], [0, 0, 1]])
        metas = {}
        for fid, ang in (("000", 0.0), ("001", 40.0)):
            a = math.radians(ang)
            fwd = np.array([-math.cos(a), -math.sin(a), 0.0])
            P = camera(mid - 1000.0 * fwd, fwd, [0, 0, -1], f=1500.0, c=192.0)
            Kinv = np.linalg.inv(K)
            ext = np.vstack([Kinv @ P, [0, 0, 0, 1]])
            metas[fid] = P
            (export / "meta" / f"A001_{fid}.json").write_text(json.dumps(
                {"case": "A001", "frame": fid, "size": [384, 384], "pose": {"K": K.tolist(), "ext": ext.tolist()}}))
        (export / "meta" / "A999_000.json").write_text("not json: a held-out person's meta is never opened")
        (export / "meta" / "A001_002.json").write_text(json.dumps(
            {"case": "A001", "frame": "002", "size": [384, 200], "pose": {"K": K.tolist(), "ext": ext.tolist()}}))
        canvas = np.array([[512 / 384, 0, 0], [0, 512 / 384, 0], [0, 0, 1.0]])
        frame = {"view": "lat_real", "P": canvas @ metas["000"], "image": np.zeros((512, 512), np.float32), "edge_ncc": 0.5}
        self.M.S.save_pair(str(pairs / "A001.npz"), {"levels": ["L1", "L2", "L3", "L4", "L5"], "landmarks": col,
                                                     "sacrum": np.zeros(3), "frames": [frame], "stand_in": False})
        (pairs / "manifest.json").write_text(json.dumps({"export": str(export), "held_out": [{"person": "x:A999"}],
                                                         "persons": [{"person": "x:A001", "case": "A001", "npz": "A001.npz", "frame_ids": ["000"]}]}))
        return pairs

    def test_reads_the_pair_and_the_other_frames_and_never_the_held_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            pairs = self.make(tmp)
            res = self.M.run_project([str(pairs)], str(Path(tmp) / "projection.json"))
            self.assertEqual(res["counts"]["pairs"]["persons"], 1)
            self.assertEqual(res["counts"]["pairs"]["held_out_not_read"], 1)
            self.assertEqual(res["counts"]["pairs"]["export_frames_not_square"], 1)
            self.assertGreater(res["rows"]["by_kind"]["pair"], 0)
            self.assertGreater(res["rows"]["by_kind"]["export"], 0)
            self.assertLess(res["pair_vs_export_ratio_gap"]["pairs"], 1e-9)
            lateral = next(m for m in res["measures"] if m["name"] == "ha/hp")["views"]["lat"]
            self.assertEqual(lateral["verdict"], "survives")         # the frame is a true lateral of a box column
            self.assertEqual(lateral["within_tolerance"]["n"], 5)
            self.assertLess(lateral["within_tolerance"]["median_abs"], 1e-9)
            self.assertTrue(self.M.projection_table(res).startswith("| Measure"))


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class Gold(unittest.TestCase):
    def setUp(self):
        self.M = load()

    def test_aggregates_one_study_a_person_with_the_ratios(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows, persons = Path(tmp) / "rows.csv", Path(tmp) / "persons.csv"
            with open(persons, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["person", "member", "study"])
                for i in range(6):
                    w.writerow([f"P{i}", "autopet", f"{i:04d}"])
                w.writerow(["V0", "verse", "gl001"])
            with open(rows, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["study", "level", "key", "value", "note"])
                for study in [f"{i:04d}" for i in range(7)] + ["gl001"]:
                    for k, level in enumerate(("L3", "L4", "L5")):
                        w.writerow([study, level, "h_post_inset", 30.0 - k, ""])
                        w.writerow([study, level, "endplate_depth", 35.0, ""])
                        w.writerow([study, level, "h_post", 28.0, ""])
                    w.writerow([study, "pelvis", "pelvic_incidence", 50.0, ""])
                    w.writerow([study, "pelvis", "intercristal_level", "L4", ""])
            summary = self.M.run_gold(str(rows), str(persons), str(Path(tmp) / "out"))
            self.assertEqual(summary["studies_with_rows"], 6)            # study 0006 and VerSe's are no chosen person's
            with open(Path(tmp) / "out" / "table.csv", newline="") as f:
                table = {(r["level"], r["measure"]): r for r in csv.DictReader(f)}
            self.assertAlmostEqual(float(table[("L4", "crush_index")]["mean"]), 29.0 / 29.0)
            self.assertAlmostEqual(float(table[("L3", "depth_over_h_post")]["mean"]), 35.0 / 28.0)
            self.assertNotIn(("L5", "crush_index"), table)
            self.assertEqual(summary["pelvis"]["intercristal_level"], {"L4": 6})
            self.assertEqual(summary["pelvis"]["pelvic_incidence"]["n"], 6)


class FakeCensus:
    """The census's interface as this tool uses it, its information one over the error, so that the X-ray errors'
    effect is plain."""

    SEED, RATIO_ERROR = 1, 0.04

    def __init__(self):
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class Series:
            key: str
            kind: str
            error: float
            levels: tuple
            mean: tuple
            sd: tuple
            n: tuple

        self.Series = Series

    def census_group(self, measures, fields, seed, nodes, correlation):
        m = measures[0]
        K = len(m.levels)
        return {"measures": [{"key": m.key, "standalone": [1.0 / m.error] * K, "standalone_se": [0.0] * K}]}


@unittest.skipIf(MISSING, f"needs numpy ({', '.join(MISSING)} missing)")
class XrayErrors(unittest.TestCase):
    def setUp(self):
        self.M = load()
        self.C = FakeCensus()
        view = {"verdict": "survives", "robust_sd": 0.02, "within_tolerance": {"median": 0.0, "n": 50},
                "bins": [{"bin": [0.0, 5.0], "n": 30, "median": 0.0, "robust_sd": 0.01},
                         {"bin": [25.0, 35.0], "n": 30, "median": -0.1, "robust_sd": 0.05},
                         {"bin": [35.0, 60.0], "n": 3, "median": -0.2, "robust_sd": 0.1}]}
        self.projection = {"measures": [{"name": "EPDu", "view": "lat", "views": {"lat": view}},
                                        {"name": "TPW/EPWu", "view": "ap", "views": {"ap": dict(view, verdict="does not survive")}}]}

    def series(self, key, kind="length", mean=35.0):
        return self.C.Series(key, kind, 1.0, self.M.LUMBAR, (mean,) * 6, (4.0,) * 6, (100,) * 6)

    def test_a_length_takes_its_relative_error_times_its_mean(self):
        err, name, how = self.M.xray_error(self.C, self.series("endplate_depth"), self.projection)
        self.assertEqual((name, how), ("EPDu", "same"))
        self.assertAlmostEqual(err, math.hypot(1.0, 0.02 * 35.0))
        err, name, how = self.M.xray_error(self.C, self.series("body_d_mid"), self.projection)
        self.assertEqual(how, "analogue")

    def test_a_measure_that_does_not_survive_or_has_no_stand_in_is_left_out(self):
        err, _, why = self.M.xray_error(self.C, self.series("tp_span_over_width", "ratio", 1.7), self.projection)
        self.assertIsNone(err)
        self.assertIn("does not survive", why)
        err, _, why = self.M.xray_error(self.C, self.series("disc_h_ant"), self.projection)
        self.assertIsNone(err)

    def test_the_angle_costs_information_bin_by_bin(self):
        rows = self.M.angle_cost(self.C, [self.series("endplate_depth")], self.projection, None, 10, 1)
        self.assertEqual([b["bin"] for b in rows[0]["bins"]], [[0.0, 5.0], [25.0, 35.0]])     # the third has 3 readings
        self.assertEqual(rows[0]["ct"], 1.0)
        self.assertGreater(rows[0]["bins"][0]["xray"], rows[0]["bins"][1]["xray"])

    def test_restricted_keeps_one_run_of_levels(self):
        s = self.C.Series("x", "ratio", 0.04, ("T12", "L1", "L2", "L3", "L4"), (1.0,) * 5, (0.1,) * 5, (9,) * 5)
        self.assertEqual(self.M.restricted(self.C, s, self.M.LUMBAR).levels, ("T12", "L1", "L2", "L3", "L4"))
        gap = self.C.Series("x", "ratio", 0.04, ("T12", "L2"), (1.0,) * 2, (0.1,) * 2, (9,) * 2)
        self.assertIsNone(self.M.restricted(self.C, gap, self.M.LUMBAR))

    def test_the_crests_line_tells_log_k_less_its_entropy(self):
        t = self.M.tuffier({"L4": 3, "L5": 1, "L4-L5": 7})
        p = [0.75, 0.25]
        self.assertAlmostEqual(t["information_nats"], math.log(6) + sum(x * math.log(x) for x in p))
        self.assertAlmostEqual(t["named_by_the_commonest"], 0.75)


@unittest.skipIf(MISSING or importlib.util.find_spec("xarray") is None or not (BORDERCALL / "schwingcheck" / "census.py").is_file(),
                 "needs numpy, xarray (bordercall's table) and a bordercall clone beside this repository")
class Census(unittest.TestCase):
    def test_restricts_a_series_to_the_lumbar_levels(self):
        M = load()
        C = M.census_module(BORDERCALL)
        pan, _ = C.panjabi_source()
        s = M.restricted(C, next(m for m in pan.measures if m.key == "endplate"), M.LUMBAR)
        self.assertEqual(s.levels, M.LUMBAR)
        self.assertEqual(len(s.mean), 6)


if __name__ == "__main__":
    unittest.main()
