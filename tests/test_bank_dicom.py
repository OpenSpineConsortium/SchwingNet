"""The DICOM path of tools/bank.py (#44): the pixel array windowed to 8 bits, the person and the
view from the header, members read inside a zip, the same bank whatever the number of workers,
and a placeholder person refused. These run where pydicom is installed (the train environment)."""

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import tempfile
import unittest

try:
    import numpy
    import pydicom
    from PIL import Image
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid
except ImportError:
    pydicom = None

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool  # so a worker process can find the functions it is handed
    spec.loader.exec_module(tool)
    return tool


def dicom(patient, study, view, seed, photometric="MONOCHROME2", **tags):
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    data = FileDataset("x.dcm", {}, file_meta=meta, preamble=b"\0" * 128)
    data.PatientID, data.StudyInstanceUID, data.ViewPosition = patient, study, view
    data.Manufacturer, data.KVP, data.ImagerPixelSpacing = "Maker", 80, [0.15, 0.15]
    data.Modality, data.PhotometricInterpretation = "DX", photometric
    data.Rows, data.Columns, data.SamplesPerPixel = 24, 32, 1
    data.BitsAllocated, data.BitsStored, data.HighBit, data.PixelRepresentation = 16, 12, 11, 0
    for name, value in tags.items():
        setattr(data, name, value)
    grid = (numpy.arange(24 * 32).reshape(24, 32) * (seed + 3)) % 4096
    data.PixelData = grid.astype(numpy.uint16).tobytes()
    out = io.BytesIO()
    data.save_as(out, enforce_file_format=True)
    return out.getvalue()


def recipe(tmp, **changes):
    shipped = json.loads((ROOT / "grid" / "banks" / "vindr_spinexr.json").read_text(encoding="utf-8"))
    shipped.update(raw=str(tmp / "raw"), bank=str(tmp / "bank"), **changes)
    path = tmp / "recipe.json"
    path.write_text(json.dumps(shipped), encoding="utf-8")
    return path


def write_set(raw):
    (raw / "train_images").mkdir(parents=True)
    (raw / "test_images").mkdir(parents=True)
    (raw / "train_images" / "a1.dicom").write_bytes(dicom("", "1.2.3.1", "AP", 1))
    (raw / "train_images" / "a2.dicom").write_bytes(dicom("", "1.2.3.1", "LL", 2))
    (raw / "test_images" / "b1.dicom").write_bytes(dicom("anonymous", "1.2.3.2", "PA", 3, "MONOCHROME1"))


def run(tool, argv):
    """The tool's exit code, its standard output and its standard error."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tool.main(argv)
    return code, out.getvalue(), err.getvalue()


def counts_of(tool, path, *extra):
    code, out, err = run(tool, ["--recipe", str(path), *extra])
    if code != 0:
        raise AssertionError(err)
    return json.loads(out)


def digests(folder):
    """The frames' and the metas' digests: BANK.json, the stamp of what made the bank, names the
    raw files' times, which two raw copies never share (#260)."""
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(folder).rglob("*")
            if p.is_file() and p.name != "BANK.json"}


@unittest.skipIf(pydicom is None, "pydicom, numpy and Pillow are the train environment's")
class DicomBankTest(unittest.TestCase):
    def setUp(self):
        self.tool = load("bank")
        self.scratch = tempfile.TemporaryDirectory()
        self.tmp = Path(self.scratch.name)

    def tearDown(self):
        self.scratch.cleanup()

    def test_a_dicom_set_banks_with_person_view_and_device_from_the_header(self):
        write_set(self.tmp / "raw")
        path = recipe(self.tmp)
        plan = counts_of(self.tool, path)
        self.assertEqual((plan["frames"], plan["persons"]), (3, 2))
        self.assertEqual(plan["transfer_syntaxes"], {"1.2.840.10008.1.2.1": 3})
        counts = counts_of(self.tool, path, "--run")
        self.assertEqual((counts["written"], counts["most_frames_per_person"]), (3, 2))
        meta = json.loads((self.tmp / "bank" / "meta" / "train_images_a2.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["case"], meta["view"]["lat_from_ap_deg"]), ("1.2.3.1", 90.0))
        self.assertEqual((meta["device"]["make"], meta["device"]["kvp"], meta["px_mm"]), ("Maker", 80.0, 0.15))
        self.assertNotIn("PatientID", meta["dicom"])
        with Image.open(self.tmp / "bank" / "images" / "train" / "test_images_b1.png") as image:
            self.assertEqual((image.mode, image.size), ("L", (32, 24)))

    def test_monochrome1_is_inverted_and_flat_frames_are_refused(self):
        straight = self.tool.dicom_as_png(dicom("p", "1.2.5", "AP", 5))[0]
        inverted = self.tool.dicom_as_png(dicom("p", "1.2.5", "AP", 5, "MONOCHROME1"))[0]
        a = numpy.asarray(Image.open(io.BytesIO(straight)), dtype=int)
        b = numpy.asarray(Image.open(io.BytesIO(inverted)), dtype=int)
        self.assertLessEqual(int(numpy.abs(a + b - 255).max()), 1)
        data = pydicom.dcmread(io.BytesIO(dicom("p", "1.2.5", "AP", 0)))
        data.PixelData = numpy.zeros((24, 32), dtype=numpy.uint16).tobytes()
        out = io.BytesIO()
        data.save_as(out)
        with self.assertRaisesRegex(self.tool.BankError, "flat"):
            self.tool.dicom_as_png(out.getvalue())

    def test_the_bank_is_the_same_bytes_with_four_workers(self):
        write_set(self.tmp / "raw")
        counts_of(self.tool, recipe(self.tmp), "--run")
        other = self.tmp / "again"
        other.mkdir()
        write_set(other / "raw")
        counts_of(self.tool, recipe(other), "--run", "--workers", "4")
        self.assertEqual(digests(self.tmp / "bank"), digests(other / "bank"))
        self.assertEqual(len(digests(other / "bank")), 6)

    def test_a_placeholder_in_every_person_tag_is_refused(self):
        raw = self.tmp / "raw" / "train_images"
        raw.mkdir(parents=True)
        for index in range(4):
            (raw / f"c{index}.dicom").write_bytes(dicom("VINDR", "1.2.3.9", "AP", index))
        code, _, err = run(self.tool, ["--recipe", str(recipe(self.tmp, max_frames_per_person=3))])
        self.assertEqual(code, 2)
        self.assertIn("more than 3 frames", err)

    def test_one_tag_keys_the_whole_source(self):
        raw = self.tmp / "raw" / "train_images"
        raw.mkdir(parents=True)
        (raw / "ap.dicom").write_bytes(dicom("P1", "1.2.7.1", "AP", 1))
        (raw / "lat.dicom").write_bytes(dicom("", "1.2.7.1", "LL", 2))
        counts = counts_of(self.tool, recipe(self.tmp))
        self.assertEqual((counts["persons"], counts["person_tag"], counts["studies"]), (1, "StudyInstanceUID", 1))

    def test_a_key_finer_than_the_study_is_refused(self):
        raw = self.tmp / "raw" / "train_images"
        raw.mkdir(parents=True)
        (raw / "ap.dicom").write_bytes(dicom("image-hash-1", "1.2.8.1", "AP", 1))
        (raw / "lat.dicom").write_bytes(dicom("image-hash-2", "1.2.8.1", "LL", 2))
        code, _, err = run(self.tool, ["--recipe", str(recipe(self.tmp))])
        self.assertEqual(code, 2)
        self.assertIn("finer than the study", err)

    def test_a_zero_exposure_is_a_blank_and_the_finer_tags_win(self):
        raw = self.tmp / "raw" / "train_images"
        raw.mkdir(parents=True)
        (raw / "a.dicom").write_bytes(dicom("P1", "1.2.9.1", "AP", 1, Exposure=0, ExposureInuAs=800))
        (raw / "b.dicom").write_bytes(dicom("P2", "1.2.9.2", "AP", 2, KVP=0, Exposure=0))
        counts_of(self.tool, recipe(self.tmp), "--run")
        a = json.loads((self.tmp / "bank" / "meta" / "train_images_a.json").read_text(encoding="utf-8"))
        b = json.loads((self.tmp / "bank" / "meta" / "train_images_b.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(a["device"]["mas"], 0.8)
        self.assertEqual((b["device"]["kvp"], b["device"]["mas"]), (None, None))

    def test_palette_pixels_are_refused_by_name(self):
        raw = self.tmp / "raw" / "train_images"
        raw.mkdir(parents=True)
        (raw / "p.dicom").write_bytes(dicom("P1", "1.2.10.1", "AP", 1, "PALETTE COLOR"))
        code, _, err = run(self.tool, ["--recipe", str(recipe(self.tmp)), "--run"])
        self.assertEqual(code, 2)
        self.assertIn("train_images/p.dicom: photometric interpretation 'PALETTE COLOR'", err)

    def test_lumos_members_are_read_inside_their_zips_by_the_shipped_recipe(self):
        shipped = json.loads((ROOT / "grid" / "banks" / "lumos.json").read_text(encoding="utf-8"))
        raw = self.tmp / "raw"
        raw.mkdir()
        with zipfile.ZipFile(raw / "lumos_x_001_280_dcm.zip", "w") as archive:
            archive.writestr("lumos_x/lumos_x_001/lumos_x_001_1.dcm", dicom("", "1.2.4.1", "AP", 1))
            archive.writestr("lumos_x/lumos_x_001/lumos_x_001_2.dcm", dicom("", "1.2.4.1", "OBL", 2))
            archive.writestr("lumos_x/lumos_x_002/lumos_x_002_1.dcm", dicom("", "1.2.4.2", "LL", 3))
        with zipfile.ZipFile(raw / "lumos_ct_001_070_dcm.zip", "w") as archive:
            archive.writestr("lumos_ct/lumos_ct_001/lumos_ct_001_1.dcm", dicom("", "1.2.4.3", "", 4))
        shipped.update(raw=str(raw), bank=str(self.tmp / "bank"))
        path = self.tmp / "lumos.json"
        path.write_text(json.dumps(shipped), encoding="utf-8")
        counts = counts_of(self.tool, path, "--run")
        self.assertEqual((counts["frames"], counts["persons"]), (3, 2))
        metas = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((self.tmp / "bank" / "meta").glob("*.json"))]
        self.assertEqual([m["case"] for m in metas], ["001", "001", "002"])
        self.assertEqual([m["view"]["lat_from_ap_deg"] for m in metas], [0.0, None, 90.0])


if __name__ == "__main__":
    unittest.main()
