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
    from PIL import Image, ImageCms
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.encaps import encapsulate
    from pydicom.uid import (JPEG2000, ExplicitVRLittleEndian, JPEG2000Lossless, JPEGBaseline8Bit, RLELossless,
                             generate_uid)
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


def film(rows=384, columns=320, seed=0):
    """A 12-bit film as the second review of #252 drew one to measure the bank's budget: a body,
    six vertebra-like blobs and some noise, small enough to bank in a test."""
    rng = numpy.random.default_rng(seed)
    y, x = numpy.mgrid[0:rows, 0:columns]
    base = 1200 + 1400 * numpy.exp(-((x - columns / 2) / (columns / 5)) ** 2)
    for k in range(6):
        base += 600 * numpy.exp(-(((x - columns / 2) / (columns / 10)) ** 2 + ((y - rows * (k + 1) / 7) / (rows / 22)) ** 2))
    return numpy.clip(base + rng.normal(0, 15, base.shape), 0, 4095).astype(numpy.uint16)


def shipped_as(pixels, syntax, **options):
    """The film as a publisher may ship it: one DICOM file in a transfer syntax pydicom writes."""
    data = pydicom.dcmread(io.BytesIO(dicom("P1", "1.2.11.1", "AP", 1)))
    data.Rows, data.Columns = pixels.shape
    data.PixelData = pixels.astype(numpy.uint16).tobytes()
    if syntax != ExplicitVRLittleEndian:
        data.compress(syntax, **options)
    out = io.BytesIO()
    data.save_as(out, enforce_file_format=True)
    return out.getvalue()


def jpeg_of(grey, quality, **options):
    out = io.BytesIO()
    Image.fromarray(grey, mode="L").save(out, format="JPEG", quality=quality, **options)
    return out.getvalue()


def shipped_as_jpeg(grey, quality):
    """The 8-bit film as a JPEG baseline DICOM file, which pydicom reads and does not write."""
    data = pydicom.dcmread(io.BytesIO(dicom("P1", "1.2.11.1", "AP", 1)))
    data.file_meta.TransferSyntaxUID = JPEGBaseline8Bit
    data.Rows, data.Columns = grey.shape
    data.BitsAllocated, data.BitsStored, data.HighBit = 8, 8, 7
    data.PixelData = encapsulate([jpeg_of(grey, quality)])
    data["PixelData"].VR = "OB"
    data["PixelData"].is_undefined_length = True
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


def banked_bytes(bank):
    """What a bank's frames take, which its shard copies once more (tools/ingest.py)."""
    return sum(p.stat().st_size for p in (Path(bank) / "images").rglob("*.png"))


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
        # the bound reads the members' headers inside their zips as the bank reads their frames
        bound = counts_of(self.tool, path, "--bound")
        self.assertEqual(bound["frames"], 3)
        self.assertGreaterEqual(bound["most_bytes"], 2 * banked_bytes(self.tmp / "bank"))

    def test_the_bound_holds_for_every_transfer_syntax_and_above_what_a_lossy_film_writes(self):
        # The bank word budgets a DICOM set at twice the raw copy's bytes, which an uncompressed or a
        # lossless film keeps under; a lossy one does not, since its file holds fewer bytes than its
        # pixels take as PNG (the second review of #252). The bound the bank job is admitted for
        # reads the rows and columns from each header alone and holds whatever the syntax.
        pixels = film()
        grey = self.tool.window_8bit(numpy, pixels.astype(numpy.float64))
        shipped = {"uncompressed": shipped_as(pixels, ExplicitVRLittleEndian), "rle": shipped_as(pixels, RLELossless),
                   "j2k_lossless": shipped_as(pixels, JPEG2000Lossless), "j2k_lossy": shipped_as(pixels, JPEG2000, j2k_cr=[10]),
                   "jpeg_q90": shipped_as_jpeg(grey, 90)}
        raw = self.tmp / "raw" / "train_images"
        raw.mkdir(parents=True)
        for name, data in shipped.items():
            (raw / f"{name}.dicom").write_bytes(data)
        path = recipe(self.tmp)
        bound = counts_of(self.tool, path, "--bound")
        self.assertEqual(bound["frames"], 5)
        self.assertFalse((self.tmp / "bank").exists(), "the bound writes nothing")
        counts_of(self.tool, path, "--run")
        for name, data in shipped.items():
            written = (self.tmp / "bank" / "images" / "train" / f"train_images_{name}.png").stat().st_size
            at_most = self.tool.frame_at_most((str(self.tmp / "raw"), f"train_images/{name}.dicom", "dcm"))
            self.assertLessEqual(written, at_most, name)
            if name in ("j2k_lossy", "jpeg_q90"):
                # so a set of such films takes more than twice its raw copy in the bank and its shard
                self.assertGreater(written, len(data), f"{name}: a lossy film writes more than its file")
        self.assertGreaterEqual(bound["most_bytes"], 2 * banked_bytes(self.tmp / "bank"))

    def test_the_bound_holds_for_each_format_pillow_reads_and_above_a_low_quality_jpeg(self):
        # JPEG, TIFF, BMP and a PNG of more than 8 bits are written as Pillow's 8-bit grey PNG, which
        # carries over the ICC profile the file holds; a JPEG below quality 95 can take more than
        # three times its bytes as PNG, beyond the six times the raw copy the word budgets for it
        # and its shard (the second review of #252).
        pixels = film()
        grey = self.tool.window_8bit(numpy, pixels.astype(numpy.float64))
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        colour = io.BytesIO()
        Image.fromarray(numpy.stack([grey] * 3, axis=-1), mode="RGB").save(colour, format="JPEG", quality=60,
                                                                          icc_profile=profile)
        wide = {}
        for image_format in ("png", "tiff"):
            out = io.BytesIO()
            Image.fromarray(pixels).save(out, format=image_format.upper())
            wide[image_format] = out.getvalue()
        bitmap = io.BytesIO()
        Image.fromarray(grey, mode="L").save(bitmap, format="BMP")
        frames = {"q50.jpg": jpeg_of(grey, 50), "q75.jpg": jpeg_of(grey, 75), "q95.jpg": jpeg_of(grey, 95),
                  "colour.jpg": colour.getvalue(), "wide.png": wide["png"], "wide.tiff": wide["tiff"],
                  "grey.bmp": bitmap.getvalue()}
        for name, data in frames.items():
            (self.tmp / name).write_bytes(data)
            written, _, _ = self.tool.as_png(data, name.rsplit(".", 1)[1])
            self.assertLessEqual(len(written), self.tool.frame_at_most((str(self.tmp), name, name.rsplit(".", 1)[1])), name)
        written, _, _ = self.tool.as_png(frames["q75.jpg"], "jpg")
        self.assertGreater(2 * len(written), 6 * len(frames["q75.jpg"]))
        with Image.open(io.BytesIO(self.tool.as_png(frames["colour.jpg"], "jpg")[0])) as carried:
            self.assertEqual(carried.info.get("icc_profile"), profile)


if __name__ == "__main__":
    unittest.main()
