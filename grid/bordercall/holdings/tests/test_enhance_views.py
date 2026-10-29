"""The reader pictures of holdings/enhance_views.py, on a small column of boxes with two ribs.

Run from the repository's root with `python -m unittest discover -s holdings/tests -t .`."""
import os
import tempfile
import unittest

import nibabel as nib
import numpy as np
from PIL import Image

from holdings import enhance_views as V


def per_label(volume, labels, axis):
    """The slow way, one pass per label, that the one-pass projection must equal."""
    shape = [n for i, n in enumerate(volume.shape) if i != axis]
    best, most = np.zeros(shape, np.uint8), np.zeros(shape, np.int32)
    for label in sorted(labels):
        count = (volume == label).sum(axis=axis, dtype=np.int32)
        better = count > most
        best[better], most[better] = label, count[better]
    return best, most


def small_study():
    """T12 over L1 over the sacrum, a rib 12 on each side of T12, on a 2 mm grid with the head last."""
    vert = np.zeros((24, 12, 30), np.uint8)
    vert[8:16, 3:9, 20:26] = 19
    vert[8:16, 3:9, 12:18] = 20
    vert[7:17, 2:10, 2:10] = 28
    rib = np.zeros_like(vert)
    rib[2:8, 4:7, 22:24] = 12
    rib[16:22, 4:7, 22:24] = 25
    return vert, rib


class Projection(unittest.TestCase):
    def test_one_pass_equals_a_pass_per_label(self):
        volume = np.random.default_rng(7).choice([0, 0, 0, 3, 5, 19, 28], size=(9, 7, 11)).astype(np.uint8)
        for axis in range(3):
            fast = V.dominant_label(volume, [3, 5, 19, 28], axis)
            slow = per_label(volume, [3, 5, 19, 28], axis)
            self.assertTrue((fast[0] == slow[0]).all() and (fast[1] == slow[1]).all())

    def test_no_labels_gives_an_empty_plane(self):
        best, most = V.dominant_label(np.zeros((3, 4, 5), np.uint8), [], 1)
        self.assertEqual(best.shape, (3, 5))
        self.assertFalse(best.any() or most.any())


class Pictures(unittest.TestCase):
    def test_a_study_gives_a_front_and_a_side_picture(self):
        vert, rib = small_study()
        affine = np.diag([2.0, 2.0, 2.0, 1.0])
        with tempfile.TemporaryDirectory() as folder:
            for name, data in (("masks", vert), ("ribs", rib)):
                os.makedirs(os.path.join(folder, name))
                nib.save(nib.Nifti1Image(data, affine), os.path.join(folder, name, "0001.nii.gz"))
            ids = os.path.join(folder, "ids.txt")
            with open(ids, "w") as handle:
                handle.write("0001\n")
            out = os.path.join(folder, "out")
            V.main([os.path.join(folder, "masks"), os.path.join(folder, "ribs"), ids, out])
            front = Image.open(os.path.join(out, "0001-front.png"))
            side = Image.open(os.path.join(out, "0001-side.png"))
            self.assertGreater(front.size[1], front.size[0] / 2)
            self.assertEqual(front.size[1], side.size[1])

    def test_masks_on_different_grids_are_refused(self):
        vert, rib = small_study()
        with tempfile.TemporaryDirectory() as folder:
            for name, data, zoom in (("masks", vert, 2.0), ("ribs", rib, 1.0)):
                os.makedirs(os.path.join(folder, name))
                image = nib.Nifti1Image(data, np.diag([zoom, zoom, zoom, 1.0]))
                nib.save(image, os.path.join(folder, name, "0001.nii.gz"))
            with self.assertRaises(ValueError):
                V.draw_study(os.path.join(folder, "masks"), os.path.join(folder, "ribs"), "0001", folder)


if __name__ == "__main__":
    unittest.main()
