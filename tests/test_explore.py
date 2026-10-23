"""tools/explore.py, run as the job runs it, the look inside one fetched set (the gate word explore): on a synthetic
Roboflow-style export in a zip, resized to 640 x 640, re-encoded and partly mirrored, of films kept
as a folder beside it, the listing gives the extensions, folders, image sizes, YOLO classes and
tables, and the comparison finds every copied film by content, mirrored ones among them, the
copies whose names survived by name, and no film for the images that are new. It needs numpy,
Pillow and the package's contracts, which the train-cpu environment holds and the required
check's python does not, so the case runs where they import and is skipped elsewhere.

    .pixi/envs/train-cpu/bin/python -m unittest tests/test_explore.py
"""

import importlib.util
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEEDED = ("numpy", "PIL", "pydantic", "icontract", "beartype")
MISSING = [name for name in NEEDED if importlib.util.find_spec(name) is None]


def films(folder, count):
    """Blocky grey films of differing sizes, the shape of a spine film, saved as JPEG."""
    import numpy as np
    from PIL import Image

    rng, made = np.random.default_rng(7), []
    for i in range(count):
        height, width = int(rng.integers(900, 1400)), int(rng.integers(400, 700))
        coarse = rng.normal(0, 1, (height // 20 + 1, width // 20 + 1))
        grey = np.kron(coarse, np.ones((20, 20)))[:height, :width]
        grey = (grey - grey.min()) / np.ptp(grey) * 255
        image = Image.fromarray(grey.astype("uint8"))
        image.save(folder / f"sunhl-1th-{i:02d} A AP.jpg", quality=95)
        made.append(image)
    return made


def export(raw, originals):
    """A Roboflow-style zip: fifteen copies resized and re-encoded, every third mirrored, the first
    five under their own names, and five new images."""
    import numpy as np
    from PIL import Image

    def jpeg(image):
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=70)
        return buffer.getvalue()

    with zipfile.ZipFile(raw / "set.zip", "w") as archive:
        archive.writestr("data.yaml", "names: ['vertebra', 'curve']\nnc: 2\n")
        archive.writestr("meta.csv", "file,label\na,1\nb,2\n")
        for i, original in enumerate(originals[:15]):
            image = original.resize((640, 640))
            if i % 3 == 0:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            stem = f"sunhl-1th-{i:02d}-A-AP" if i < 5 else f"img{i}"
            name = f"train/images/{stem}_jpg.rf.{'ab' * 16}.jpg"
            archive.writestr(name, jpeg(image))
            archive.writestr(name.replace("images", "labels").replace(".jpg", ".txt"), "0 0.5 0.5 0.1 0.1\n1 0.4 0.4 0.2 0.2\n")
        rng = np.random.default_rng(11)
        for i in range(5):
            archive.writestr(f"valid/images/new{i}.jpg", jpeg(Image.fromarray((rng.random((640, 640)) * 255).astype("uint8"))))


@unittest.skipIf(MISSING, f"needs {', '.join(MISSING)}: the train-cpu environment holds them")
class ExploreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.theirs, self.raw = self.tmp / "theirs", self.tmp / "raw"
        self.theirs.mkdir()
        self.raw.mkdir()
        export(self.raw, films(self.theirs, 40))
        self.out = self.tmp / "report.md"

    def report(self, *against):
        args = [sys.executable, str(ROOT / "tools" / "explore.py"), "--id", "example", "--raw", str(self.raw), "--out", str(self.out), "--workers", "2"]
        for pair in against:
            args += ["--against", pair]
        done = subprocess.run(args, capture_output=True, text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return self.out.read_text(encoding="ascii")

    def test_the_listing_says_what_the_set_holds(self):
        text = self.report()
        self.assertIn("  files: 38, images: 20", text)
        self.assertIn("  .jpg: 20 files", text)
        self.assertIn("    labels/: 15", text)
        self.assertIn("  640 x 640 L: 20", text)
        self.assertIn("    names: ['vertebra', 'curve']", text)
        self.assertIn("  class 1: 15 boxes", text)
        self.assertIn("  meta.csv: 2 rows; header: file,label", text)
        self.assertNotIn("## against", text)
        self.assertNotIn(str(self.tmp), text)

    def test_the_comparison_finds_the_copied_films_and_only_them(self):
        text = self.report(f"AASCE-test={self.theirs}")
        self.assertIn("names: 5 of this set's images share a file name", text)
        self.assertIn("the same film (NCC64 >= 0.97): 15 of this set's images, 15 distinct films of AASCE-test, 5 of them mirrored", text)
        self.assertIn("no candidate at all: 5", text)
        self.assertIn("~ sunhl-1th-", text)
        self.assertNotIn(str(self.tmp), text)


if __name__ == "__main__":
    unittest.main()
