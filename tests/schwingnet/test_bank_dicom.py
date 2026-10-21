"""The DICOM path of tools/bank.py (#44): the pixel array windowed to 8 bits, the person and the
view from the header, members read inside a zip, the same bank whatever the number of workers,
and a placeholder person refused. These run where pydicom is installed (the train environment)."""

import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

pydicom = pytest.importorskip("pydicom")
numpy = pytest.importorskip("numpy")
pytest.importorskip("PIL")

from pydicom.dataset import FileDataset, FileMetaDataset  # noqa: E402
from pydicom.uid import ExplicitVRLittleEndian, generate_uid  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool  # so a worker process can find the functions it is handed
    spec.loader.exec_module(tool)
    return tool


def dicom(patient: str, study: str, view: str, seed: int, photometric: str = "MONOCHROME2") -> bytes:
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
    grid = (numpy.arange(24 * 32).reshape(24, 32) * (seed + 3)) % 4096
    data.PixelData = grid.astype(numpy.uint16).tobytes()
    out = io.BytesIO()
    data.save_as(out, enforce_file_format=True)
    return out.getvalue()


def recipe(tmp: Path, **changes) -> Path:
    shipped = json.loads((ROOT / "grid" / "banks" / "vindr_spinexr.json").read_text(encoding="utf-8"))
    shipped.update(raw=str(tmp / "raw"), bank=str(tmp / "bank"), **changes)
    path = tmp / "recipe.json"
    path.write_text(json.dumps(shipped), encoding="utf-8")
    return path


def write_set(raw: Path) -> None:
    (raw / "train_images").mkdir(parents=True)
    (raw / "test_images").mkdir(parents=True)
    (raw / "train_images" / "a1.dicom").write_bytes(dicom("", "1.2.3.1", "AP", 1))
    (raw / "train_images" / "a2.dicom").write_bytes(dicom("", "1.2.3.1", "LL", 2))
    (raw / "test_images" / "b1.dicom").write_bytes(dicom("anonymous", "1.2.3.2", "PA", 3, "MONOCHROME1"))


def run(tool, path: Path, *extra: str, capsys) -> dict:
    assert tool.main(["--recipe", str(path), *extra]) == 0
    return json.loads(capsys.readouterr().out)


def test_a_dicom_set_banks_with_person_view_and_device_from_the_header(tmp_path, capsys) -> None:
    tool = load("bank")
    write_set(tmp_path / "raw")
    path = recipe(tmp_path)
    plan = run(tool, path, capsys=capsys)
    assert plan["frames"] == 3 and plan["persons"] == 2 and plan["transfer_syntaxes"] == {"1.2.840.10008.1.2.1": 3}
    counts = run(tool, path, "--run", capsys=capsys)
    assert counts["written"] == 3 and counts["most_frames_per_person"] == 2
    meta = json.loads((tmp_path / "bank" / "meta" / "train_images_a2.json").read_text(encoding="utf-8"))
    assert meta["case"] == "1.2.3.1" and meta["view"]["lat_from_ap_deg"] == 90.0
    assert meta["device"]["make"] == "Maker" and meta["device"]["kvp"] == 80.0 and meta["px_mm"] == 0.15
    assert "PatientID" not in meta["dicom"]
    frame = (tmp_path / "bank" / "images" / "train" / "test_images_b1.png").read_bytes()
    from PIL import Image

    image = Image.open(io.BytesIO(frame))
    assert image.mode == "L" and image.size == (32, 24)


def test_monochrome1_is_inverted_and_flat_frames_are_refused(tmp_path) -> None:
    tool = load("bank")
    straight = tool.dicom_as_png(dicom("p", "1.2.5", "AP", 5))[0]
    inverted = tool.dicom_as_png(dicom("p", "1.2.5", "AP", 5, "MONOCHROME1"))[0]
    from PIL import Image

    a = numpy.asarray(Image.open(io.BytesIO(straight)), dtype=int)
    b = numpy.asarray(Image.open(io.BytesIO(inverted)), dtype=int)
    assert numpy.abs(a + b - 255).max() <= 1
    flat = dicom("p", "1.2.5", "AP", 0)
    data = pydicom.dcmread(io.BytesIO(flat))
    data.PixelData = numpy.zeros((24, 32), dtype=numpy.uint16).tobytes()
    out = io.BytesIO()
    data.save_as(out)
    with pytest.raises(tool.BankError, match="flat"):
        tool.dicom_as_png(out.getvalue())


def test_the_bank_is_the_same_bytes_with_four_workers(tmp_path, capsys) -> None:
    tool = load("bank")
    write_set(tmp_path / "raw")
    run(tool, recipe(tmp_path), "--run", capsys=capsys)
    one = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (tmp_path / "bank").rglob("*") if p.is_file()}
    other = tmp_path / "again"
    other.mkdir()
    write_set(other / "raw")
    run(tool, recipe(other), "--run", "--workers", "4", capsys=capsys)
    four = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (other / "bank").rglob("*") if p.is_file()}
    assert one == four and len(one) == 6


def test_a_placeholder_in_every_person_tag_is_refused(tmp_path, capsys) -> None:
    tool = load("bank")
    raw = tmp_path / "raw" / "train_images"
    raw.mkdir(parents=True)
    for index in range(4):
        (raw / f"c{index}.dicom").write_bytes(dicom("VINDR", "1.2.3.9", "AP", index))
    path = recipe(tmp_path, max_frames_per_person=3)
    assert tool.main(["--recipe", str(path)]) == 2
    assert "more than 3 frames" in capsys.readouterr().err


def test_lumos_members_are_read_inside_their_zips_by_the_shipped_recipe(tmp_path, capsys) -> None:
    tool = load("bank")
    shipped = json.loads((ROOT / "grid" / "banks" / "lumos.json").read_text(encoding="utf-8"))
    raw = tmp_path / "raw"
    raw.mkdir()
    with zipfile.ZipFile(raw / "lumos_x_001_280_dcm.zip", "w") as archive:
        archive.writestr("lumos_x/lumos_x_001/lumos_x_001_1.dcm", dicom("", "1.2.4.1", "AP", 1))
        archive.writestr("lumos_x/lumos_x_001/lumos_x_001_2.dcm", dicom("", "1.2.4.1", "OBL", 2))
        archive.writestr("lumos_x/lumos_x_002/lumos_x_002_1.dcm", dicom("", "1.2.4.2", "LL", 3))
    with zipfile.ZipFile(raw / "lumos_ct_001_070_dcm.zip", "w") as archive:
        archive.writestr("lumos_ct/lumos_ct_001/lumos_ct_001_1.dcm", dicom("", "1.2.4.3", "", 4))
    shipped.update(raw=str(raw), bank=str(tmp_path / "bank"))
    path = tmp_path / "lumos.json"
    path.write_text(json.dumps(shipped), encoding="utf-8")
    counts = run(tool, path, "--run", capsys=capsys)
    assert counts["frames"] == 3 and counts["persons"] == 2
    metas = sorted((tmp_path / "bank" / "meta").glob("*.json"))
    cases = [json.loads(p.read_text(encoding="utf-8"))["case"] for p in metas]
    assert cases == ["001", "001", "002"]
    views = [json.loads(p.read_text(encoding="utf-8"))["view"]["lat_from_ap_deg"] for p in metas]
    assert views == [0.0, None, 90.0]
