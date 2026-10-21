"""The catalog's rules (schwingnet.catalog) and the tool around them (tools/catalog.py)."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from icontract import ViolationError
from pydantic import ValidationError

from schwingnet.catalog import (
    DEFAULT_PARTS,
    HASH_SPACE,
    LEVELS,
    DeviceClass,
    FrozenPerson,
    Item,
    Modality,
    Part,
    Query,
    Region,
    RegistryEntry,
    ShardManifest,
    SplitRule,
    View,
    band,
    best,
    content_digest,
    cosine,
    hash_part,
    is_transitional,
    part_of,
    region_of,
    shard_name,
    view_band,
    where_clause,
)

ROOT = Path(__file__).resolve().parents[2]
SHA = "0" * 64


def load_tool():
    spec = importlib.util.spec_from_file_location("catalog_tool", ROOT / "tools" / "catalog.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def test_every_level_has_a_region_and_only_the_rare_two_are_transitional() -> None:
    assert len(LEVELS) == 27
    assert region_of("C3") is Region.CERVICAL
    assert region_of("T13") is Region.THORACIC
    assert region_of("L6") is Region.LUMBAR
    assert region_of("sacrum") is Region.SACRUM
    assert [lvl for lvl in LEVELS if is_transitional(lvl)] == ["T13", "L6"]
    with pytest.raises(ViolationError):
        region_of("L7")


def test_the_hash_split_is_a_share_of_the_hash_space_and_the_frozen_list_wins() -> None:
    assert hash_part(0, 0.1) is Part.VALIDATION
    assert hash_part(HASH_SPACE - 1, 0.1) is Part.TRAIN
    assert hash_part(int(0.1 * HASH_SPACE) - 1, 0.1) is Part.VALIDATION
    frozen = frozenset({"carmlspine:case42"})
    assert part_of("carmlspine:case42", 0, 0.1, frozen) is Part.TEST
    assert part_of("carmlspine:case7", 0, 0.1, frozen) is Part.VALIDATION
    with pytest.raises(ViolationError):
        part_of(" case7", 0, 0.1, frozen)


def test_view_bands_fold_the_angle_and_exposure_bands_start_at_a_multiple() -> None:
    assert view_band(0.0) is View.FRONTAL
    assert view_band(180.0) is View.FRONTAL
    assert view_band(-90.0) is View.LATERAL
    assert view_band(270.0) is View.LATERAL
    assert view_band(45.0) is View.OBLIQUE
    assert band(73.0, 10) == 70
    assert band(0.0, 5) == 0


def test_cosine_ranks_and_best_keeps_the_given_order_on_ties() -> None:
    assert cosine((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)
    assert best((("c", 0.9), ("a", 0.2), ("b", 0.9)), 2) == ("c", "b")
    assert best((("a", 0.2),), 5) == ("a",)
    assert best((), 3) == ()
    for bad in [(("a", 0.2), ("a", 0.3)), (("a", float("nan")),)]:
        with pytest.raises(ViolationError):
            best(bad, 1)
    for a, b in [((0.0, 0.0), (1.0, 0.0)), ((3.0,), (5e-309,)), ((1.0,), (1.0, 0.0))]:
        with pytest.raises(ViolationError):
            cosine(a, b)


def test_a_shard_is_named_by_source_day_and_content_in_any_order() -> None:
    digest = content_digest(("a" * 64, "b" * 64))
    assert digest == content_digest(("b" * 64, "a" * 64))
    assert shard_name("carmlspine", "2026-10-21", digest) == f"carmlspine/2026-10-21-{digest[:12]}"
    for args in [("carm/lspine", "2026-10-21", digest), ("carmlspine", "2026-10-21", "ab")]:
        with pytest.raises(ViolationError):
            shard_name(*args)
    with pytest.raises(ViolationError):
        content_digest(("ab",))


def test_a_query_is_one_parameterised_where_clause_that_never_reads_test_unasked() -> None:
    clause, params = where_clause(Query())
    assert clause == " WHERE item.part IN (?, ?)" and params == ("train", "validation")
    clause, params = where_clause(
        Query(levels=("L5", "sacrum"), views=(View.LATERAL,), parts=(Part.TRAIN,), kvp_band=70)
    )
    assert clause.count("?") == len(params) == 6
    assert "label.level IS NOT NULL" in clause
    assert params == ("train", "L5", "sacrum", "lateral", 70, 80)
    assert "label.level IS NOT NULL" in where_clause(Query(labelled_only=True))[0]
    assert "test" in where_clause(Query(parts=(Part.TEST,)))[1]
    with pytest.raises(ViolationError):
        where_clause(Query(kvp_band=70, kvp_band_width=0))


def test_the_registry_and_the_split_files_validate() -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    assert {"carmlspine", "carmlspine_sweeps"} <= set(inputs.registry)
    assert "carmlspine:case42" in inputs.test_persons and "carmlspine:case134" in inputs.test_persons
    assert inputs.rule.validation_share == 0.1
    assert tool.person_part("carmlspine:case42", inputs.test_persons, inputs.rule)[0] is Part.TEST
    hashed = tool.person_hash(inputs.rule.salt, "carmlspine:case7")
    digest = hashlib.sha256(f"schwingnet-split|{inputs.rule.salt}|carmlspine:case7".encode()).digest()
    assert hashed == int.from_bytes(digest[:8], "big")
    assert len(inputs.test_persons_sha256) == 64


def test_a_frozen_person_of_an_unregistered_source_is_refused(tmp_path: Path) -> None:
    tool = load_tool()
    persons = tmp_path / "p.json"
    persons.write_text(json.dumps([{"person": "nowhere:case1", "why": "a typo"}]), encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="names no registered source"):
        tool.load_inputs(test_persons_path=persons)


def test_the_shapes_refuse_what_the_catalog_cannot_hold() -> None:
    with pytest.raises(ValidationError):
        FrozenPerson(person=" x", why="w")
    with pytest.raises(ValidationError):
        SplitRule(salt="s", validation_share=1.0, hash="h")
    with pytest.raises(ValidationError):
        RegistryEntry.model_validate({"source": "carmlspine"})
    with pytest.raises(ValidationError, match="its facts name it"):
        ShardManifest.model_validate(dict(manifest("train", [item("p", "L5", "a.png", SHA)]), name="carmlspine/2026-10-21-000000000000"))
    with pytest.raises(ValidationError, match="no . or .. segment"):
        Item.model_validate(item("p", "L5", "../etc/passwd", SHA))


def item(person: str, level: str, path: str, sha: str, angle: float = 90.0) -> dict[str, object]:
    return {
        "path": path,
        "sha256": sha,
        "person": person,
        "modality": Modality.XA.value,
        "device": {"device_class": DeviceClass.MOBILE_C_ARM.value, "make": "Ziehm"},
        "exposure": {"kvp": 73.0, "mas": 2.5, "px_mm": 0.3},
        "lat_from_ap_deg": angle,
        "labels": [{"level": level, "box": [0.1, 0.1, 0.5, 0.5], "labeller": "cbct"}],
    }


def manifest(kind: str, items: list[dict[str, object]], supersedes: str | None = None) -> dict[str, object]:
    digest = content_digest(tuple(str(i["sha256"]) for i in items))
    return {
        "schema_version": 1,
        "name": shard_name("carmlspine", "2026-10-21", digest),
        "source": "carmlspine",
        "kind": kind,
        "ingest_date": "2026-10-21",
        "code_commit": "0123abc",
        "supersedes": supersedes,
        "items": items,
    }


def write(folder: Path, name: str, data: dict[str, object]) -> Path:
    path = folder / name / "MANIFEST.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


TRAIN_ITEMS = [
    item("carmlspine:case7", "L5", "a.png", "a" * 64, 90.0),
    item("carmlspine:case7", "L4", "b.png", "b" * 64, 0.0),
    item("carmlspine:case8", "L6", "c.png", "c" * 64, 88.0),
]
TEST_ITEMS = [item("carmlspine:case42", "L6", "d.png", "d" * 64, 91.0)]


def built(tool, tmp_path: Path, manifests: list[Path]) -> tuple[Path, str]:
    out = tmp_path / "catalog.sqlite"
    return out, tool.build(out, manifests, tool.load_inputs())


def test_a_catalog_builds_from_manifests_and_answers_queries(tmp_path: Path) -> None:
    tool = load_tool()
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS))
    test = write(tmp_path, "test", manifest("test", TEST_ITEMS))
    review = write(tmp_path, "review", manifest("review", [TRAIN_ITEMS[2]]))
    out, digest = built(tool, tmp_path, [train, test, review])
    assert digest == hashlib.sha256(out.read_bytes()).hexdigest()
    assert tool.build(tmp_path / "again.sqlite", [train, test, review], tool.load_inputs()) == digest
    db = tool.open_catalog(out)
    lateral = tool.run_query(db, Query(views=(View.LATERAL,)))
    assert [(r["path"], r["shard"][:16]) for r in lateral] == [
        ("a.png", "carmlspine/2026-"), ("c.png", "carmlspine/2026-"), ("c.png", "carmlspine/2026-")
    ]
    assert {r["person"] for r in tool.run_query(db, Query(levels=("L6",)))} == {"carmlspine:case8"}
    rare = tool.run_query(db, Query(levels=("L6",), parts=(*DEFAULT_PARTS, Part.TEST)))
    assert {r["person"] for r in rare} == {"carmlspine:case8", "carmlspine:case42"}
    assert tool.run_query(db, Query(parts=(Part.TEST,)))[0]["person"] == "carmlspine:case42"
    assert tool.run_query(db, Query(kvp_band=70, device_classes=(DeviceClass.FILM,))) == []
    counts = tool.summary(db)
    assert counts["test_persons"] == [{"person": "carmlspine:case42", "frame_count": 1}]
    assert {"level": "L6", "part": "test", "boxes": 1} in counts["by_level_and_part"]
    assert tool.export(db, "item", tmp_path / "item.jsonl") == 5
    assert tool.export(db, "shard", tmp_path / "shard.jsonl") == 3
    assert tool.manifest_paths(tool.load_inputs().registry, [], "/grid") == []


def test_what_a_build_refuses_leaves_nothing_behind(tmp_path: Path) -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    old = manifest("train", TRAIN_ITEMS[:1])
    cases = {
        "test persons": manifest("train", TEST_ITEMS),
        "not a test person": manifest("test", TRAIN_ITEMS[:1]),
        "also loaded": manifest("train", TRAIN_ITEMS, supersedes=str(old["name"])),
    }
    for message, data in cases.items():
        folder = tmp_path / message.replace(" ", "_")
        paths = [write(folder, "bad", data)]
        if message == "also loaded":
            paths.append(write(folder, "old", old))
        with pytest.raises(tool.CatalogError, match=message):
            tool.build(folder / "c.sqlite", paths, inputs)
        assert sorted(p.name for p in folder.iterdir()) == sorted({"bad", "old"} & {p.parent.name for p in paths})
    with pytest.raises(tool.CatalogError, match="No such file"):
        tool.build(tmp_path / "c.sqlite", [tmp_path / "missing.json"], inputs)


def test_embeddings_load_into_a_fresh_file_and_similar_never_ranks_a_test_frame(tmp_path: Path) -> None:
    tool = load_tool()
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS))
    test = write(tmp_path, "test", manifest("test", TEST_ITEMS))
    out, before = built(tool, tmp_path, [train, test])
    vectors = tmp_path / "v.jsonl"
    rows = [("a" * 64, [1.0, 0.0]), ("b" * 64, [0.0, 1.0]), ("c" * 64, [0.9, 0.1]), ("d" * 64, [1.0, 0.0])]
    vectors.write_text("\n".join(json.dumps({"item": i, "vector": v}) for i, v in rows), encoding="utf-8")
    loaded, after = tool.embed(out, "v1", vectors)
    assert loaded == 4 and after != before and not (tmp_path / "catalog.sqlite.building").exists()
    db = tool.open_catalog(out)
    assert [r["item"] for r in tool.similar(db, "v1", "a" * 64, 1)] == ["c" * 64]
    with_test = tool.similar(db, "v1", "a" * 64, 1, (*DEFAULT_PARTS, Part.TEST))
    assert [r["item"] for r in with_test] == ["d" * 64]
    with pytest.raises(tool.CatalogError, match="no embedding"):
        tool.similar(db, "v2", "a" * 64, 1)
    vectors.write_text(json.dumps({"item": "f" * 64, "vector": [1.0]}), encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="no frame of the catalog"):
        tool.embed(out, "v1", vectors)
    vectors.write_text(json.dumps({"item": "a" * 64, "vector": []}), encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="same length"):
        tool.embed(out, "v1", vectors)
    assert tool.main(["query", str(out), "--levels", "L5,L4", "--count"]) == 0
    assert tool.main(["similar", str(out), "--model", "v1", "--item", "a" * 64, "--k", "2"]) == 0


def test_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tool = load_tool()
    assert tool.main(["summary", str(tmp_path / "none.sqlite")]) == 1
    assert "no catalog there" in capsys.readouterr().err
    assert tool.main(["check"]) == 0 and "registry: 2 sources" in capsys.readouterr().out
    assert tool.main(["part", " carmlspine:case42 "]) == 0 and capsys.readouterr().out.strip() == "test"
    assert tool.main(["schema"]) == 0 and "CREATE TABLE item" in capsys.readouterr().out
    assert tool.main(["build", "--out", str(tmp_path / "c.sqlite")]) == 1
    assert "no manifest to read" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        tool.main(["similar", "x", "--model", "v", "--item", "a", "--k", "-1"])
