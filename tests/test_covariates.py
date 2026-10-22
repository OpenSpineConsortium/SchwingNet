"""tools/covariates.py: DICOM headers counted, ages reduced to decades, tables named, no rows kept.

DICOM needs pydicom, so that part runs in the train-cpu environment
(`pixi run -e train-cpu python -m unittest tests.test_covariates`) and skips under plain python3;
the tables part runs anywhere."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HAS_PYDICOM = importlib.util.find_spec("pydicom") is not None


def load():
    spec = importlib.util.spec_from_file_location("covariates_under_test", ROOT / "tools" / "covariates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TablesTest(unittest.TestCase):
    def test_columns_and_counts_without_rows(self):
        tool = load()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "Data_Entry.csv").write_text("Image Index,Patient Age,Patient Gender\na.png,45,M\nb.png,61,F\n", encoding="utf-8")
        (tmp / "labels.json").write_text(json.dumps([{"image": "a", "cobb": 12.0}]), encoding="utf-8")
        found = tool.side_files(tmp)
        self.assertEqual(found["Data_Entry.csv"], {"columns": ["Image Index", "Patient Age", "Patient Gender"], "rows": 2})
        self.assertEqual(found["labels.json"], {"keys": ["cobb", "image"], "items": 1})
        self.assertNotIn("45", json.dumps(found))

    def test_ages_become_decades(self):
        tool = load()
        self.assertEqual(tool.age_decade("045Y"), "40s")
        self.assertEqual(tool.age_decade("018M"), "0s")
        self.assertIsNone(tool.age_decade("unknown"))


@unittest.skipUnless(HAS_PYDICOM, "needs pydicom (the train environment)")
class DicomTest(unittest.TestCase):
    def test_headers_are_counted_and_reduced(self):
        from pydicom.dataset import Dataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, generate_uid

        tool = load()
        tmp = Path(tempfile.mkdtemp())
        for n, (age, sex) in enumerate((("045Y", "M"), ("047Y", "F"), ("071Y", "F"))):
            meta = FileMetaDataset()
            meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1.1"
            meta.MediaStorageSOPInstanceUID = generate_uid()
            meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds = Dataset()
            ds.file_meta = meta
            ds.PatientAge, ds.PatientSex, ds.PatientID = age, sex, f"secret{n}"
            ds.ViewPosition, ds.KVP = "AP", "81"
            ds.save_as(str(tmp / f"{n}.dcm"), enforce_file_format=True)
        census = tool.dicom_census(tmp, 10, 1)
        self.assertEqual(census["headers_read"], 3)
        self.assertEqual(census["values"]["PatientAge"], {"40s": 2, "70s": 1})
        self.assertEqual(census["values"]["PatientSex"], {"F": 2, "M": 1})
        self.assertEqual(census["values"]["KVP"], {"80 kV": 3})
        self.assertNotIn("secret", json.dumps(census))


if __name__ == "__main__":
    unittest.main()
