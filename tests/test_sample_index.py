"""tools/sample_index.py: roots, units, a scan in two tasks, the merge's joins and the manifest.

The DICOM part needs pydicom, so it runs in the train-cpu environment
(`pixi run -e train-cpu python -m unittest tests.test_sample_index`) and skips under plain
python3; the rest runs anywhere."""

import importlib.util
import json
import os
import sqlite3
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HAS_PYDICOM = importlib.util.find_spec("pydicom") is not None


def load():
    spec = importlib.util.spec_from_file_location("sample_index_under_test", ROOT / "tools" / "sample_index.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiff(path, width, height):
    entries = [(256, 3, 1, width), (257, 3, 1, height), (258, 3, 1, 16), (277, 3, 1, 1)]
    body = b"II*\x00" + struct.pack("<I", 8) + struct.pack("<H", len(entries))
    body += b"".join(struct.pack("<HHIHH", tag, kind, n, value, 0) for tag, kind, n, value in entries)
    path.write_bytes(body + struct.pack("<I", 0) + b"\x00" * 64)


def png(path, width, height):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\x00" * width for _ in range(height))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def dicom(path, modality, series, sop, age):
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"
    meta.MediaStorageSOPInstanceUID = sop
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    data = FileDataset(str(path), {}, file_meta=meta, preamble=b"\x00" * 128)
    data.Modality, data.SeriesInstanceUID, data.SOPInstanceUID = modality, series, sop
    data.StudyInstanceUID, data.PatientID, data.PatientAge, data.PatientSex = "1.2.3", "P1", age, "F"
    data.Rows, data.Columns, data.BitsStored, data.KVP = 32, 48, 12, "80"
    data.Manufacturer = "Acme"
    data.save_as(str(path), enforce_file_format=True) if pydicom.__version__ >= "3" else data.save_as(str(path))


def lay_out(tmp):
    data = tmp / "data"
    films = data / "nhanes_full"
    films.mkdir(parents=True)
    for number in range(4):
        tiff(films / f"film_0001234{number}.tif", 300 + number, 400)
    labels = data / "nhanes_annotated" / "extracted"
    labels.mkdir(parents=True)
    (labels / "film_00012340_label.pkl").write_bytes(b"\x80\x04N.")
    (films / "variables.csv").write_text("film,age,sex\nfilm_00012340.tif,45,M\nfilm_00012341.tif,61,F\n", encoding="utf-8")
    coco = data / "coco_set"
    (coco / "images").mkdir(parents=True)
    png(coco / "images" / "a1001.png", 20, 10)
    png(coco / "images" / "a1002.png", 20, 10)
    (coco / "boxes.json").write_text(json.dumps({
        "images": [{"id": 1, "file_name": "images/a1001.png"}],
        "annotations": [{"image_id": 1, "category_id": 3, "bbox": [1, 2, 3, 4]}],
        "categories": [{"id": 3, "name": "L5"}]}), encoding="utf-8")
    (data / "_samples").mkdir()
    return data


class SampleIndexTest(unittest.TestCase):
    def build(self, extra=None):
        tool = load()
        tmp = Path(tempfile.mkdtemp())
        data = lay_out(tmp)
        if extra:
            extra(data)
        sources = tmp / "sources.json"
        sources.write_text(json.dumps({"sources": [
            {"id": "nhanes2_cdc_films", "status": "on_disk", "annotation": {"status": ["pseudo"]},
             "locations": [{"path": str(data / "nhanes_full"), "role": "raw", "storage": "CEPH"}]},
            {"id": "nhanes2_zenodo_landmarks", "status": "on_disk",
             "locations": [{"path": str(data / "nhanes_annotated"), "role": "raw", "storage": "CEPH"}]},
            {"id": "gone", "status": "deleted", "locations": [{"path": "/nowhere", "role": "raw"}]}]}),
            encoding="utf-8")
        registry = tmp / "registry"
        registry.mkdir()
        run = tmp / "run"
        run.mkdir()
        tool.main(["roots", "--data-root", str(data), "--sources", str(sources), "--registry", str(registry),
                   "--out", str(run / "roots.tsv")])
        tool.main(["units", "--roots", str(run / "roots.tsv"), "--out", str(run / "units.tsv")])
        for task in range(2):
            tool.main(["scan", "--run", str(run), "--task", str(task), "--tasks", "2", "--workers", "2"])
        tool.main(["merge", "--run", str(run)])
        return tool, run, sqlite3.connect(run / "samples.sqlite")

    def test_roots_name_sources_and_skip_tool_folders(self):
        _, run, db = self.build()
        sources = {row[0] for row in db.execute("SELECT sources FROM root")}
        self.assertEqual(sources, {"nhanes2_cdc_films", "nhanes2_zenodo_landmarks", "unmapped:coco_set"})

    def test_formats_and_shapes_from_headers(self):
        _, _, db = self.build()
        rows = dict(db.execute("SELECT name, format || ' ' || width || 'x' || height FROM file WHERE role = 'image'"))
        self.assertEqual(rows["film_00012341.tif"], "tiff 301x400")
        self.assertEqual(rows["a1001.png"], "png 20x10")

    def test_annotated_by_stem_elsewhere_and_by_coco(self):
        _, _, db = self.build()
        annotated = dict(db.execute("SELECT name, annotated FROM file WHERE role = 'image'"))
        self.assertEqual(annotated["film_00012340.tif"], 1)
        self.assertEqual(annotated["film_00012341.tif"], 0)
        self.assertEqual(annotated["a1001.png"], 1)
        self.assertEqual(annotated["a1002.png"], 0)

    def test_sidecar_rows_join_their_samples(self):
        _, _, db = self.build()
        meta = dict(db.execute("""SELECT m.col, m.value FROM sample_meta m JOIN file f ON f.id = m.file_id
                                  WHERE f.name = 'film_00012341.tif'"""))
        self.assertEqual(meta["age"], "61")
        self.assertEqual(meta["sex"], "F")

    def test_manifest_holds_aggregates_only(self):
        _, run, _ = self.build()
        result = json.loads((run / "MANIFEST.json").read_text(encoding="utf-8"))
        films = result["nhanes2_cdc_films"]
        self.assertEqual((films["images"], films["annotated"]), (4, 1))
        text = (run / "MANIFEST.md").read_text(encoding="utf-8")
        self.assertIn("| nhanes2_cdc_films | 5 |", text)
        self.assertNotIn("film_0001234", (run / "MANIFEST.json").read_text(encoding="utf-8"))

    def test_manifest_takes_an_unreadable_file(self):
        # A file the scan could not open has no format and the role unreadable, beside named
        # formats in its group: the first grid merge failed writing MANIFEST.json on just that.
        tool, run, db = self.build()
        db.execute("UPDATE file SET format = NULL, role = 'unreadable', error = 'PermissionError' "
                   "WHERE name = 'film_00012341.tif'")
        db.commit()
        tool.report(run / "samples.sqlite", run / "again.json", run / "again.md")
        formats = json.loads((run / "again.json").read_text(encoding="utf-8"))["nhanes2_cdc_films"]["formats"]
        self.assertEqual(formats["unknown"], 1)

    def test_a_requeued_task_skips_what_it_finished(self):
        tool, run, db = self.build()
        before = db.execute("SELECT COUNT(*) FROM file").fetchone()[0]
        units, files = tool.scan(run, 0, 2, False, 2)
        self.assertEqual(files, 0)
        self.assertGreater(units, 0)
        tool.merge(run)
        again = sqlite3.connect(run / "samples.sqlite").execute("SELECT COUNT(*) FROM file").fetchone()[0]
        self.assertEqual(again, before)

    def test_merge_cache_reads_only_ascii_digits(self):
        tool = load()
        saved = os.environ.get("SAMPLES_CACHE_MB")
        try:
            for value, expected in (("512", 512 * 1024), ("", 32 * 1024 * 1024),
                                    ("\u0663", 32 * 1024 * 1024), ("9" * 5000, 32 * 1024 * 1024)):
                os.environ["SAMPLES_CACHE_MB"] = value
                self.assertEqual(tool.merge_cache_kib(), expected)
        finally:
            if saved is None:
                os.environ.pop("SAMPLES_CACHE_MB", None)
            else:
                os.environ["SAMPLES_CACHE_MB"] = saved

    def test_keys_meet_across_paths_and_zeros(self):
        tool = load()
        self.assertEqual(tool.key_of("images/01234.PNG"), "1234")
        self.assertIsNone(tool.key_of("images/0012.PNG"))
        self.assertEqual(tool.key_of("sub/scan_001.nii.gz"), "scan_001")
        self.assertEqual(tool.bare_of("img_0007_mask"), "img_0007")
        self.assertEqual(tool.digit_runs("film_00012340"), ["12340"])

    @unittest.skipUnless(HAS_PYDICOM, "pydicom is in the train-cpu environment")
    def test_dicom_headers_whole_for_films_and_once_per_series(self):
        def add(data):
            folder = data / "dicom_set"
            folder.mkdir()
            dicom(folder / "dx.dcm", "DX", "9.1", "9.1.1", "045Y")
            for number in range(3):
                dicom(folder / f"ct{number}.dcm", "CT", "9.2", f"9.2.{number}", "070Y")
        _, _, db = self.build(add)
        full = dict(db.execute("SELECT modality, SUM(header_full) FROM file WHERE format = 'dicom' GROUP BY modality"))
        self.assertEqual(full, {"CT": 1, "DX": 1})
        ages = {row[0] for row in db.execute("""SELECT h.value FROM sample_header h JOIN file f ON f.id = h.file_id
                                                WHERE f.name = 'ct2.dcm' AND h.keyword = 'PatientAge'""")}
        self.assertEqual(ages, {"070Y"})
        self.assertNotIn("PixelData", {row[0] for row in db.execute("SELECT keyword FROM dicom")})


if __name__ == "__main__":
    unittest.main()
