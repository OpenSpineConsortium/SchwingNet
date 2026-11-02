"""Tests of tools/annotator_landmarks.py on synthetic bones whose answers are known: a box vertebra's corners, a ball's
centre, a ring's lowest and most medial points, a notch's deepest point, a symphysis's ends and the plane resting on
three spines.

The tool reads masks with numpy, scipy and nibabel, which CI's python3 may lack, so the module is skipped there; run it
with any python that has them:

    python -m unittest tests.test_annotator_landmarks
"""

import importlib.util
import unittest
from pathlib import Path

MISSING = [name for name in ("numpy", "scipy", "nibabel") if importlib.util.find_spec(name) is None]
ROOT = Path(__file__).resolve().parent.parent

if not MISSING:
    import numpy as np

    spec = importlib.util.spec_from_file_location("annotator_landmarks_under_test",
                                                  ROOT / "tools" / "annotator_landmarks.py")
    AL = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(AL)


def lattice(shape, start):
    """An affine of 1 mm voxels whose centres start at `start` (world mm, RAS), and every voxel centre's world point."""
    affine = np.eye(4)
    affine[:3, 3] = start
    idx = np.indices(shape).reshape(3, -1).T
    return affine, idx, idx + np.asarray(start, float)


def box_vertebra():
    """A labelled volume holding one lumbar-sized vertebra drawn in the world's own axes (x right, y anterior, z up): a
    box body 40 mm wide, 30 deep and 24 tall in front of y = 0, its plates at z = 12 and -12, and an arch closing a
    canal 14 mm wide and 15 deep behind it over the body's middle 16 mm. Voxel centres sit on half millimetres, so each
    face lies on a whole one."""
    shape = (60, 70, 50)
    affine, idx, w = lattice(shape, (-29.5, -29.5, -24.5))
    x, y, z = w.T
    body = (np.abs(x) < 20) & (y > 0) & (y < 30) & (np.abs(z) < 12)
    arch_z = np.abs(z) < 8
    pedicles = (np.abs(x) > 7) & (np.abs(x) < 12) & (y > -15) & (y < 0) & arch_z
    lamina = (np.abs(x) < 12) & (y > -20) & (y <= -15) & arch_z
    vol = np.zeros(shape, np.int16)
    vol.reshape(-1)[body | pedicles | lamina] = AL.LEVEL_ID["L3"]
    return vol, affine


def labelled(vol, affine):
    G = AL.engine()["G"]
    return AL.Labelled("test", vol, G.VoxelGrid(affine, vol.shape), {AL.LEVEL_ID["L3"]: "L3"}, np.zeros((0, 3), int))


def mask_points(inside, shape, start):
    """The voxel indices and world points of the voxels whose centres lie inside."""
    affine, idx, w = lattice(shape, start)
    keep = inside(*w.T)
    return affine, idx[keep], w[keep]


def world_frame():
    G = AL.engine()["G"]
    return G.Frame(np.zeros(3), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0]))


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class BoxVertebra(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vol, affine = box_vertebra()
        verts, notes = AL.read_vertebrae(labelled(vol, affine))
        cls.v = verts.get("L3")
        cls.notes = notes
        cls.points, cls.why = AL.vertebra_points(cls.v) if cls.v is not None else ({}, {})

    def near(self, name, want, tol):
        self.assertIn(name, self.points, self.why)
        got = np.asarray(self.points[name], float)
        self.assertLess(float(np.linalg.norm(got - np.asarray(want, float))), tol, f"{name}: {got} against {want}")

    def test_the_engine_reads_the_box(self):
        self.assertIsNotNone(self.v, self.notes)

    def test_sagittal_corners_lie_on_the_box_corners_at_the_midline(self):
        # within 0.8 mm: the engine settles this box's frame 1.4 degrees about its axis (anatomy.settle), which moves a
        # point on the midline 0.4 mm across at the plate's ends
        self.near("posterior_superior", (0, 0, 12.0), 0.8)
        self.near("posterior_inferior", (0, 0, -12.0), 0.8)
        self.near("anterior_superior", (0, 30, 12.0), 0.8)
        self.near("anterior_inferior", (0, 30, -12.0), 0.8)

    def test_plate_centres_lie_on_the_plates_middle(self):
        # column.plate_centre puts the plate on its cells' outermost voxel centres, half a voxel inside the face
        self.near("centre_superior", (0, 15, 11.5), 0.8)
        self.near("centre_inferior", (0, 15, -11.5), 0.8)

    def test_coronal_corners_lie_on_the_plates_lateral_ends_in_its_front_half(self):
        # the plate's plane runs through its cells' outermost centres (scanimport's plate_plane), half a voxel inside
        for name, x, z in (("superior_right", 20, 11.5), ("superior_left", -20, 11.5),
                           ("inferior_right", 20, -11.5), ("inferior_left", -20, -11.5)):
            self.assertIn(name, self.points, self.why)
            got = self.points[name]
            self.assertAlmostEqual(got[0], x, delta=0.6, msg=name)
            self.assertAlmostEqual(got[2], z, delta=0.8, msg=name)
            self.assertGreaterEqual(got[1], 14.0, name)       # the front half of the plate's depth
            self.assertLessEqual(got[1], 30.0, name)

    def test_every_vertebral_point_names_a_construction(self):
        for name in self.points:
            self.assertIn(name, AL.CONSTRUCTIONS)


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Pelvis(unittest.TestCase):
    def test_a_balls_centre_is_found_beside_its_neck_and_shaft(self):
        centre, radius = np.array([4.0, -3.0, 10.0]), 23.0
        axis = np.array([0.6, 0.0, -0.8])

        def inside(x, y, z):
            p = np.stack([x, y, z], 1) - centre
            along = p @ axis
            off = np.linalg.norm(p - along[:, None] * axis, axis=1)
            neck = (along > 0) & (along < 60) & (off < 13)
            shaft = (np.abs(p[:, 0] - 40) < 12) & (np.abs(p[:, 1]) < 12) & (p[:, 2] < -40) & (p[:, 2] > -90)
            return (np.linalg.norm(p, axis=1) < radius) | neck | shaft

        affine, idx, _ = mask_points(inside, (110, 70, 140), (-40.5, -38.5, -100.5))
        got = AL.ball_centre(idx, AL.engine()["G"].VoxelGrid(affine, (110, 70, 140)))
        self.assertIsNotNone(got)
        self.assertLess(float(np.linalg.norm(got["centre"] - centre)), 1.0)
        self.assertAlmostEqual(got["radius"], radius, delta=1.0)

    def test_a_rings_lowest_and_most_medial_points(self):
        # a right hip's obturator ring: 15 mm inside, 27 outside, 10 thick from front to back, its middle 15 mm medial
        # to (left of) and 40 below the hip centre
        middle = np.array([-15.0, 0.0, -40.0])

        def inside(x, y, z):
            r = np.hypot(x - middle[0], z - middle[2])
            return (r > 15) & (r < 27) & (np.abs(y) < 5)

        _, _, pts = mask_points(inside, (70, 20, 70), (-49.5, -9.5, -74.5))
        got = AL.obturator(pts, world_frame(), np.zeros(3), "right")
        self.assertIsNotNone(got)
        self.assertLess(float(np.linalg.norm(got["inferior"] - (middle + [0, 0, -16.0]))), 2.0, got)
        self.assertLess(float(np.linalg.norm(got["medial"] - (middle + [-16.0, 0, 0]))), 2.0, got)
        self.assertEqual(got["pitch_deg"], 0)
        self.assertEqual(got["yaw_deg"], 0)

    def test_a_notchs_deepest_point(self):
        # a plate in the sagittal plane, its posterior border at y = -60 with a round notch 20 mm deep at z = 0
        def inside(x, y, z):
            plate = (np.abs(x) < 3) & (y > -60) & (y < 20) & (np.abs(z) < 60)
            return plate & (np.hypot(y + 60, z) > 20)

        _, _, pts = mask_points(inside, (10, 90, 130), (-4.5, -64.5, -64.5))
        got = AL.sciatic_notch(pts, world_frame(), np.zeros(3))
        self.assertIsNotNone(got)
        self.assertLess(float(np.linalg.norm(got["point"] - [0, -39.0, 0])), 2.0, got)
        self.assertAlmostEqual(got["depth_mm"], 20.0, delta=2.0)

    def test_a_symphysis_ends_on_each_pubis(self):
        def pubis(sign):
            def inside(x, y, z):
                return (sign * x > 3) & (sign * x < 30) & (y > 0) & (y < 15) & (z > -60) & (z < -20)
            return mask_points(inside, (80, 30, 60), (-39.5, -9.5, -69.5))[2]

        got = AL.symphysis(pubis(1.0), pubis(-1.0), world_frame())
        self.assertIsNotNone(got)
        for side in ("right", "left"):
            self.assertAlmostEqual(got[f"superior_{side}"][2], -20.5, delta=1.5)
            self.assertAlmostEqual(got[f"inferior_{side}"][2], -59.5, delta=1.5)
        self.assertGreater(got["superior_right"][0], 0)
        self.assertLess(got["superior_left"][0], 0)
        self.assertAlmostEqual(got["gap_mm"], 7.0, delta=0.1)

    def test_the_anterior_pelvic_plane_rests_on_the_spines_and_the_pubis(self):
        rng = np.random.default_rng(3)
        ilium = rng.uniform([-30, -40, 10], [30, 10, 80], (4000, 3))
        right, left = ilium + [70, 0, 0], ilium + [-70, 0, 0]
        pubis = rng.uniform([5, -10, -60], [35, 5, -30], (1500, 3))
        spines = {"right": np.array([75.0, 30.0, 55.0]), "left": np.array([-72.0, 28.0, 52.0])}
        tubercle = np.array([20.0, 25.0, -45.0])
        right = np.vstack([right, spines["right"], pubis])
        left = np.vstack([left, spines["left"], pubis * [-1, 1, 1], tubercle * [-1, 1, 1] + [0, -8, 0]])
        right = np.vstack([right, tubercle])
        got = AL.anterior_plane(right, left, world_frame())
        self.assertTrue(got["settled"])
        for side in ("right", "left"):
            self.assertLess(float(np.linalg.norm(got[side] - spines[side])), 1e-6)
        self.assertLess(float(np.linalg.norm(got["pubic"] - tubercle)), 1e-6)


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}")
class Frames(unittest.TestCase):
    def test_lps_turns_x_and_y(self):
        self.assertEqual(list(AL.to_lps([1.0, 2.0, 3.0])), [-1.0, -2.0, 3.0])

    def test_the_held_out_specimen_is_refused(self):
        with self.assertRaises(ValueError):
            AL.refuse_held_out(["17-1882", "18-1109"])
        self.assertEqual(AL.refuse_held_out(["17-1882"]), ["17-1882"])

    def test_every_person_point_has_constructions_in_the_table(self):
        for kind, constructions in AL.PERSON.items():
            for c in constructions:
                self.assertIn(c, AL.CONSTRUCTIONS, kind)

    def test_a_person_row_measures_the_distance_in_lps(self):
        person = {"FH-l": [10.0, 0.0, 0.0], "ASIS-R": [0.0, 0.0, 0.0], "XYZ-l": [0.0, 0.0, 0.0]}
        readings = {"totalseg": {"points": {"hip_centre.left": {"lps": [13.0, 4.0, 0.0]},
                                            "asis.right": {"lps": [0.0, 0.0, 2.0]}}},
                    "authors": {"points": {"hip_centre.left": {"lps": [10.0, 0.0, 1.0]}}}}
        rows = {(r["landmark"], r["construction"]): r for r in AL.person_rows("c", person, readings)}
        self.assertEqual(rows[("FH-l", "hip_centre")]["totalseg"], 5.0)
        self.assertEqual(rows[("FH-l", "hip_centre")]["authors"], 1.0)
        self.assertIsNone(rows[("FH-l", "femoral_head")]["totalseg"])
        self.assertEqual(rows[("ASIS-R", "asis")]["totalseg"], 2.0)
        self.assertNotIn(("XYZ-l", "asis"), rows)
        table = {(t["landmark"], t["construction"]): t for t in AL.summary(list(rows.values()), ["totalseg", "authors"])}
        self.assertTrue(table[("FH-l", "hip_centre")]["totalseg"]["agrees"])
        self.assertEqual(table[("FH (both sides)", "hip_centre")]["authors"]["n"], 1)


if __name__ == "__main__":
    unittest.main()
