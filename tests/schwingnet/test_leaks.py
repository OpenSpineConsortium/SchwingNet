"""The leak checks (issue #9): the rules of schwingnet.leaks, the join of tools/leaks.py over
fingerprint files written for real shards, and the dry run of grid/run-leaks.sh.

The fingerprint step decodes frames with numpy and Pillow, which the gate's environment does not
hold, so here the reductions a fingerprint would carry are drawn in pure Python and written in the
fingerprint file's own format; tests/test_leaks_pipeline.py runs the decoding end to end where the
train-cpu environment is.
"""

import base64
import hashlib
import math
import importlib.util
import json
import os
import random
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from schwingnet import leaks

ROOT = Path(__file__).resolve().parents[2]
SIDE = leaks.NCC_SIDE
PINNED_PHASH = "8d1cc53631763bc3"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{name}_leaks_test", ROOT / "tools" / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


TOOL = load("leaks")


def pattern(seed: int) -> bytes:
    """A 64 x 64 grey reduction of a few bright discs on a dark ground, unlike another seed's."""
    rnd = random.Random(seed)
    discs = [
        (rnd.randrange(SIDE), rnd.randrange(SIDE), rnd.randrange(5, 18), rnd.randrange(50, 160))
        for _ in range(6)
    ]
    return bytes(
        min(255, 20 + sum(v for cx, cy, r, v in discs if (x - cx) ** 2 + (y - cy) ** 2 <= r * r))
        for y in range(SIDE)
        for x in range(SIDE)
    )


def nudged(image: bytes, seed: int) -> bytes:
    """A re-exposed copy: brighter by twelve, with a little noise, clipped to 8 bits."""
    rnd = random.Random(seed)
    return bytes(max(0, min(255, v + 12 + rnd.randint(-2, 2))) for v in image)


def pooled(image: bytes) -> bytes:
    """The 32 x 32 reduction a perceptual hash is taken over: the mean of each 2 x 2 block."""
    half = SIDE // 2
    return bytes(
        sum(image[(2 * y + dy) * SIDE + 2 * x + dx] for dy in (0, 1) for dx in (0, 1)) // 4
        for y in range(half)
        for x in range(half)
    )


def print_of(frame: str, person: str, image: bytes, part: str = "train") -> leaks.Print:
    store = hashlib.sha256(frame.encode()).hexdigest()
    pixel = hashlib.sha256(image).hexdigest()
    source = person.split(":")[0]
    return leaks.Print(frame, person, part, source, store, pixel, leaks.phash(pooled(image), 32))


def check6(prints: tuple[leaks.Print, ...], classes: dict[str, str]) -> tuple[leaks.Finding, ...]:
    """The CHK-6 path the join takes: candidates, the crossing ones, NCC64, the verdict rows."""
    codes = tuple(p.phash for p in prints)
    pairs = leaks.candidate_pairs(codes, leaks.DEFAULT_DISTANCE, frozenset(range(len(codes))), 100)
    scored = tuple(
        leaks.Scored(i, j, d, leaks.ncc(REDUCTIONS[prints[i].frame], REDUCTIONS[prints[j].frame]))
        for i, j, d in leaks.crossing(prints, pairs, classes)
    )
    return leaks.near_duplicates(prints, scored, classes)


REDUCTIONS: dict[str, bytes] = {}


def framed(frame: str, person: str, image: bytes, part: str = "train") -> leaks.Print:
    REDUCTIONS[frame] = image
    return print_of(frame, person, image, part)


def test_a_hash_is_stable_and_a_flat_frame_sets_only_its_mean() -> None:
    image = pooled(pattern(3))
    assert leaks.phash(image, 32) == leaks.phash(bytes(image), 32)
    assert leaks.phash(bytes(64), 8) == 0
    assert leaks.phash(bytes([90]) * 1024, 32) == 1 << 63
    assert bin(leaks.phash(image, 32)).count("1") == 32
    assert (
        leaks.hamming(leaks.phash(image, 32), leaks.phash(pooled(nudged(pattern(3), 1)), 32)) <= 2
    )
    assert leaks.hamming(leaks.phash(image, 32), leaks.phash(pooled(pattern(4)), 32)) > 6


def test_a_hash_is_exact_integers_so_every_machine_sets_the_same_bits() -> None:
    # The fixed-point basis is the one place a platform's cosine enters; every scaled value of
    # every side a hash takes lies far from a half, so no libm's last bit can round it the
    # other way, and the bits of a known image are pinned.
    for side in range(leaks.HASH_SIDE, 65):
        for u in range(leaks.HASH_SIDE):
            for x in range(side):
                scaled = math.cos(math.pi * (2 * x + 1) * u / (2 * side)) * leaks.COSINE_SCALE
                assert abs(abs(scaled) % 1 - 0.5) > 1e-6
    assert f"{leaks.phash(pooled(pattern(3)), 32):016x}" == PINNED_PHASH
    gradient = bytes((x * 7 + y * 3) % 256 for y in range(32) for x in range(32))
    assert leaks.phash(gradient, 32) == leaks.phash(bytes(gradient), 32)


def test_bands_put_back_together_and_the_radius_covers_the_distance() -> None:
    code = 0x0123_4567_89AB_CDEF
    assert leaks.bands(code) == (0xCDEF, 0x89AB, 0x4567, 0x0123)
    assert [leaks.probe_radius(d) for d in (0, 3, 4, 6, 7, 8, 11)] == [0, 0, 1, 1, 1, 2, 2]


def test_the_candidate_search_finds_every_pair_the_all_pairs_search_finds() -> None:
    rnd = random.Random(7)
    bases = [rnd.getrandbits(64) for _ in range(12)]
    codes = tuple(
        base ^ sum(1 << b for b in rnd.sample(range(64), rnd.randrange(0, 12)))
        for base in bases
        for _ in range(8)
    )
    for threshold in (0, 2, 5, 6, 9):
        for probes in (frozenset(range(len(codes))), frozenset(range(0, len(codes), 5))):
            expected = sorted(
                (i, j, leaks.hamming(codes[i], codes[j]))
                for i in range(len(codes))
                for j in range(i + 1, len(codes))
                if leaks.hamming(codes[i], codes[j]) <= threshold and (i in probes or j in probes)
            )
            assert list(leaks.candidate_pairs(codes, threshold, probes, 10_000)) == expected


def test_a_search_past_its_budget_says_so_by_one_pair_more() -> None:
    codes = tuple([0x00FF_00FF_00FF_00FF] * 10)
    pairs = leaks.candidate_pairs(codes, 0, frozenset(range(10)), 7)
    assert len(pairs) == 8


def test_ncc_is_one_for_a_copy_minus_one_for_a_negative_and_zero_for_a_flat_frame() -> None:
    image = pattern(5)
    assert leaks.ncc(image, image) == 1.0
    assert leaks.ncc(image, bytes(255 - v for v in image)) == pytest.approx(-1.0)
    assert leaks.ncc(image, bytes([77]) * len(image)) == 0.0
    assert leaks.ncc(bytes(10), bytes(10)) == 1.0
    assert leaks.ncc(image, nudged(image, 2)) >= leaks.NCC_MIN
    assert leaks.ncc(image, pattern(6)) < leaks.NCC_MIN
    other = pattern(8)
    assert leaks.ncc_with(image, other, leaks.moments(image), leaks.moments(other)) == leaks.ncc(
        image, other
    )


def test_chk6_catches_a_re_exposed_copy_under_another_person() -> None:
    original, copy = pattern(11), nudged(pattern(11), 3)
    prints = (
        framed("a/1.png", "src:p1", original),
        framed("a/2.png", "src:p2", pattern(12)),
        framed("b/1.png", "src:p9", copy),
    )
    rows = check6(prints, {})
    assert [(r.check, r.frames, r.persons) for r in rows] == [
        ("CHK-6", ("a/1.png", "b/1.png"), ("src:p1", "src:p9"))
    ]
    assert rows[0].reason == "near-duplicate under two persons" and rows[0].ncc is not None
    assert rows[0].ncc >= leaks.NCC_MIN


def test_chk6_leaves_one_person_in_one_part_and_catches_one_person_in_two() -> None:
    original, copy = pattern(21), nudged(pattern(21), 4)
    same_side = (framed("a/1.png", "src:p1", original), framed("a/2.png", "src:p1", copy))
    assert check6(same_side, {}) == ()
    joined = (framed("a/3.png", "src:p1", original), framed("b/3.png", "other:q1", copy))
    assert check6(joined, {"other:q1": "other:q1", "src:p1": "other:q1"}) == ()
    split = (
        framed("a/4.png", "src:p1", original, "train"),
        framed("b/4.png", "other:q1", copy, "validation"),
    )
    rows = check6(split, {"other:q1": "other:q1", "src:p1": "other:q1"})
    assert [r.reason for r in rows] == ["near-duplicate across parts"]


def test_chk7_catches_an_exact_copy_under_two_persons_once() -> None:
    image = pattern(31)
    a = print_of("a/1.png", "src:p1", image)
    b = leaks.Print("b/1.png", "src:p2", "train", "src", a.store_key, a.pixel_key, a.phash)
    rows = leaks.shared_keys((a, b, print_of("a/2.png", "src:p3", pattern(32))), {}, {})
    assert len(rows) == 1
    assert rows[0].reason == "undeclared alias: one key under two persons (store_key)"
    assert rows[0].key == a.store_key and rows[0].persons == ("src:p1", "src:p2")


def test_chk7_takes_a_declaration_and_still_fails_a_declared_person_on_two_sides() -> None:
    image = pattern(41)
    a = print_of("a/1.png", "one:p1", image)
    b = leaks.Print("b/1.png", "two:q1", "train", "two", "f" * 64, a.pixel_key, a.phash)
    persons = leaks.alias_classes((("one:p1", "two:q1"),))
    assert leaks.shared_keys((a, b), persons, {})[0].reason.startswith(
        "undeclared alias: one key under two sources"
    )
    sources = leaks.alias_classes((("one", "two"),))
    assert leaks.shared_keys((a, b), persons, sources) == ()
    split = leaks.Print("b/1.png", "two:q1", "validation", "two", "f" * 64, a.pixel_key, a.phash)
    rows = leaks.shared_keys((a, split), persons, sources)
    assert [r.reason for r in rows] == ["declared alias split across parts (pixel_key)"]


def test_alias_classes_join_declarations_that_share_a_name() -> None:
    classes = leaks.alias_classes((("c", "d"), ("b", "c"), ("x", "y")))
    assert classes == {"b": "b", "c": "b", "d": "b", "x": "x", "y": "x"}


def test_a_frame_with_no_keys_fails_and_the_verdict_counts_every_row() -> None:
    rows = leaks.unfingerprinted((("s/1.png", "src:p1", "src", "unreadable (OSError)"),))
    assert rows[0].check == leaks.UNKNOWN and rows[0].reason.startswith("not fingerprinted")
    assert leaks.verdict(rows) == leaks.FAIL and leaks.verdict(()) == leaks.PASS
    assert leaks.counts(rows) == {"CHK-6": 0, "CHK-7": 0, "UNKNOWN": 1}


# --- the tool, over shards tools/ingest.py cut from synthetic banks ----------------------------


def shard(tmp: Path, source: str, seed: int) -> Path:
    """A real shard of twelve synthetic frames of four persons under <tmp>/data/<source>/."""
    bank = tmp / f"bank-{source}"
    load("synthetic_bank").main([str(bank), "--frames", "12", "--cases", "4", "--seed", str(seed)])
    root = tmp / "data" / source
    argv = ["run", "--bank", str(bank), "--source", source, "--kind", "train", "--date"]
    argv += ["2026-10-21", "--code-commit", "abcdef1", "--grid-root", str(root)]
    assert load("ingest").main(argv) == 0
    (folder,) = sorted((root / "shards").iterdir())
    return folder


def frame_row(item: Any, source: str, image: bytes) -> dict[str, str]:
    return {
        "record": "frame",
        "frame": item.path,
        "person": item.person,
        "source": source,
        "store_key": item.sha256,
        "pixel_key": hashlib.sha256(image).hexdigest(),
        "phash": f"{leaks.phash(pooled(image), 32):016x}",
        "ncc64": base64.b64encode(image).decode("ascii"),
    }


def write_prints(
    folder: Path, out: Path, change: dict[int, dict[str, str]]
) -> list[dict[str, str]]:
    """The fingerprint file of a shard, each frame drawn from its own seed; `change` overwrites
    fields of some rows, which is how a test plants a copy."""
    manifest, digest = TOOL.read_manifest(folder)
    items = sorted(manifest.items, key=lambda i: i.path)
    rows = [frame_row(it, manifest.source, pattern(int(it.sha256[:8], 16))) for it in items]
    for index, fields in change.items():
        rows[index] = {k: v for k, v in {**rows[index], **fields}.items() if v != ""}
    header = {
        "record": "shard",
        "shard": manifest.name,
        "source": manifest.source,
        "kind": manifest.kind.value,
        "supersedes": manifest.supersedes,
        "manifest_sha256": digest,
        "fingerprint_version": TOOL.FINGERPRINT_VERSION,
        "frames": len(rows),
        "errors": sum(1 for r in rows if "error" in r),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(TOOL.line(r) + "\n" for r in [header, *rows]), encoding="utf-8")
    return rows


def join(tmp: Path, *extra: str) -> tuple[int, dict[str, Any]]:
    out = tmp / "out"
    argv = ["join", "--fingerprints", str(tmp / "fp" / "*.jsonl"), "--out", str(out), *extra]
    code = TOOL.main(argv)
    return code, json.loads((out / "LEAKS.json").read_text(encoding="utf-8"))


@pytest.fixture
def two_shards(tmp_path: Path) -> tuple[Path, Path, Path]:
    return tmp_path, shard(tmp_path, "carmlspine", 1), shard(tmp_path, "carmlspine_sweeps", 2)


def test_the_join_passes_two_clean_shards_and_writes_the_same_bytes_twice(
    two_shards: tuple[Path, Path, Path],
) -> None:
    tmp, a, b = two_shards
    write_prints(a, tmp / "fp" / "a.jsonl", {})
    write_prints(b, tmp / "fp" / "b.jsonl", {})
    listing = tmp / "shards.txt"
    listing.write_text(f"{a}\n{b}\n", encoding="utf-8")
    code, result = join(tmp, "--expect", str(listing))
    assert code == 0 and result["verdict"] == "PASS" and result["frames"] == 24
    first = (tmp / "out" / "LEAKS.json").read_bytes()
    assert join(tmp, "--expect", str(listing))[0] == 0
    assert (tmp / "out" / "LEAKS.json").read_bytes() == first
    assert (tmp / "out" / "LEAKS.md").read_text(encoding="utf-8").startswith("# Leak checks: PASS")


def test_the_join_fails_a_copy_across_shards_and_persons(
    two_shards: tuple[Path, Path, Path],
) -> None:
    tmp, a, b = two_shards
    rows_a = write_prints(a, tmp / "fp" / "a.jsonl", {})
    near = base64.b64encode(nudged(base64.b64decode(rows_a[3]["ncc64"]), 9)).decode("ascii")
    near_pixels = hashlib.sha256(base64.b64decode(near)).hexdigest()
    near_hash = f"{leaks.phash(pooled(base64.b64decode(near)), 32):016x}"
    copied = {k: rows_a[0][k] for k in ("store_key", "pixel_key", "phash", "ncc64")}
    planted = {"ncc64": near, "pixel_key": near_pixels, "phash": near_hash}
    write_prints(b, tmp / "fp" / "b.jsonl", {0: copied, 5: planted})
    code, result = join(tmp)
    assert code == 1 and result["verdict"] == "FAIL"
    assert result["counts"] == {"CHK-6": 1, "CHK-7": 1, "UNKNOWN": 0, "input_problems": 0}
    checks = {row["check"]: row for row in result["rows"]}
    assert checks["CHK-7"]["key"] == rows_a[0]["store_key"]
    assert checks["CHK-6"]["ncc"] >= leaks.NCC_MIN


def test_a_frame_never_fingerprinted_and_a_shard_never_listed_fail_the_join(
    two_shards: tuple[Path, Path, Path],
) -> None:
    tmp, a, b = two_shards
    write_prints(a, tmp / "fp" / "a.jsonl", {2: {"error": "cannot decode (OSError)", "phash": ""}})
    listing = tmp / "shards.txt"
    listing.write_text(f"{a}\n{b}\n", encoding="utf-8")
    code, result = join(tmp, "--expect", str(listing))
    assert code == 1 and result["counts"]["UNKNOWN"] == 1
    assert any("no fingerprint of carmlspine_sweeps/" in p for p in result["input_problems"])


def test_an_unreadable_fingerprint_file_fails_the_join(two_shards: tuple[Path, Path, Path]) -> None:
    tmp, a, _ = two_shards
    write_prints(a, tmp / "fp" / "a.jsonl", {})
    (tmp / "fp" / "b.jsonl").write_text('{"record": "shard"\n', encoding="utf-8")
    code, result = join(tmp)
    assert code == 1 and result["verdict"] == "FAIL"
    assert result["input_problems"] == [
        f"{tmp / 'fp' / 'b.jsonl'}: not a readable fingerprint file (JSONDecodeError)"
    ]


def test_a_new_shard_is_checked_against_the_rest_and_a_superseded_one_is_dropped(
    two_shards: tuple[Path, Path, Path],
) -> None:
    tmp, a, b = two_shards
    rows_a = write_prints(a, tmp / "fp" / "a.jsonl", {})
    copied = {k: rows_a[0][k] for k in ("store_key", "pixel_key", "phash", "ncc64")}
    write_prints(b, tmp / "fp" / "b.jsonl", {0: copied})
    code, result = join(tmp, "--new", str(b))
    assert code == 1 and result["settings"]["new"].startswith("carmlspine_sweeps/")
    assert result["counts"]["CHK-7"] == 1
    first_a, *_ = (tmp / "fp" / "a.jsonl").read_text(encoding="utf-8").splitlines()
    head_b, *rest_b = (tmp / "fp" / "b.jsonl").read_text(encoding="utf-8").splitlines()
    superseded = json.loads(first_a)["shard"]
    successor = dict(json.loads(head_b), supersedes=superseded)
    (tmp / "fp" / "b.jsonl").write_text("\n".join([TOOL.line(successor), *rest_b]) + "\n")
    code, result = join(tmp)
    assert code == 0 and result["superseded_dropped"] == [superseded]


def test_a_frame_that_cannot_be_read_or_does_not_match_its_hash_is_a_line_with_its_reason(
    tmp_path: Path,
) -> None:
    folder = shard(tmp_path, "carmlspine", 3)
    manifest, _ = TOOL.read_manifest(folder)
    item = manifest.items[0]
    gone = TOOL.fingerprint_frame((str(folder), "00/" + "0" * 64 + ".png", "0" * 64, "x:1", "x"))
    assert gone["error"] == "unreadable (FileNotFoundError)" and "store_key" not in gone
    wrong = TOOL.fingerprint_frame((str(folder), item.path, "1" * 64, item.person, "carmlspine"))
    assert wrong["error"] == "the bytes do not match the manifest's sha256"


def test_a_person_key_spelled_like_a_source_never_joins_two_sources(tmp_path: Path) -> None:
    # Persons whose keys read "source:one" and "source:two", declared one person, are a person
    # alias only: the sources one and two stay two, so one key under both still fails.
    declared = tmp_path / "aliases.json"
    groups = [{"persons": ["one:p1", "two:q1"], "why": "a crosswalk"}]
    groups.append({"persons": ["source:one", "source:two"], "why": "a person so keyed"})
    declared.write_text(json.dumps({"persons": groups, "sources": []}), encoding="utf-8")
    persons, sources = TOOL.load_declared(declared)
    assert sources == {}
    image = pattern(51)
    a = print_of("a/1.png", "one:p1", image)
    b = leaks.Print("b/1.png", "two:q1", "train", "two", "f" * 64, a.pixel_key, a.phash)
    (row,) = leaks.shared_keys((a, b), persons, sources)
    assert row.reason == "undeclared alias: one key under two sources (pixel_key)"


def test_a_line_with_a_key_missing_or_malformed_is_a_frame_never_fingerprinted(
    two_shards: tuple[Path, Path, Path],
) -> None:
    tmp, a, b = two_shards
    write_prints(a, tmp / "fp" / "a.jsonl", {1: {"ncc64": "AAAA"}, 4: {"pixel_key": ""}})
    write_prints(b, tmp / "fp" / "b.jsonl", {2: {"phash": "not-hex-at-all!!"}})
    code, result = join(tmp)
    assert code == 1 and result["counts"]["UNKNOWN"] == 3
    assert {row["reason"] for row in result["rows"]} == {
        "not fingerprinted: a fingerprint line with a key missing or malformed"
    }


class Interrupted(Exception):
    """What a requeue looks like to the task: the work stops part way."""


def test_a_requeued_fingerprint_takes_up_the_chunks_it_finished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = shard(tmp_path, "carmlspine", 4)
    manifest, _ = TOOL.read_manifest(folder)
    paths = sorted(item.path for item in manifest.items)
    seen: list[str] = []

    def stopping_at(limit: int) -> Any:
        def fake(task: tuple[str, str, str, str, str]) -> dict[str, str]:
            if len(seen) == limit:
                raise Interrupted
            seen.append(task[1])
            return {"record": "frame", "frame": task[1], "person": task[3], "source": task[4]}

        return fake

    monkeypatch.setattr(TOOL, "imaging", lambda: None)
    monkeypatch.setattr(TOOL, "CHUNK_FRAMES", 5)
    out = tmp_path / "fp" / "a.jsonl"
    monkeypatch.setattr(TOOL, "fingerprint_frame", stopping_at(7))
    with pytest.raises(Interrupted):
        TOOL.fingerprint(folder, out, 1)
    assert seen == paths[:7] and not out.exists()
    seen.clear()
    monkeypatch.setattr(TOOL, "fingerprint_frame", stopping_at(len(paths)))
    answer = TOOL.fingerprint(folder, out, 1)
    assert seen == paths[5:] and answer["chunks_resumed"] == 1 and answer["errors"] == 0
    lines = out.read_text(encoding="utf-8").splitlines()
    assert [json.loads(text)["frame"] for text in lines[1:]] == paths
    assert not Path(f"{out}.parts").exists()


# --- the grid scripts --------------------------------------------------------------------------


def run_leaks(data_root: Path, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ROOT / "grid" / "run-leaks.sh")],
        env={**os.environ, "SCHWINGNET": str(ROOT), "DATA_ROOT": str(data_root), **env},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_the_dry_run_submits_one_array_task_a_shard_and_the_join_after_it(tmp_path: Path) -> None:
    for name in ("alpha/shards/2026-10-21-aaaaaaaaaaaa", "beta/shards/2026-10-21-bbbbbbbbbbbb"):
        (tmp_path / name).mkdir(parents=True)
        (tmp_path / name / "MANIFEST.json").write_text("{}", encoding="utf-8")
    done = run_leaks(tmp_path, HPCW_DRY="1", CONCURRENCY="3", LEAKS_OUT=str(tmp_path / "_leaks"))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "--name leaks_fingerprint --class batch" in done.stderr and "--array 0-1%3 -- 04-leaks.sbatch" in done.stderr
    assert "--name leaks_join --class batch" in done.stderr and "--after DRY_leaks_fingerprint:any -- 05-leaks-join.sbatch" in done.stderr
    assert "05-leaks-join.sbatch" in done.stderr and "shards: 2 listed" in done.stdout
    (listing,) = (tmp_path / "_leaks" / "runs").glob("*/shards.txt")
    assert listing.read_text(encoding="utf-8").splitlines() == [
        str(tmp_path / "alpha/shards/2026-10-21-aaaaaaaaaaaa"),
        str(tmp_path / "beta/shards/2026-10-21-bbbbbbbbbbbb"),
    ]


def test_a_staging_folder_is_never_listed_even_under_a_root_inside_a_shards_folder(
    tmp_path: Path,
) -> None:
    # find's -path lets a wildcard cross a slash, so a pattern alone would match a `shards` in
    # the data root's own path; the staging folder, and a folder whose parent is not shards, are
    # left out by their own names.
    root = tmp_path / "shards" / "data"
    for name in (
        "src/shards/2026-10-21-aaaaaaaaaaaa",
        "src/shards/.ingest-2026-10-21-aaaaaaaaaaaa-x",
        "src/raw/2026-10-21-bbbbbbbbbbbb",
    ):
        (root / name).mkdir(parents=True)
        (root / name / "MANIFEST.json").write_text("{}", encoding="utf-8")
    done = run_leaks(root, HPCW_DRY="1", LEAKS_OUT=str(tmp_path / "_leaks"))
    assert done.returncode == 0, done.stdout + done.stderr
    (listing,) = (tmp_path / "_leaks" / "runs").glob("*/shards.txt")
    assert listing.read_text(encoding="utf-8").splitlines() == [
        str(root / "src/shards/2026-10-21-aaaaaaaaaaaa")
    ]


def test_the_submit_refuses_a_data_root_with_no_shard(tmp_path: Path) -> None:
    done = run_leaks(tmp_path, HPCW_DRY="1", LEAKS_OUT=str(tmp_path / "_leaks"))
    assert done.returncode == 64 and "nothing to check" in done.stdout
