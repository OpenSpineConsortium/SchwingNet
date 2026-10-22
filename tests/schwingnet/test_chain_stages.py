"""The three stage scripts of the X-ray chain run off the grid, with bash, on a data root of a
test's own (issue #40): stage 2 banks and ingests a synthetic raw copy, a raw copy that grew
cuts a successor shard and not a sibling, and stage 3 builds the catalog from each source's
chain at its head alone and split-checks it. This is the run the container made on 2026-10-21,
kept as a test; it needs pydantic, so it is a gate-lane test and not one of tests/."""

import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRID = ROOT / "grid"


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


def write_films(raw: Path, patients: range) -> None:
    folder = raw / "images_001" / "images"
    folder.mkdir(parents=True, exist_ok=True)
    for patient in patients:
        for follow in range(2):
            (folder / f"{patient:08d}_{follow:03d}.png").write_bytes(png(48, 32, patient * 2 + follow))


def stage(name: str, cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    done = subprocess.run(
        ["bash", str(GRID / name)],
        cwd=cwd,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=600,
    )
    return done.returncode, done.stdout + done.stderr


def test_the_stages_run_off_the_grid_and_a_grown_raw_copy_is_counted_once(tmp_path: Path) -> None:
    data_root, banks, logs = tmp_path / "data", tmp_path / "banks", tmp_path / "logs"
    banks.mkdir()
    logs.mkdir()
    (banks / "nih_chestxray14.json").write_bytes((GRID / "banks" / "nih_chestxray14.json").read_bytes())
    write_films(data_root / "nih_chestxray14" / "raw", range(1, 9))
    env = {
        "SCHWINGNET": str(ROOT),
        "PYDRV": sys.executable,
        "DATA_ROOT": str(data_root),
        "BANKS": str(banks),
        "STORE": str(data_root / "_catalog"),
    }
    code, out = stage("02-bank-ingest.sbatch", logs, env)
    assert code == 0, out
    assert "written 16 frames, 8 persons, 0 labels" in out
    assert (data_root / "_tmp").is_dir()
    shards = sorted((data_root / "nih_chestxray14" / "shards").iterdir())
    assert len(shards) == 1
    code, out = stage("03-catalog.sbatch", logs, env)
    assert code == 0, out
    assert '"frames": 16' in out and "split-check of version 1: disjoint" in out

    # The raw copy grows by two patients (a zip unpacked after the first ingest, a second part of
    # a download): the second ingest supersedes the first shard and the catalog counts 20 frames,
    # not 36, since it reads the chain at its head.
    write_films(data_root / "nih_chestxray14" / "raw", range(9, 11))
    code, out = stage("02-bank-ingest.sbatch", logs, env)
    assert code == 0, out
    assert "written 20 frames, 10 persons, 0 labels" in out
    shards = sorted((data_root / "nih_chestxray14" / "shards").iterdir())
    assert len(shards) == 2
    manifests = [json.loads((s / "MANIFEST.json").read_text(encoding="utf-8")) for s in shards]
    successor = next(m for m in manifests if len(m["items"]) == 20)
    first = next(m for m in manifests if len(m["items"]) == 16)
    assert successor["supersedes"] == first["name"]
    code, out = stage("03-catalog.sbatch", logs, env)
    assert code == 0, out
    assert "manifests read: 2" in out
    assert '"frames": 20' in out and '"version": 2' in out

    # The same bank again: the shard is already there, nothing supersedes anything, and the
    # catalog's bytes equal the latest version, which is reported as not new.
    code, out = stage("02-bank-ingest.sbatch", logs, env)
    assert code == 0, out
    assert "already there 20 frames" in out
    assert len(list((data_root / "nih_chestxray14" / "shards").iterdir())) == 2
    code, out = stage("03-catalog.sbatch", logs, env)
    assert code == 0, out
    assert '"new": false' in out
    report = (logs / "logs" / "03-catalog-STAGE-REPORT.md").read_text(encoding="utf-8")
    assert "split-check of version 2: disjoint" in report
    # each passed check left the marker the version 1 run's chooser reads (grid/v1-version.sh)
    assert sorted(p.name[:14] for p in (data_root / "_catalog" / "checked").iterdir()) == ["catalog-000001", "catalog-000002"]
