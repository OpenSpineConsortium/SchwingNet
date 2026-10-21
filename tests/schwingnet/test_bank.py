"""A bank tools/bank.py writes from a raw folder is one tools/ingest.py reads and plans a shard from."""

import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_tool", ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def png(width: int, height: int, seed: int) -> bytes:
    raw = bytes(((x * 7 + y * 3 + seed) % 256) for y in range(height) for x in range(width + 1))

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


def test_a_bank_from_a_raw_folder_plans_as_a_train_shard(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bank_tool, ingest = load("bank"), load("ingest")
    raw = tmp_path / "raw" / "images_001" / "images"
    raw.mkdir(parents=True)
    for index, name in enumerate(["00000001_000", "00000001_001", "00000002_000"]):
        (raw / f"{name}.png").write_bytes(png(40, 30, index))
    recipe = json.loads(
        (ROOT / "grid" / "banks" / "nih_chestxray14.json").read_text(encoding="utf-8")
    )
    recipe["raw"], recipe["bank"] = str(tmp_path / "raw"), str(tmp_path / "bank")
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    assert bank_tool.main(["--recipe", str(path), "--run"]) == 0
    assert json.loads(capsys.readouterr().out)["written"] == 3
    argv = [
        "plan",
        "--bank",
        str(tmp_path / "bank"),
        "--source",
        "nih_chestxray14",
        "--kind",
        "train",
        "--split",
        "train",
        "--date",
        "2026-10-21",
        "--code-commit",
        "0123abc",
        "--grid-root",
        str(tmp_path / "grid" / "nih_chestxray14"),
    ]
    assert ingest.main(argv) == 0
    planned = json.loads(capsys.readouterr().out)
    assert (planned["frames_kept"], planned["persons"], planned["labels"]) == (3, 2, 0)
    assert planned["shard"].startswith("nih_chestxray14/2026-10-21-")
    assert not (tmp_path / "grid").exists()
