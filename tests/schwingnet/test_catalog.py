"""The catalog's rules (schwingnet.catalog) and the tool around them (tools/catalog.py)."""

import hashlib
import importlib.util
import json
import sqlite3
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
    VersionRecord,
    View,
    band,
    best,
    changed_keys,
    content_digest,
    cosine,
    frame_path,
    hash_part,
    is_transitional,
    part_of,
    region_of,
    shard_folder,
    shard_name,
    version_file_name,
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
    with pytest.raises(ViolationError):
        hash_part(0, 1e-4)
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


def test_the_layout_puts_every_frame_shard_and_version_in_one_computable_place() -> None:
    assert frame_path("ab" * 32, "png") == "ab/" + "ab" * 32 + ".png"
    assert shard_folder("/grid/data/carmlspine", "carmlspine/2026-10-21-" + "0" * 12) == (
        "/grid/data/carmlspine/shards/2026-10-21-" + "0" * 12
    )
    assert version_file_name(7, "f" * 64) == "catalog-000007-ffffffffffff.sqlite"
    assert changed_keys(frozenset({"a", "b"}), frozenset({"b", "c", "a0"})) == (("a0", "c"), ("a",))
    assert changed_keys(frozenset(), frozenset()) == ((), ())
    with pytest.raises(ViolationError):
        frame_path("ab", "png")
    with pytest.raises(ViolationError):
        frame_path("ab" * 32, "tar.gz")
    with pytest.raises(ViolationError):
        shard_folder("/grid/carmlspine/", "carmlspine/x")
    with pytest.raises(ViolationError):
        shard_folder("/grid/carmlspine", "carmlspine")
    with pytest.raises(ViolationError):
        shard_folder("/grid/other", "carmlspine/x")
    with pytest.raises(ViolationError):
        version_file_name(0, "f" * 64)
    with pytest.raises(ViolationError):
        version_file_name(1, "f/" * 8)


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
    assert list(inputs.registry) == sorted(inputs.registry)
    assert {"carmlspine", "carmlspine_sweeps"} <= set(inputs.registry)
    assert (
        "carmlspine:case42" in inputs.test_persons and "carmlspine:case134" in inputs.test_persons
    )
    assert inputs.rule.validation_share == 0.1
    assert tool.person_part("carmlspine:case42", inputs.test_persons, inputs.rule)[0] is Part.TEST
    hashed = tool.person_hash(inputs.rule.salt, "carmlspine:case7")
    digest = hashlib.sha256(
        f"schwingnet-split|{inputs.rule.salt}|carmlspine:case7".encode()
    ).digest()
    assert hashed == int.from_bytes(digest[:8], "big")
    assert len(inputs.test_persons_sha256) == 64


def test_a_frozen_person_of_an_unregistered_source_is_refused(tmp_path: Path) -> None:
    tool = load_tool()
    persons = tmp_path / "p.json"
    persons.write_text(json.dumps([{"person": "nowhere:case1", "why": "a typo"}]), encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="names no registered source"):
        tool.load_inputs(test_persons_path=persons)


def registry_entry(source: str, shards: list[dict[str, str]]) -> dict[str, object]:
    return {
        "source": source,
        "identity_level": "patient",
        "person_key_rule": f"{source}:<case>",
        "access": "held",
        "modality": "xa",
        "device_class": "mobile_c_arm",
        "regions": ["lumbar"],
        "grid_root": f"/grid/data/{source}",
        "shards": shards,
    }


def test_a_registry_file_is_named_by_its_source_and_its_shards_lie_in_the_layout(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    name = "carmlspine/2026-10-21-" + "0" * 12
    good = {
        "name": name,
        "kind": "train",
        "manifest": f"/grid/data/carmlspine/shards/2026-10-21-{'0' * 12}/MANIFEST.json",
    }
    (tmp_path / "carmlspine.json").write_text(
        json.dumps(registry_entry("carmlspine", [good])), encoding="utf-8"
    )
    assert list(tool.load_registry(tmp_path)) == ["carmlspine"]
    (tmp_path / "other.json").write_text(
        json.dumps(registry_entry("carmlspine", [])), encoding="utf-8"
    )
    with pytest.raises(tool.CatalogError, match="named other but the source is carmlspine"):
        tool.load_registry(tmp_path)
    (tmp_path / "other.json").unlink()
    bad = {"name": name, "kind": "train", "manifest": "/grid/elsewhere/MANIFEST.json"}
    (tmp_path / "carmlspine.json").write_text(
        json.dumps(registry_entry("carmlspine", [bad])), encoding="utf-8"
    )
    with pytest.raises(
        tool.CatalogError, match="the layout puts it at /grid/data/carmlspine/shards/"
    ):
        tool.load_registry(tmp_path)
    elsewhere = dict(registry_entry("carmlspine", []), grid_root="/grid/data/other")
    (tmp_path / "carmlspine.json").write_text(json.dumps(elsewhere), encoding="utf-8")
    with pytest.raises(
        tool.CatalogError, match="grid_root /grid/data/other is not the folder carmlspine"
    ):
        tool.load_registry(tmp_path)


def test_the_shapes_refuse_what_the_catalog_cannot_hold() -> None:
    with pytest.raises(ValidationError):
        FrozenPerson(person=" x", why="w")
    with pytest.raises(ValidationError):
        SplitRule(salt="s", validation_share=1.0, hash="h")
    with pytest.raises(ValidationError):
        SplitRule(salt="s", validation_share=1e-4, hash="h")
    with pytest.raises(ValidationError):
        RegistryEntry.model_validate({"source": "carmlspine"})
    with pytest.raises(ValidationError, match="its facts name it"):
        ShardManifest.model_validate(
            dict(
                manifest("train", [item("p", "L5", SHA)]), name="carmlspine/2026-10-21-000000000000"
            )
        )
    with pytest.raises(ValidationError, match="pattern"):
        Item.model_validate(dict(item("p", "L5", SHA), path="../etc/passwd"))
    with pytest.raises(ValidationError, match="its digest puts it at"):
        Item.model_validate(dict(item("p", "L5", SHA), path=frame_path("1" * 64, "png")))
    record = {
        "version": 1,
        "file": version_file_name(1, SHA),
        "sha256": SHA,
        "schema_version": 1,
        "reason": "build",
        "frames": 0,
        "persons": 0,
        "bytes": 1,
        "written_at": "2026-10-21T00:00:00Z",
    }
    assert VersionRecord.model_validate(record).parent is None
    with pytest.raises(ValidationError, match="its facts name it"):
        VersionRecord.model_validate(dict(record, version=2))
    with pytest.raises(ValidationError, match="its own parent"):
        VersionRecord.model_validate(dict(record, parent=SHA))


def item(person: str, level: str, sha: str, angle: float = 90.0) -> dict[str, object]:
    return {
        "path": frame_path(sha, "png"),
        "sha256": sha,
        "person": person,
        "modality": Modality.XA.value,
        "device": {"device_class": DeviceClass.MOBILE_C_ARM.value, "make": "Ziehm"},
        "exposure": {"kvp": 73.0, "mas": 2.5, "px_mm": 0.3},
        "lat_from_ap_deg": angle,
        "labels": [{"level": level, "box": [0.1, 0.1, 0.5, 0.5], "labeller": "cbct"}],
    }


def manifest(
    kind: str, items: list[dict[str, object]], supersedes: str | None = None
) -> dict[str, object]:
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
    item("carmlspine:case7", "L5", "a" * 64, 90.0),
    item("carmlspine:case7", "L4", "b" * 64, 0.0),
    item("carmlspine:case8", "L6", "c" * 64, 88.0),
]
TEST_ITEMS = [item("carmlspine:case42", "L6", "d" * 64, 91.0)]


def test_a_catalog_builds_from_manifests_and_answers_queries(tmp_path: Path) -> None:
    tool = load_tool()
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS))
    test = write(tmp_path, "test", manifest("test", TEST_ITEMS))
    review = write(tmp_path, "review", manifest("review", [TRAIN_ITEMS[2]]))
    store = tmp_path / "store"
    record, new = tool.build(
        store, [train, test, review], tool.load_inputs(), "0123abc", "2026-10-21"
    )
    path = store / "versions" / record.file
    assert new and record.version == 1 and record.parent is None
    assert record.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record.frames == 5 and record.persons == 3 and len(record.shards) == 3
    assert record.added_shards == record.shards and record.removed_shards == ()
    assert record.frames_by_source_and_part == {
        "carmlspine|test": 1,
        "carmlspine|train": 2,
        "carmlspine|validation": 2,
    }
    db = tool.open_catalog(store)
    lateral = tool.run_query(db, Query(views=(View.LATERAL,)))
    assert [(r["path"][:3], r["shard"][:16]) for r in lateral] == [
        ("aa/", "carmlspine/2026-"),
        ("cc/", "carmlspine/2026-"),
        ("cc/", "carmlspine/2026-"),
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


def test_a_version_is_read_only_and_the_store_never_holds_two_of_one_thing(tmp_path: Path) -> None:
    tool = load_tool()
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS))
    test = write(tmp_path, "test", manifest("test", TEST_ITEMS))
    store = tmp_path / "store"
    first, _ = tool.build(store, [train], tool.load_inputs())
    path = store / "versions" / first.file
    assert path.stat().st_mode & 0o777 == 0o444
    assert first.bytes == path.stat().st_size and first.written_at.endswith("Z")
    assert (
        tool.open_catalog(store).execute("PRAGMA application_id").fetchone()[0]
        == tool.APPLICATION_ID
    )
    assert (store / "CURRENT").read_text(encoding="utf-8") == first.file + "\n"
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        tool.open_catalog(store).execute("DELETE FROM item")
    again, new = tool.build(store, [train], tool.load_inputs())
    assert not new and again == first and len(tool.read_versions(store)) == 1
    second, new = tool.build(store, [train, test], tool.load_inputs())
    assert new and second.version == 2 and second.parent == first.sha256
    assert second.written_at >= first.written_at
    assert (
        second.added_shards == (manifest("test", TEST_ITEMS)["name"],)
        and second.removed_shards == ()
    )
    third, _ = tool.build(store, [test], tool.load_inputs())
    assert third.removed_shards == (manifest("train", TRAIN_ITEMS)["name"],) and third.frames == 1
    assert sorted(p.name for p in (store / "versions").iterdir()) == sorted(
        r.file for r in tool.read_versions(store)
    )
    assert tool.run_query(tool.open_catalog(store, 1), Query())[0]["person"] == "carmlspine:case7"
    assert tool.run_query(tool.open_catalog(path), Query()) == tool.run_query(
        tool.open_catalog(store, 1), Query()
    )
    assert tool.run_query(tool.open_catalog(store), Query()) == []
    with pytest.raises(tool.CatalogError, match="no version 9; the log holds 1 to 3"):
        tool.open_catalog(store, 9)
    (store / "VERSIONS.jsonl").write_text("not json\n", encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="line 1"):
        tool.read_versions(store)


def test_what_a_build_refuses_leaves_nothing_behind(tmp_path: Path) -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    old = manifest("train", TRAIN_ITEMS[:1])
    cases = {
        "test persons": manifest("train", TEST_ITEMS),
        "not a test person": manifest("test", TRAIN_ITEMS[:1]),
        "also loaded": manifest("train", TRAIN_ITEMS, supersedes=str(old["name"])),
    }
    store = tmp_path / "store"
    for message, data in cases.items():
        folder = tmp_path / message.replace(" ", "_")
        paths = [write(folder, "bad", data)]
        if message == "also loaded":
            paths.append(write(folder, "old", old))
        with pytest.raises(tool.CatalogError, match=message):
            tool.build(store, paths, inputs)
    with pytest.raises(tool.CatalogError, match="No such file"):
        tool.build(store, [tmp_path / "missing.json"], inputs)
    assert list((store / "versions").iterdir()) == [] and not (store / "VERSIONS.jsonl").exists()
    with pytest.raises(tool.CatalogError, match="no catalog there"):
        tool.open_catalog(store)


def test_embeddings_make_a_new_version_and_similar_never_ranks_a_test_frame(tmp_path: Path) -> None:
    tool = load_tool()
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS))
    test = write(tmp_path, "test", manifest("test", TEST_ITEMS))
    store = tmp_path / "store"
    before, _ = tool.build(store, [train, test], tool.load_inputs())
    vectors = tmp_path / "v.jsonl"
    rows = [
        ("a" * 64, [1.0, 0.0]),
        ("b" * 64, [0.0, 1.0]),
        ("c" * 64, [0.9, 0.1]),
        ("d" * 64, [1.0, 0.0]),
    ]
    vectors.write_text(
        "\n".join(json.dumps({"item": i, "vector": v}) for i, v in rows), encoding="utf-8"
    )
    loaded, (after, new) = tool.embed(store, "v1", vectors)
    assert loaded == 4 and new and after.version == 2 and after.parent == before.sha256
    assert after.embeddings_by_model == {"v1": 4} and after.shards == before.shards
    assert [p.name for p in (store / "versions").iterdir() if p.name.startswith(".")] == []
    db = tool.open_catalog(store)
    assert [r["item"] for r in tool.similar(db, "v1", "a" * 64, 1)] == ["c" * 64]
    with_test = tool.similar(db, "v1", "a" * 64, 1, (*DEFAULT_PARTS, Part.TEST))
    assert [r["item"] for r in with_test] == ["d" * 64]
    with pytest.raises(tool.CatalogError, match="no embedding"):
        tool.similar(db, "v2", "a" * 64, 1)
    with pytest.raises(tool.CatalogError, match="no embedding"):
        tool.similar(tool.open_catalog(store, 1), "v1", "a" * 64, 1)
    vectors.write_text(json.dumps({"item": "f" * 64, "vector": [1.0]}), encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="no frame of the catalog"):
        tool.embed(store, "v1", vectors)
    vectors.write_text(json.dumps({"item": "a" * 64, "vector": []}), encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="same length"):
        tool.embed(store, "v1", vectors)
    assert len(tool.read_versions(store)) == 2
    rebuilt, new = tool.build(store, [train, test], tool.load_inputs())
    assert (
        new
        and rebuilt.version == 3
        and rebuilt.parent == after.sha256
        and rebuilt.embeddings_by_model == {}
    )
    assert tool.main(["query", str(store), "--levels", "L5,L4", "--count", "--version", "2"]) == 0
    assert (
        tool.main(
            [
                "similar",
                str(store),
                "--version",
                "2",
                "--model",
                "v1",
                "--item",
                "a" * 64,
                "--k",
                "2",
            ]
        )
        == 0
    )


def test_the_command_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tool = load_tool()
    assert tool.main(["summary", str(tmp_path / "none")]) == 1
    assert "no catalog there" in capsys.readouterr().err
    assert tool.main(["versions", str(tmp_path / "none")]) == 1
    assert "no catalog there" in capsys.readouterr().err
    registered = len(list((ROOT / "data" / "registry").glob("*.json")))
    assert tool.main(["check"]) == 0
    assert f"registry: {registered} sources" in capsys.readouterr().out
    assert (
        tool.main(["part", " carmlspine:case42 "]) == 0
        and capsys.readouterr().out.strip() == "test"
    )
    assert tool.main(["schema"]) == 0 and "CREATE TABLE item" in capsys.readouterr().out
    assert tool.main(["build", "--store", str(tmp_path / "store")]) == 1
    assert "no manifest to read" in capsys.readouterr().err
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS))
    argv = [
        "build",
        "--store",
        str(tmp_path / "store"),
        "--manifest",
        str(train),
        "--as-of",
        "2026-10-21",
    ]
    assert tool.main(argv) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["new"] and first["version"] == 1 and first["frames"] == 3
    assert tool.main(argv) == 0 and json.loads(capsys.readouterr().out)["new"] is False
    assert tool.main(["versions", str(tmp_path / "store")]) == 0
    assert json.loads(capsys.readouterr().out)["as_of"] == "2026-10-21"
    assert tool.main(["summary", str(tmp_path / "store"), "--version", "9"]) == 1
    assert "no version 9" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        tool.main(["similar", "x", "--model", "v", "--item", "a", "--k", "-1"])


def test_a_frame_whose_bytes_sit_in_two_parts_is_refused_and_shows_in_the_check(
    tmp_path: Path,
) -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    train = write(tmp_path, "train", manifest("train", TRAIN_ITEMS[:2]))
    test = write(tmp_path, "test", manifest("test", [item("carmlspine:case42", "L5", "a" * 64)]))
    with pytest.raises(tool.CatalogError, match="two persons or in two parts"):
        tool.build(tmp_path / "store", [train, test], inputs)
    assert not (tmp_path / "store" / "VERSIONS.jsonl").exists()
    # The same bytes in a train shard and a review shard under one person is no leak.
    review = write(tmp_path, "review", manifest("review", TRAIN_ITEMS[:1]))
    assert tool.build(tmp_path / "store", [train, review], inputs)[0].frames == 3
    # On a catalog an older tool let through, the split check and similar both see the leak.
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    with pytest.raises(tool.CatalogError):
        tool.fill(db, [train, test], inputs, None)
    check = tool.split_check(db, inputs)
    assert check["frames_in_two_parts"] == ["a" * 64] and not check["disjoint"]
    assert check["persons_in_two_parts"] == []
    for sha, vector in [("a" * 64, [1.0, 0.0]), ("b" * 64, [0.9, 0.1])]:
        db.execute("INSERT INTO embedding VALUES (?, 'v1', 2, ?)", (sha, tool.pack(vector)))
    assert tool.similar(db, "v1", "b" * 64, 5) == []
    assert [
        r["item"] for r in tool.similar(db, "v1", "b" * 64, 5, (*DEFAULT_PARTS, Part.TEST))
    ] == ["a" * 64]


def test_a_write_holds_the_lock_and_a_store_that_moved_under_it_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    a = write(tmp_path, "a", manifest("train", TRAIN_ITEMS[:1]))
    b = write(tmp_path, "b", manifest("train", TRAIN_ITEMS[2:]))
    store = tmp_path / "store"
    taken: list[tuple[str, int]] = []
    real_lockf, real_describe = tool.fcntl.lockf, tool.describe

    def lockf(handle: object, operation: int) -> None:
        taken.append(("lock", operation))
        real_lockf(handle, operation)

    def describe(*args: object, **kw: object) -> object:
        taken.append(("describe", 0))
        return real_describe(*args, **kw)

    monkeypatch.setattr(tool.fcntl, "lockf", lockf)
    monkeypatch.setattr(tool, "describe", describe)
    first, _ = tool.build(store, [a], inputs)
    assert taken == [("lock", tool.fcntl.LOCK_EX), ("describe", 0), ("lock", tool.fcntl.LOCK_UN)]
    assert (store / "LOCK").is_file()
    # Another writer lands between this build's reading of the log and its sealing (a lock a
    # process never holds against itself): the build is dropped, not numbered twice.
    monkeypatch.setattr(tool, "describe", real_describe)

    def describe_after_another_landed(*args: object, **kw: object) -> object:
        monkeypatch.setattr(tool, "describe", real_describe)
        tool.build(store, [a, b], inputs)
        return real_describe(*args, **kw)

    monkeypatch.setattr(tool, "describe", describe_after_another_landed)
    with pytest.raises(tool.CatalogError, match="another build landed"):
        tool.build(store, [b], inputs)
    records = tool.read_versions(store)
    assert [r.version for r in records] == [1, 2] and records[1].parent == first.sha256
    assert [p.name for p in (store / "versions").iterdir() if p.name.startswith(".")] == []
    # An unchanged build leaves no staging file either, and never deletes another's.
    other = store / "versions" / ".building-someone-elses"
    other.write_text("still being written", encoding="utf-8")
    assert tool.build(store, [a, b], inputs)[1] is False
    assert [p.name for p in (store / "versions").iterdir() if p.name.startswith(".")] == [
        other.name
    ]


def test_a_replaced_file_a_forged_log_and_a_stale_current_are_refused(tmp_path: Path) -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    a = write(tmp_path, "a", manifest("train", TRAIN_ITEMS[:1]))
    store = tmp_path / "store"
    first, _ = tool.build(store, [a], inputs)
    second, _ = tool.build(store, [a], inputs, "abcdef0")
    log = store / "VERSIONS.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    # A line whose number or parent is not the line before it.
    forged = (
        lines[1].replace('"version":2', '"version":7').replace("catalog-000002", "catalog-000007")
    )
    log.write_text("\n".join([lines[0], forged]) + "\n", encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="line 2 is version 7"):
        tool.read_versions(store)
    log.write_text(
        "\n".join([lines[0], lines[1].replace(first.sha256, "0" * 64)]) + "\n", encoding="utf-8"
    )
    with pytest.raises(tool.CatalogError, match="parent is 0{64}, not the line before it"):
        tool.read_versions(store)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # CURRENT names a file the log's last line does not.
    (store / "CURRENT").write_text(first.file + "\n", encoding="utf-8")
    with pytest.raises(tool.CatalogError, match="but the log's last line is"):
        tool.open_catalog(store)
    (store / "CURRENT").write_text(second.file + "\n", encoding="utf-8")
    assert tool.open_catalog(store, 1).execute("SELECT COUNT(*) FROM item").fetchone()[0] == 1
    # The file replaced in place, as a person with a writable directory can: unlink and recreate.
    final = store / "versions" / second.file
    copy = tmp_path / "copy.sqlite"
    copy.write_bytes(final.read_bytes())
    db = sqlite3.connect(copy)
    db.execute("UPDATE item SET part = 'train'")
    db.commit()
    db.close()
    final.unlink()
    copy.rename(final)
    with pytest.raises(tool.CatalogError, match="not the .* it was sealed with"):
        tool.open_catalog(store)
    with pytest.raises(tool.CatalogError, match="it was sealed with"):
        tool.open_catalog(final)
    assert tool.open_catalog(store, 1).execute("SELECT COUNT(*) FROM item").fetchone()[0] == 1


def test_the_same_facts_give_the_same_bytes_whatever_order_or_directory_names_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = load_tool()
    inputs = tool.load_inputs()
    a = write(tmp_path, "a", manifest("train", TRAIN_ITEMS[:1]))
    b = write(tmp_path, "b", manifest("train", TRAIN_ITEMS[2:]))
    store = tmp_path / "a?b#c" / "store"
    first, _ = tool.build(store, [a, b], inputs)
    assert tool.build(store, [b, a], inputs)[1] is False
    monkeypatch.chdir(tmp_path)
    assert tool.build(store, [Path("b/MANIFEST.json"), Path("a/MANIFEST.json")], inputs)[1] is False
    db = tool.open_catalog(store)
    assert sorted(r[0] for r in db.execute("SELECT manifest FROM shard")) == [str(a), str(b)]
    assert len(tool.read_versions(store)) == 1


def test_a_vector_with_no_direction_is_refused_before_it_is_stored(tmp_path: Path) -> None:
    tool = load_tool()
    a = write(tmp_path, "a", manifest("train", TRAIN_ITEMS[:2]))
    store = tmp_path / "store"
    tool.build(store, [a], tool.load_inputs())
    vectors = tmp_path / "v.jsonl"
    cases = [
        ("no direction", [0.0, 0.0]),
        ("not a number", [1.0, float("nan")]),
        ("beyond float32", [1e39, 0.0]),
        ("no direction", [1e-50, 0.0]),
    ]
    for message, vector in cases:
        vectors.write_text(json.dumps({"item": "a" * 64, "vector": vector}), encoding="utf-8")
        with pytest.raises(tool.CatalogError, match=message):
            tool.embed(store, "v1", vectors)
    assert len(tool.read_versions(store)) == 1
    # A zero vector an older tool stored is named, never handed to the ranking rule.
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(tool.SCHEMA)
    db.execute("INSERT INTO embedding VALUES (?, 'v1', 2, ?)", ("a" * 64, tool.pack([0.0, 0.0])))
    with pytest.raises(tool.CatalogError, match="no direction for a{64}"):
        tool.similar(db, "v1", "a" * 64, 5)
