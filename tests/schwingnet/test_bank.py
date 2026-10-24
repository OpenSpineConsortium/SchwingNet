"""A bank tools/bank.py writes from a raw folder is one tools/ingest.py reads and plans a shard from."""

import importlib.util
import json
import os
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


def test_a_bank_made_again_from_the_same_raw_copy_reads_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bank_tool = load("bank")
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
    first = json.loads(capsys.readouterr().out)
    assert first["written"] == 3 and "unchanged" not in first
    stamp = json.loads((tmp_path / "bank" / "BANK.json").read_text(encoding="utf-8"))
    assert stamp["counts"]["frames"] == 3 and len(stamp["stamp"]["raw_sha256"]) == 64
    assert bank_tool.main(["--recipe", str(path), "--run"]) == 0
    again = json.loads(capsys.readouterr().out)
    assert again["unchanged"] is True and (again["written"], again["kept"]) == (0, 3)
    assert again["persons"] == first["persons"]
    # A raw file written again, even with the same bytes, makes a full run, which keeps the bank.
    touched = raw / "00000001_000.png"
    touched.write_bytes(touched.read_bytes())
    later = touched.stat().st_mtime_ns + 10**9
    os.utime(touched, ns=(later, later))
    assert bank_tool.main(["--recipe", str(path), "--run"]) == 0
    full = json.loads(capsys.readouterr().out)
    assert "unchanged" not in full and (full["written"], full["kept"]) == (0, 3)
    # A plan neither reads nor writes the stamp.
    assert bank_tool.main(["--recipe", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "plan"


def nih_recipe(tmp_path: Path, raw: Path) -> Path:
    """The NIH recipe pointed at a raw folder and a bank under the test's own folder."""
    recipe = json.loads(
        (ROOT / "grid" / "banks" / "nih_chestxray14.json").read_text(encoding="utf-8")
    )
    recipe["raw"], recipe["bank"] = str(raw), str(tmp_path / "bank")
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    return path


def bank_run(bank_tool, recipe: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    assert bank_tool.main(["--recipe", str(recipe), "--run"]) == 0
    return json.loads(capsys.readouterr().out)


def test_a_linked_folder_of_films_is_in_the_stamp_and_a_link_loop_is_walked_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bank_tool = load("bank")
    copy = tmp_path / "grid_copy" / "images"
    copy.mkdir(parents=True)
    for index, name in enumerate(["00000001_000", "00000002_000"]):
        (copy / f"{name}.png").write_bytes(png(40, 30, index))
    raw = tmp_path / "raw"
    (raw / "images_001").mkdir(parents=True)
    (raw / "images_001" / "images").symlink_to(copy, target_is_directory=True)
    (raw / "loop").symlink_to(raw, target_is_directory=True)
    (raw / "Data_Entry_2017.csv").symlink_to(tmp_path / "gone.csv")
    recipe = nih_recipe(tmp_path, raw)
    first = bank_run(bank_tool, recipe, capsys)
    assert first["written"] == 2
    listing = bank_tool.tree_listing(raw)
    assert any(line.startswith("images_001/images/00000001_000.png\t") for line in listing)
    assert any(line.startswith("Data_Entry_2017.csv\tmissing\t") for line in listing)
    assert not any(line.startswith("loop/images_001/") for line in listing)
    # A film added to the linked copy is seen, and banked.
    (copy / "00000003_000.png").write_bytes(png(40, 30, 7))
    grown = bank_run(bank_tool, recipe, capsys)
    assert "unchanged" not in grown and (grown["written"], grown["kept"]) == (1, 2)
    # The link pointed at another copy of the same files, times and all, changes the stamp too.
    other = tmp_path / "other_copy"
    other.mkdir()
    for film in sorted(copy.iterdir()):
        (other / film.name).write_bytes(film.read_bytes())
        os.utime(other / film.name, ns=(film.stat().st_atime_ns, film.stat().st_mtime_ns))
    before = bank_tool.tree_listing(raw)
    (raw / "images_001" / "images").unlink()
    (raw / "images_001" / "images").symlink_to(other, target_is_directory=True)
    assert bank_tool.tree_listing(raw) != before
    assert "unchanged" not in bank_run(bank_tool, recipe, capsys)


def test_a_thinned_or_edited_bank_is_made_again_and_a_refused_run_leaves_no_stamp(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bank_tool = load("bank")
    raw = tmp_path / "raw" / "images_001" / "images"
    raw.mkdir(parents=True)
    for index, name in enumerate(["00000001_000", "00000002_000", "00000003_000"]):
        (raw / f"{name}.png").write_bytes(png(40, 30, index))
    recipe = nih_recipe(tmp_path, tmp_path / "raw")
    bank, stamp = tmp_path / "bank", tmp_path / "bank" / "BANK.json"
    assert bank_run(bank_tool, recipe, capsys)["written"] == 3
    assert len(json.loads(stamp.read_text(encoding="utf-8"))["bank_sha256"]) == 64
    # Frames removed from the bank by hand are written back from raw, not reported as kept.
    films = sorted((bank / "images" / "train").iterdir())
    films[0].unlink()
    (bank / "meta" / (films[0].stem + ".json")).unlink()
    restored = bank_run(bank_tool, recipe, capsys)
    assert "unchanged" not in restored and (restored["written"], restored["kept"]) == (1, 2)
    assert bank_run(bank_tool, recipe, capsys)["unchanged"] is True
    # A meta edited by hand is no longer what the stamp recorded: the run is refused, as before
    # #260, and the stamp goes with it, so no later run or ingest trusts the edited bank.
    meta = bank / "meta" / (films[1].stem + ".json")
    meta.chmod(0o644)
    meta.write_text(meta.read_text(encoding="utf-8").replace("{", '{"edited": 1, ', 1), encoding="utf-8")
    assert bank_tool.main(["--recipe", str(recipe), "--run"]) == 2
    assert "other bytes" in capsys.readouterr().err
    assert not stamp.exists()
