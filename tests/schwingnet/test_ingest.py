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
