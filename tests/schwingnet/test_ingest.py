"""tools/ingest.py turns a bank of frames into one content-addressed shard the catalog builds from."""

import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest

from schwingnet.catalog import ShardManifest, frame_path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def png(width: int, height: int, seed: int) -> bytes:
    raw = bytes(((x * 31 + y * 17 + seed) % 256) for y in range(height) for x in range(width + 1))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def frame(
    bank: Path, split: str, stem: str, case: str, seed: int, boxes: list[dict[str, object]]
) -> None:
    (bank / "images" / split).mkdir(parents=True, exist_ok=True)
    (bank / "meta").mkdir(exist_ok=True)
    (bank / "images" / split / f"{stem}.png").write_bytes(png(40, 20, seed))
    meta = {
        "case": case,
        "split": split,
        "px_mm": 0.3,
        "device": {
            "make": "Ziehm",
            "model": "Vision",
            "detector": "flat panel",
            "kvp": 73.0,
            "mas": 2.0,
        },
        "view": {"gantry_deg": 12.0, "lat_from_ap_deg": 90.0},
        "boxes": boxes,
    }
    (bank / "meta" / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")


def box(
    level: str | None, x0: float = 4, y0: float = 2, x1: float = 30, y1: float = 18
) -> dict[str, object]:
    return {"cls": 0, "level": level, "box": [x0, y0, x1, y1], "visible_frac": 0.9, "px": 100}


def bank_of(tmp_path: Path) -> Path:
    bank = tmp_path / "bank"
    frame(bank, "train", "case7_f1", "case7", 1, [box("L4"), box(None)])
    frame(bank, "train", "case7_f2", "case7", 2, [box("L5"), box("S1", 0, 0, 50, 30)])
    frame(bank, "train", "case7_f3", "case7", 1, [box("L4")])
    frame(bank, "train", "case8_f1", "case8", 3, [box("L6", 10, 10, 10, 12)])
    frame(bank, "val", "case9_f1", "case9", 4, [box("L3")])
    frame(bank, "test", "case42_f1", "case42", 5, [box("L6")])
    return bank


def argv(bank: Path, root: Path, kind: str, split: str, command: str = "run") -> list[str]:
    return [
        command,
        "--bank",
        str(bank),
        "--source",
        "carmlspine",
        "--kind",
        kind,
        "--split",
        split,
        "--date",
        "2026-10-21",
        "--code-commit",
        "0123abc",
        "--grid-root",
        str(root),
    ]


def test_a_bank_becomes_one_shard_at_its_content_addresses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest, catalog = load("ingest"), load("catalog")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    assert ingest.main(argv(bank, root, "train", "train", "plan")) == 0
    planned = json.loads(capsys.readouterr().out)
    assert not root.exists() and "outcome" not in planned
    assert ingest.main(argv(bank, root, "train", "train")) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["outcome"] == "written" and report["verified"] == 3
    assert report["frames_read"] == 4 and report["frames_kept"] == 3 and report["persons"] == 2
    assert report["duplicates"] == [
        {
            "stem": "case7_f3",
            "same_bytes_as": "case7_f1.png",
            "sha256": report["duplicates"][0]["sha256"],
        }
    ]
    assert report["boxes_without_level"] == 2 and report["labels"] == 3
    folder = Path(report["folder"])
    assert folder == root / "shards" / report["shard"].split("/")[1]
    manifest = ShardManifest.model_validate(
        json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    )
    assert [i.person for i in manifest.items] == [
        "carmlspine:case7",
        "carmlspine:case7",
        "carmlspine:case8",
    ]
    for item in manifest.items:
        path = folder / item.path
        assert item.path == frame_path(item.sha256, "png") and path.stat().st_mode & 0o777 == 0o444
        assert (item.lat_from_ap_deg, item.gantry_deg) == (90.0, 12.0)
        assert (item.exposure.kvp, item.exposure.mas, item.exposure.px_mm) == (73.0, 2.0, 0.3)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item.sha256
    levels = sorted(label.level for item in manifest.items for label in item.labels)
    assert levels == ["L4", "L5", "sacrum"] and manifest.items[1].labels[1].box == (
        0.0,
        0.0,
        1.0,
        1.0,
    )
    assert (folder / "MANIFEST.json").stat().st_mode & 0o777 == 0o444
    assert [p.name for p in root.joinpath("shards").iterdir() if p.name.startswith(".")] == []
    assert ingest.main(argv(bank, root, "train", "train")) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "already there"
    assert ingest.main(argv(bank, root, "train", "val")) == 0
    assert ingest.main(argv(bank, root, "test", "test")) == 0
    capsys.readouterr()
    manifests = sorted(root.glob("shards/*/MANIFEST.json"))
    assert len(manifests) == 3
    store = tmp_path / "store"
    record, new = catalog.build(store, manifests, catalog.load_inputs(), "0123abc")
    assert new and record.frames == 5 and record.frames_by_source_and_part["carmlspine|test"] == 1
    check = catalog.split_check(catalog.open_catalog(store), catalog.load_inputs())
    assert check["disjoint"] and check["per_source"]["carmlspine"]["identity_level"] == "patient"


def test_what_the_ingest_refuses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    assert ingest.main(argv(bank, root, "train", "test")) == 1
    assert "would hold the frozen test persons ['carmlspine:case42']" in capsys.readouterr().err
    assert ingest.main(argv(bank, root, "test", "train")) == 1
    assert "not frozen" in capsys.readouterr().err
    assert ingest.main(argv(bank, root, "train", "nowhere")) == 1
    assert "no frame under images/nowhere" in capsys.readouterr().err
    assert ingest.main(argv(bank, root, "train", "train")[:-1] + [str(tmp_path / "other")]) == 1
    assert "is not the folder named carmlspine" in capsys.readouterr().err
    (bank / "meta" / "case9_f1.json").unlink()
    assert ingest.main(argv(bank, root, "train", "val")) == 1
    assert "no meta file" in capsys.readouterr().err
    (bank / "images" / "train" / "case8_f1.png").write_bytes(b"not a png")
    assert ingest.main(argv(bank, root, "train", "train")) == 1
    assert "not a PNG" in capsys.readouterr().err
    assert not root.exists()
    assert ingest.main(argv(bank, root, "train", "train")[:-2] + ["--source", "nowhere"]) == 1
    assert "nowhere has no registry entry" in capsys.readouterr().err


def test_a_shard_already_there_with_another_manifest_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    assert ingest.main(argv(bank, root, "train", "val")) == 0
    folder = Path(json.loads(capsys.readouterr().out)["folder"])
    manifest = folder / "MANIFEST.json"
    manifest.chmod(0o644)
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("0123abc", "0123abd"), encoding="utf-8"
    )
    assert ingest.main(argv(bank, root, "train", "val")) == 1
    assert "its manifest differs" in capsys.readouterr().err
    with pytest.raises(ingest.IngestError, match="not a PNG"):
        ingest.png_size(b"\x89PNG\r\n\x1a\n" + b"\0" * 8 + b"IHDR" + struct.pack(">II", 0, 5))


def test_the_same_bytes_under_two_persons_are_refused_and_the_plan_names_frozen_persons_not_seen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    assert ingest.main(argv(bank, root, "test", "test", "plan")) == 0
    planned = json.loads(capsys.readouterr().out)
    assert planned["frozen_persons_not_seen"] == [
        "carmlspine:case121",
        "carmlspine:case134",
        "carmlspine:case136",
        "carmlspine:case39",
    ]
    frame(bank, "train", "case7_f9", "case42", 1, [box("L4")])
    assert ingest.main(argv(bank, root, "train", "train")) == 1
    assert (
        "same bytes as case7_f1.png, under another person (carmlspine:case42"
        in capsys.readouterr().err
    )
    assert not root.exists()


def test_a_second_ingest_that_loses_the_rename_keeps_the_first_shard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    real_rename = ingest.os.rename

    def rename_after_a_sibling_landed(src: str, dst: str) -> None:
        monkeypatch.setattr(ingest.os, "rename", real_rename)
        assert ingest.main(argv(bank, root, "train", "val")) == 0
        capsys.readouterr()
        real_rename(src, dst)

    monkeypatch.setattr(ingest.os, "rename", rename_after_a_sibling_landed)
    assert ingest.main(argv(bank, root, "train", "val")) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "already there"
    assert [p.name for p in (root / "shards").iterdir() if p.name.startswith(".")] == []
    # Another run's staging folder, whatever it is called, is never removed.
    stale = root / "shards" / f".ingest-2026-10-21-000000000000-{ingest.os.getpid()}"
    stale.mkdir()
    (stale / "half").write_text("still being written", encoding="utf-8")
    assert ingest.main(argv(bank, root, "train", "train")) == 0
    assert (stale / "half").is_file()


def test_the_command_line_is_checked_before_the_bank_is_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    base = argv(bank, root, "train", "train", "plan")
    for flag, value, message in [
        ("--date", "21-10-2026", "the date '21-10-2026' is not spelled"),
        ("--code-commit", "main", "the commit 'main' is not spelled"),
        ("--modality", "bogus", "'bogus' is none of xa, rf"),
        ("--device-class", "laptop", "'laptop' is none of mobile_c_arm"),
    ]:
        words = list(base)
        if flag in words:
            words[words.index(flag) + 1] = value
        else:
            words += [flag, value]
        assert ingest.main(words) == 1
        assert message in capsys.readouterr().err
    # A hidden file or a file of another kind beside the frames is not a frame.
    (bank / "images" / "train" / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    (bank / "images" / "train" / "notes.txt").write_text("not a frame", encoding="utf-8")
    assert ingest.main(base) == 0
    assert json.loads(capsys.readouterr().out)["frames_read"] == 4


def test_one_bank_whose_split_mixes_frozen_persons_becomes_a_test_and_a_train_shard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    frame(bank, "train", "case121_f1", "case121", 6, [box("L5")])
    assert ingest.main(argv(bank, root, "train", "")) == 1
    assert "would hold the frozen test persons" in capsys.readouterr().err
    assert ingest.main(argv(bank, root, "train", "") + ["--persons", "unfrozen"]) == 0
    train = json.loads(capsys.readouterr().out)
    assert train["kind"] == "train" and train["persons"] == 3 and train["persons_left_out"] == 2
    assert train["frozen_persons_not_seen"] == [
        "carmlspine:case134",
        "carmlspine:case136",
        "carmlspine:case39",
    ]
    assert ingest.main(argv(bank, root, "test", "") + ["--persons", "frozen"]) == 0
    test = json.loads(capsys.readouterr().out)
    assert test["kind"] == "test" and test["persons"] == 2 and test["frames_kept"] == 2
    assert len(list(root.glob("shards/*/MANIFEST.json"))) == 2


def test_the_persons_filter_never_hides_the_same_bytes_under_two_persons(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = bank_of(tmp_path), tmp_path / "grid" / "carmlspine"
    frame(bank, "train", "case121_f1", "case121", 1, [box("L5")])
    assert ingest.main(argv(bank, root, "train", "") + ["--persons", "unfrozen"]) == 1
    assert "under another person" in capsys.readouterr().err
    assert ingest.main(argv(bank, root, "test", "test") + ["--persons", "unfrozen"]) == 1
    assert "leaves no frame of the bank" in capsys.readouterr().err
    assert not root.exists()


def carm_frame(
    bank: Path,
    split: str,
    case: str,
    view: str,
    angle: float,
    seed: int,
    device_kvp: float | None = None,
) -> None:
    """A frame as spinesurg-ct-nnunet's tools/carmlspine_labels.py writes C-ArmLSpine's bank:
    `view` is the frame's tag, the positioner angle and kvp sit beside it, the device carries
    make and model alone, and each box carries both labellers' names."""
    (bank / "images" / split).mkdir(parents=True, exist_ok=True)
    (bank / "meta").mkdir(exist_ok=True)
    stem = f"{case}_{view}"
    (bank / "images" / split / f"{stem}.png").write_bytes(png(40, 20, seed))
    boxes = [
        {
            "cls": 0,
            "box": [4.0, 2.0, 30.0, 18.0],
            "level_ts": "L4",
            "level_spineps": "L4",
            "level_agree": True,
            "level": "L4",
            "visible_frac": 0.97,
            "complete": True,
        },
        {
            "cls": 0,
            "box": [4.0, 2.0, 30.0, 18.0],
            "level_ts": "L5",
            "level_spineps": "L6",
            "level_agree": False,
            "level": None,
            "visible_frac": 0.9,
            "complete": True,
        },
    ]
    meta = {
        "case": case,
        "view": view,
        "view_class": view.rstrip("0123456789"),
        "repeat": 1,
        "split": split,
        "stem": stem,
        "device": {"make": "Yiying (FIRST)", "model": "Surgio-B51"}
        | ({} if device_kvp is None else {"kvp": device_kvp}),
        "kvp": 72.0,
        "angle": angle,
        "px_mm": 0.24,
        "boxes": boxes,
    }
    (bank / "meta" / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")


def test_the_carmlspine_builders_meta_is_read_with_its_view_tag_and_angle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = tmp_path / "bank", tmp_path / "grid" / "carmlspine"
    carm_frame(bank, "train", "case7", "AP", -2.0, 1)
    carm_frame(bank, "train", "case8", "LAT", 89.0, 2, device_kvp=80.0)
    carm_frame(bank, "val", "case39", "LAT2", 90.5, 3)
    assert ingest.main(argv(bank, root, "train", "") + ["--persons", "unfrozen"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (
        report["frames_kept"] == 2 and report["labels"] == 2 and report["boxes_without_level"] == 2
    )
    manifest = ShardManifest.model_validate(
        json.loads((Path(report["folder"]) / "MANIFEST.json").read_text(encoding="utf-8"))
    )
    # The device's own kVp wins over the one beside it; the spot bank records no gantry angle.
    assert sorted(
        (i.person, i.lat_from_ap_deg, i.gantry_deg, i.exposure.kvp, i.device.model)
        for i in manifest.items
    ) == [
        ("carmlspine:case7", -2.0, None, 72.0, "Surgio-B51"),
        ("carmlspine:case8", 89.0, None, 80.0, "Surgio-B51"),
    ]
    assert report["persons_left_out"] == 1  # case39, a frozen test person (the second demo sweep)
    assert ingest.main(argv(bank, root, "test", "") + ["--persons", "frozen"]) == 0
    test = json.loads(capsys.readouterr().out)
    assert test["kind"] == "test" and test["frames_kept"] == 1 and test["persons"] == 1


def test_a_meta_of_another_shape_is_one_line_naming_the_frame(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = tmp_path / "bank", tmp_path / "grid" / "carmlspine"
    carm_frame(bank, "train", "case7", "AP", 0.0, 1)
    meta_path = bank / "meta" / "case7_AP.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    image = bank / "images" / "train" / "case7_AP.png"
    for key, value, said in [
        ("device", "Surgio-B51", "meta's device is a str, not an object"),
        ("boxes", {"L4": [4, 2, 30, 18]}, "meta's boxes is not a list of objects"),
        ("boxes", {}, "meta's boxes is not a list of objects"),
        ("boxes", ["L4"], "meta's boxes is not a list of objects"),
        ("view", ["AP"], "meta's view is a list, not an object"),
        ("angle", "89.0", "meta's angle is a str, not a number"),
        ("angle", True, "meta's angle is a bool, not a number"),
    ]:
        meta_path.write_text(json.dumps({**meta, key: value}), encoding="utf-8")
        assert ingest.main(argv(bank, root, "train", "")) == 1
        assert capsys.readouterr().err == f"ingest: {image}: {said}\n"


def sweep_frame(bank: Path, case: str, index: int, angle: float, seed: int) -> None:
    """A projection as spinesurg-ct-nnunet's tools/case134_sweep.py writes the C-ArmLSpine sweep
    bank: no `view` at all, the header's positioner angle as `angle` beside the registered pose's
    own angles, kvp beside the device, and `mode` naming the frames a spin."""
    (bank / "images" / "test").mkdir(parents=True, exist_ok=True)
    (bank / "meta").mkdir(exist_ok=True)
    stem = f"{case}_sw{index:03d}"
    (bank / "images" / "test" / f"{stem}.png").write_bytes(png(40, 20, seed))
    meta = {
        "dataset": "carmlspine_sweep",
        "case": case,
        "frame": f"sw{index:03d}",
        "stem": stem,
        "split": "test",
        "mode": "cbct_spin",
        "device": {"make": "Yiying (FIRST)", "model": "Surgio-B51"},
        "angle": angle,
        "tilt": 0.0,
        "kvp": 75.0,
        "lat_signed_deg": round(-angle + 1.5, 2),
        "size": 40,
        "boxes": [{"cls": 0, "box": [4.0, 2.0, 30.0, 18.0], "kept": True, "level": None}],
        "n_kept": 1,
    }
    (bank / "meta" / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")


def test_the_case134_sweep_bank_is_read_at_its_spin_angles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = tmp_path / "bank", tmp_path / "grid" / "carmlspine_sweeps"
    sweep_frame(bank, "case134", 0, 122.0, 1)
    sweep_frame(bank, "case134", 1, -51.5, 2)
    command = argv(bank, root, "test", "test")
    command[command.index("carmlspine")] = "carmlspine_sweeps"
    # The registry keys a sweep's person as the spot frames' (carmlspine:<case>).
    assert ingest.main(command + ["--person-prefix", "carmlspine"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["kind"] == "test" and report["frames_kept"] == 2
    manifest = ShardManifest.model_validate(
        json.loads((Path(report["folder"]) / "MANIFEST.json").read_text(encoding="utf-8"))
    )
    # The header's angle is both the angle from AP and, for a spin, the gantry angle.
    assert sorted((i.lat_from_ap_deg, i.gantry_deg, i.exposure.kvp) for i in manifest.items) == [
        (-51.5, -51.5, 75.0),
        (122.0, 122.0, 75.0),
    ]


def paeth(left: int, up: int, up_left: int) -> int:
    estimate = left + up - up_left
    near = (abs(estimate - left), abs(estimate - up), abs(estimate - up_left))
    if near[0] <= near[1] and near[0] <= near[2]:
        return left
    return up if near[1] <= near[2] else up_left


def grey_png(rows: list[list[int]], colour: int = 0) -> bytes:
    """An 8-bit greyscale PNG whose rows use each of the five filters in turn, so the ingest's
    own decoder is held to all of them; colour type 2 writes the same bytes under an RGB header."""
    raw = bytearray()
    previous = [0] * len(rows[0])
    for y, row in enumerate(rows):
        kind = y % 5
        raw.append(kind)
        for x, value in enumerate(row):
            left, up, up_left = (row[x - 1] if x else 0), previous[x], (previous[x - 1] if x else 0)
            guess = (0, left, up, (left + up) >> 1, paeth(left, up, up_left))[kind]
            raw.append((value - guess) & 255)
        previous = row

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, colour, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw)))
        + chunk(b"IEND", b"")
    )


def png_chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def map_rows(width: int, height: int, code: int) -> list[list[int]]:
    rows = [[0] * width for _ in range(height)]
    for y in range(2, height - 2):
        for x in range(4, 30):
            rows[y][x] = code
    return rows


def with_map(bank: Path, stem: str, data: bytes, projector: str = "registered") -> None:
    (bank / "maps").mkdir(exist_ok=True)
    (bank / "maps" / f"{stem}.png").write_bytes(data)
    meta_path = bank / "meta" / f"{stem}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"level_map": f"maps/{stem}.png", "level_map_from": projector})
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def test_a_frames_level_map_rides_in_the_shard_and_a_wrong_one_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank, root = tmp_path / "bank", tmp_path / "grid" / "carmlspine"
    frame(bank, "train", "case7_f1", "case7", 1, [box("L4")])
    frame(bank, "train", "case7_f2", "case7", 2, [box("L5")])
    good = grey_png(map_rows(40, 20, 23))
    decoded = [list(row) for row in ingest.png_grey_rows(good)]
    assert decoded == map_rows(40, 20, 23), "every filter decodes"
    with_map(bank, "case7_f1", good)
    assert ingest.main(argv(bank, root, "train", "train")) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["level_maps"] == 1 and report["verified"] == 2 and report["frames_kept"] == 2
    folder = Path(report["folder"])
    written = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest = ShardManifest.model_validate(written)
    assert manifest.schema_version == 2 and sum("level_map" in i for i in written["items"]) == 1
    (carried,) = [i for i in manifest.items if i.level_map]
    assert carried.level_map is not None
    assert (carried.level_map.projector, carried.level_map.labeller) == ("registered", "projected")
    copied = folder / carried.level_map.path
    assert copied.stat().st_mode & 0o777 == 0o444
    assert hashlib.sha256(copied.read_bytes()).hexdigest() == carried.level_map.sha256
    assert carried.level_map.sha256 == hashlib.sha256(good).hexdigest()
    assert carried.level_map.path == frame_path(carried.level_map.sha256, "png")
    assert ingest.main(argv(bank, root, "train", "train")) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "already there"
    # A bank without maps writes the manifest the tool wrote before maps existed.
    plain = tmp_path / "plain"
    frame(plain, "train", "case8_f1", "case8", 3, [box("L4")])
    assert ingest.main(argv(plain, tmp_path / "grid2" / "carmlspine", "train", "train")) == 0
    first = json.loads(
        Path(json.loads(capsys.readouterr().out)["folder"], "MANIFEST.json").read_text(
            encoding="utf-8"
        )
    )
    assert first["schema_version"] == 1 and all("level_map" not in i for i in first["items"])
    # What is refused, each by name, before anything is written.
    wrong = [
        (grey_png(map_rows(40, 21, 23)), "registered", "the level map is 40x21, the frame 40x20"),
        (grey_png(map_rows(40, 20, 28)), "render", "holds the value 28; a level's code is 1 to 27"),
        (
            grey_png(map_rows(40, 20, 23), colour=2),
            "render",
            "8-bit greyscale PNG without interlace",
        ),
        (b"not a png", "render", "not a PNG"),
        (good[:26], "render", "not a PNG"),
        (good[:29] + bytes([good[29] ^ 1]) + good[30:], "render", "IHDR chunk fails its checksum"),
        (good[:-13], "render", "IDAT chunk is cut short"),
        (
            good[:8] + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 40, 20, 8, 0, 0, 1, 0)) + good[33:],
            "render",
            "filter method 0, not",
        ),
        (good[:33] + png_chunk(b"IEND", b"") + good[33:-12], "render", "does not decompress"),
        (good, "guessed", "not one of render, registered"),
    ]
    for data, projector, words in wrong:
        with_map(bank, "case7_f1", data, projector)
        assert ingest.main(argv(bank, tmp_path / "grid3" / "carmlspine", "train", "train")) == 1
        assert words in capsys.readouterr().err
    meta_path = bank / "meta" / "case7_f1.json"
    meta = dict(json.loads(meta_path.read_text(encoding="utf-8")), level_map_from="render")
    for named in ("../maps/case7_f1.png", "/maps/case7_f1.png", "", 3):
        meta_path.write_text(json.dumps(dict(meta, level_map=named)), encoding="utf-8")
        assert ingest.main(argv(bank, tmp_path / "grid3" / "carmlspine", "train", "train")) == 1
        assert "not a path inside the bank" in capsys.readouterr().err
    meta_path.write_text(json.dumps(dict(meta, level_map="maps/elsewhere.png")), encoding="utf-8")
    assert ingest.main(argv(bank, tmp_path / "grid3" / "carmlspine", "train", "train")) == 1
    assert "the level map elsewhere.png" in capsys.readouterr().err
    assert not (tmp_path / "grid3").exists()


def test_a_duplicate_frames_level_map_is_named_in_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest = load("ingest")
    bank = tmp_path / "bank"
    frame(bank, "train", "case7_f1", "case7", 1, [box("L4")])
    frame(bank, "train", "case7_f2", "case7", 1, [box("L4")])
    good = grey_png(map_rows(40, 20, 23))
    with_map(bank, "case7_f2", good)
    assert ingest.main(argv(bank, tmp_path / "grid" / "carmlspine", "train", "train")) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["frames_kept"], report["level_maps"]) == (1, 0)
    (duplicate,) = report["duplicates"]
    assert duplicate["stem"] == "case7_f2" and duplicate["same_bytes_as"] == "case7_f1.png"
    assert duplicate["level_map_dropped"] == hashlib.sha256(good).hexdigest()
    # The same map on both stems loses nothing, so the report says nothing.
    with_map(bank, "case7_f1", good)
    assert ingest.main(argv(bank, tmp_path / "grid2" / "carmlspine", "train", "train")) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["level_maps"] == 1 and "level_map_dropped" not in report["duplicates"][0]
