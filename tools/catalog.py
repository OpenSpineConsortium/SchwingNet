"""The frame catalog: build a SQLite index from the registry and the shard manifests, and query it.

docs/research/data-catalog.md is the design. The pure rules (the shapes, the split, the bands, the
query predicates, the cosine ranking) are schwingnet.catalog under beethoven-qa's gate; this script
is the reading and writing around them: it validates the files under data/registry/ and data/splits/,
reads each shard's MANIFEST.json, writes one SQLite file (the standard library's sqlite3, a plain
file on whatever volume holds it, which DuckDB and pandas open in place) and answers queries from
it. A Metaflow step calls these commands by path and passes the catalog's sha256 and a query's
answer on as artifacts. The images never enter the file: a row names a frame's shard, path and hash.
Every write makes a fresh file and renames it into place, so a reader never sees a half file and two
builds from the same inputs are the same bytes.

    pixi run --locked python tools/catalog.py check
    pixi run --locked python tools/catalog.py schema
    pixi run --locked python tools/catalog.py part carmlspine:case7
    pixi run --locked python tools/catalog.py build --out catalog.sqlite --manifest <dir>/MANIFEST.json ...
    pixi run --locked python tools/catalog.py query catalog.sqlite --levels L5,sacrum --views lateral
    pixi run --locked python tools/catalog.py embed catalog.sqlite --model v1 --vectors vectors.jsonl
    pixi run --locked python tools/catalog.py similar catalog.sqlite --model v1 --item <sha256> --k 24
    pixi run --locked python tools/catalog.py summary catalog.sqlite
    pixi run --locked python tools/catalog.py export catalog.sqlite --table item --out item.jsonl
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import struct
import sys
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "vendor" / "beethoven-qa" / "src"))

from schwingnet.catalog import (  # the path above makes the package importable
    DEFAULT_PARTS,
    DeviceClass,
    FrozenPerson,
    Modality,
    Part,
    Query,
    Region,
    RegistryEntry,
    ShardKind,
    ShardManifest,
    SplitRule,
    View,
    best,
    cosine,
    is_transitional,
    part_of,
    region_of,
    view_band,
    where_clause,
)

REGISTRY = ROOT / "data" / "registry"
TEST_PERSONS = ROOT / "data" / "splits" / "test-persons.json"
RULE = ROOT / "data" / "splits" / "rule.json"
CATALOG_SCHEMA = 1
TABLES = ("build", "source", "shard", "person", "item", "label", "embedding")

# What a build reads besides the manifests: the registry, the frozen test persons with the
# sha256 of their file, and the split rule with the sha256 of its file.
Inputs = namedtuple("Inputs", "registry test_persons rule test_persons_sha256 rule_sha256")

SCHEMA = """
CREATE TABLE build (
    schema_version INTEGER NOT NULL,
    code_commit TEXT,
    salt TEXT NOT NULL,
    validation_share REAL NOT NULL,
    test_persons_sha256 TEXT NOT NULL,
    rule_sha256 TEXT NOT NULL
);
CREATE TABLE source (
    source TEXT PRIMARY KEY,
    identity_level TEXT NOT NULL,
    modality TEXT NOT NULL,
    device_class TEXT NOT NULL,
    grid_root TEXT NOT NULL,
    access TEXT NOT NULL
);
CREATE TABLE shard (
    name TEXT PRIMARY KEY,
    source TEXT NOT NULL REFERENCES source(source),
    kind TEXT NOT NULL,
    ingest_date TEXT NOT NULL,
    code_commit TEXT NOT NULL,
    supersedes TEXT,
    manifest TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    item_count INTEGER NOT NULL
);
CREATE TABLE person (
    person TEXT PRIMARY KEY,
    source TEXT NOT NULL REFERENCES source(source),
    part TEXT NOT NULL,
    hash_hex TEXT NOT NULL,
    frame_count INTEGER NOT NULL
);
CREATE TABLE item (
    sha256 TEXT NOT NULL,
    shard TEXT NOT NULL REFERENCES shard(name),
    path TEXT NOT NULL,
    source TEXT NOT NULL,
    person TEXT NOT NULL REFERENCES person(person),
    part TEXT NOT NULL,
    modality TEXT NOT NULL,
    device_class TEXT NOT NULL,
    make TEXT,
    model TEXT,
    detector TEXT,
    kvp REAL,
    mas REAL,
    px_mm REAL,
    lat_from_ap_deg REAL,
    gantry_deg REAL,
    view TEXT,
    acquired TEXT,
    label_count INTEGER NOT NULL,
    PRIMARY KEY (shard, sha256)
);
CREATE TABLE label (
    item TEXT NOT NULL,
    shard TEXT NOT NULL,
    level TEXT NOT NULL,
    region TEXT NOT NULL,
    transitional INTEGER NOT NULL,
    x0 REAL NOT NULL, y0 REAL NOT NULL, x1 REAL NOT NULL, y1 REAL NOT NULL,
    labeller TEXT NOT NULL,
    FOREIGN KEY (shard, item) REFERENCES item(shard, sha256)
);
CREATE TABLE embedding (
    item TEXT NOT NULL,
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY (item, model)
);
CREATE INDEX item_sha256 ON item(sha256);
CREATE INDEX item_part ON item(part);
CREATE INDEX item_source ON item(source);
CREATE INDEX item_person ON item(person);
CREATE INDEX item_view ON item(view);
CREATE INDEX item_device ON item(device_class, modality);
CREATE INDEX item_kvp ON item(kvp);
CREATE INDEX label_item ON label(shard, item);
CREATE INDEX label_level ON label(level);
CREATE INDEX label_region ON label(region);
"""

ITEM_COLUMNS = (
    "sha256", "shard", "path", "source", "person", "part", "modality", "device_class", "make",
    "model", "detector", "kvp", "mas", "px_mm", "lat_from_ap_deg", "gantry_deg", "view",
    "acquired", "label_count",
)


class CatalogError(Exception):
    """A file or a manifest the catalog refuses, with the reason a person reads."""


def person_hash(salt, person):
    """The split hash of a person: the rule data/splits/rule.json states, in code."""
    text = f"schwingnet-split|{salt}|{person}".encode()
    return int.from_bytes(hashlib.sha256(text).digest()[:8], "big")


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except OSError as error:
        raise CatalogError(f"{path}: {error}") from error


def read_json(path):
    try:
        return json.loads(read_bytes(path))
    except ValueError as error:
        raise CatalogError(f"{path}: {error}") from error


def load_registry(folder=REGISTRY):
    """Every registry entry, validated; a file that does not hold together names itself."""
    entries = {}
    for path in sorted(Path(folder).glob("*.json")):
        try:
            entry = RegistryEntry.model_validate(read_json(path))
        except ValueError as error:
            raise CatalogError(f"{path}: {error}") from error
        if entry.source != path.stem:
            raise CatalogError(f"{path}: the file is named {path.stem} but the entry says {entry.source}")
        entries[entry.source] = entry
    return entries


def load_split(test_persons_path=TEST_PERSONS, rule_path=RULE):
    """The frozen test persons and the rule, validated, each with its file's sha256."""
    persons_bytes, rule_bytes = read_bytes(test_persons_path), read_bytes(rule_path)
    try:
        persons = tuple(FrozenPerson.model_validate(row) for row in json.loads(persons_bytes))
        rule = SplitRule.model_validate(json.loads(rule_bytes))
    except ValueError as error:
        raise CatalogError(f"{test_persons_path} or {rule_path}: {error}") from error
    names = [p.person for p in persons]
    if len(set(names)) != len(names):
        raise CatalogError(f"{test_persons_path}: a person is listed twice")
    digests = (hashlib.sha256(persons_bytes).hexdigest(), hashlib.sha256(rule_bytes).hexdigest())
    return frozenset(names), rule, digests


def load_inputs(folder=REGISTRY, test_persons_path=TEST_PERSONS, rule_path=RULE):
    """Everything a build reads besides the manifests, checked against each other."""
    registry = load_registry(folder)
    test_persons, rule, (persons_sha256, rule_sha256) = load_split(test_persons_path, rule_path)
    for person in sorted(test_persons):
        source = person.partition(":")[0]
        if source not in registry:
            raise CatalogError(f"{test_persons_path}: {person} names no registered source")
    return Inputs(registry, test_persons, rule, persons_sha256, rule_sha256)


def load_manifest(path):
    """One shard's MANIFEST.json, validated, with the sha256 of its bytes."""
    data = read_bytes(path)
    try:
        manifest = ShardManifest.model_validate(json.loads(data))
    except ValueError as error:
        raise CatalogError(f"{path}: {error}") from error
    return manifest, hashlib.sha256(data).hexdigest()


def person_part(person, test_persons, rule):
    hash_value = person_hash(rule.salt, person)
    return part_of(person, hash_value, rule.validation_share, test_persons), hash_value


def refuse_mixed_shard(manifest, path, test_persons):
    """A shard is one kind: a train or review shard that holds a frozen test person is refused."""
    if manifest.kind is ShardKind.TEST:
        return
    held = sorted({item.person for item in manifest.items} & test_persons)
    if held:
        raise CatalogError(f"{path}: a {manifest.kind.value} shard holds test persons {held}")


def refuse_superseded(loaded):
    """A build reads a shard or its successor, never both, so no frame is counted twice."""
    names = {manifest.name for _, manifest, _ in loaded}
    if len(names) != len(loaded):
        raise CatalogError("a shard is named twice among the manifests")
    for _, manifest, _ in loaded:
        if manifest.supersedes in names:
            raise CatalogError(f"{manifest.name} supersedes {manifest.supersedes}, which is also loaded")


def item_row(item, manifest, part):
    view = None if item.lat_from_ap_deg is None else view_band(item.lat_from_ap_deg).value
    return (
        item.sha256, manifest.name, item.path, manifest.source, item.person, part.value,
        item.modality.value, item.device.device_class.value, item.device.make, item.device.model,
        item.device.detector, item.exposure.kvp, item.exposure.mas, item.exposure.px_mm,
        item.lat_from_ap_deg, item.gantry_deg, view, item.acquired, len(item.labels),
    )


def label_rows(item, shard):
    for label in item.labels:
        yield (
            item.sha256, shard, label.level, region_of(label.level).value,
            int(is_transitional(label.level)), *label.box, label.labeller,
        )


def insert_shard(db, manifest, path, manifest_sha256):
    db.execute(
        "INSERT INTO shard VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            manifest.name, manifest.source, manifest.kind.value, manifest.ingest_date,
            manifest.code_commit, manifest.supersedes, str(path), manifest_sha256,
            len(manifest.items),
        ),
    )


def insert_persons(db, manifest, test_persons, rule):
    """Each person of the shard, with its part; a person seen in an earlier shard keeps its row."""
    parts = {}
    for item in manifest.items:
        part, hash_value = person_part(item.person, test_persons, rule)
        parts[item.person] = part
        db.execute(
            "INSERT INTO person VALUES (?, ?, ?, ?, 0) ON CONFLICT(person) DO NOTHING",
            (item.person, manifest.source, part.value, f"{hash_value:016x}"),
        )
        db.execute("UPDATE person SET frame_count = frame_count + 1 WHERE person = ?", (item.person,))
    return parts


def insert_items(db, manifest, parts):
    marks = ", ".join("?" for _ in ITEM_COLUMNS)
    for item in manifest.items:
        if manifest.kind is ShardKind.TEST and parts[item.person] is not Part.TEST:
            raise CatalogError(f"{manifest.name}: a test shard holds {item.person}, who is not a test person")
        db.execute(f"INSERT INTO item VALUES ({marks})", item_row(item, manifest, parts[item.person]))
        db.executemany("INSERT INTO label VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", label_rows(item, manifest.name))


def insert_sources(db, registry, needed):
    for source in sorted(needed):
        if source not in registry:
            raise CatalogError(f"a manifest names the source {source}, which has no registry entry")
        entry = registry[source]
        db.execute(
            "INSERT INTO source VALUES (?, ?, ?, ?, ?, ?)",
            (
                source, entry.identity_level.value, entry.modality.value, entry.device_class.value,
                entry.grid_root, entry.access,
            ),
        )


def manifest_paths(registry, named, root):
    """The manifests to read: those named on the command line, else every one the registry lists."""
    if named:
        return [Path(p) for p in named]
    paths = []
    for entry in registry.values():
        for shard in entry.shards:
            if shard.superseded_by is None:
                paths.append(Path(root) / shard.manifest if root else Path(shard.manifest))
    return paths


def write_fresh(out, writer):
    """Write a file beside `out` through `writer(path)`, then rename it into place; on a refusal
    nothing is left behind. Returns the sha256 of the file in place."""
    fresh = Path(str(out) + ".building")
    fresh.unlink(missing_ok=True)
    try:
        writer(fresh)
    except BaseException:
        fresh.unlink(missing_ok=True)
        raise
    os.replace(fresh, out)
    return hashlib.sha256(Path(out).read_bytes()).hexdigest()


def build(out, manifests, inputs, code_commit=None):
    """The catalog from the manifests and the inputs, as one fresh file."""
    def writer(fresh):
        db = sqlite3.connect(fresh)
        try:
            fill(db, manifests, inputs, code_commit)
            db.commit()
        finally:
            db.close()
    return write_fresh(out, writer)


def fill(db, manifests, inputs, code_commit):
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO build VALUES (?, ?, ?, ?, ?, ?)",
        (CATALOG_SCHEMA, code_commit, inputs.rule.salt, inputs.rule.validation_share,
         inputs.test_persons_sha256, inputs.rule_sha256),
    )
    loaded = [(path, *load_manifest(path)) for path in manifests]
    refuse_superseded(loaded)
    insert_sources(db, inputs.registry, {manifest.source for _, manifest, _ in loaded})
    for path, manifest, manifest_sha256 in loaded:
        refuse_mixed_shard(manifest, path, inputs.test_persons)
        insert_shard(db, manifest, path, manifest_sha256)
        parts = insert_persons(db, manifest, inputs.test_persons, inputs.rule)
        insert_items(db, manifest, parts)


def open_catalog(path):
    if not Path(path).is_file():
        raise CatalogError(f"{path}: no catalog there; build one first")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def split_list(text, kind=None):
    values = tuple(v for v in (text or "").split(",") if v)
    try:
        return tuple(kind(v) for v in values) if kind else values
    except ValueError as error:
        raise CatalogError(str(error)) from error


def query_from_args(args):
    return Query(
        levels=split_list(args.levels),
        regions=split_list(args.regions, Region),
        views=split_list(args.views, View),
        modalities=split_list(args.modalities, Modality),
        device_classes=split_list(args.device_classes, DeviceClass),
        sources=split_list(args.sources),
        parts=split_list(args.parts, Part),
        persons=split_list(args.persons),
        shards=split_list(args.shards),
        kvp_band=args.kvp_band,
        kvp_band_width=args.kvp_band_width,
        labelled_only=args.labelled_only,
    )


def run_query(db, query):
    """The frames a query names, each once per shard, with shard, path, hash, person and part."""
    clause, params = where_clause(query)
    sql = (
        "SELECT DISTINCT item.sha256, item.shard, item.path, item.person, item.part, item.source,"
        " item.modality, item.device_class, item.view, item.kvp FROM item"
        " LEFT JOIN label ON label.item = item.sha256 AND label.shard = item.shard"
        + clause + " ORDER BY item.shard, item.path"
    )
    return [dict(row) for row in db.execute(sql, params)]


def pack(vector):
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack(blob, dim):
    if len(blob) != 4 * dim:
        raise CatalogError(f"an embedding of dim {dim} holds {len(blob)} bytes, not {4 * dim}")
    return struct.unpack(f"<{dim}f", blob)


def read_vectors(path):
    """JSONL lines {"item": sha256, "vector": [...]}, every vector of one length, none empty."""
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        row = json.loads(line)
        vector = [float(x) for x in row["vector"]]
        if not vector or (rows and len(vector) != len(rows[0][1])):
            raise CatalogError(f"{path}: line {number}: every vector has the same length, above zero")
        rows.append((str(row["item"]), vector))
    return rows


def embed(catalog, model, vectors_path):
    """Load one model's embeddings into a fresh copy of the catalog and rename it into place."""
    rows = read_vectors(vectors_path)

    def writer(fresh):
        shutil.copyfile(catalog, fresh)
        db = sqlite3.connect(fresh)
        try:
            known = {r[0] for r in db.execute("SELECT DISTINCT sha256 FROM item")}
            for item, vector in rows:
                if item not in known:
                    raise CatalogError(f"{item} is no frame of the catalog")
                db.execute("INSERT OR REPLACE INTO embedding VALUES (?, ?, ?, ?)",
                           (item, model, len(vector), pack(vector)))
            db.commit()
        finally:
            db.close()

    return len(rows), write_fresh(catalog, writer)


def similar(db, model, item, k, parts=DEFAULT_PARTS):
    """The k frames nearest `item` in `model`'s embedding space, by cosine, best first.

    Only frames of the named parts are ranked (never the test set unless asked), so a
    selection fed by this answer cannot carry a test frame into training.
    """
    marks = ", ".join("?" for _ in parts)
    rows = db.execute(
        "SELECT DISTINCT embedding.item, dim, vector FROM embedding JOIN item ON item.sha256 = embedding.item"
        f" WHERE embedding.model = ? AND item.part IN ({marks})", (model, *(p.value for p in parts)),
    ).fetchall()
    anchor = db.execute("SELECT dim, vector FROM embedding WHERE model = ? AND item = ?", (model, item)).fetchone()
    if anchor is None:
        raise CatalogError(f"{item} has no embedding under model {model}")
    reference = unpack(anchor["vector"], anchor["dim"])
    vectors = {row["item"]: unpack(row["vector"], row["dim"]) for row in rows if row["item"] != item}
    if any(len(v) != len(reference) for v in vectors.values()):
        raise CatalogError(f"model {model} holds embeddings of more than one length")
    scored = tuple((other, cosine(reference, vector)) for other, vector in vectors.items())
    scores = dict(scored)
    return [{"item": other, "cosine": scores[other]} for other in best(scored, k)]


def summary(db):
    """Counts per source and part, per level and part, and the test persons: the numbers a result row carries."""
    by_part = db.execute(
        "SELECT source, part, COUNT(*) AS frames, COUNT(DISTINCT person) AS persons"
        " FROM item GROUP BY source, part ORDER BY source, part"
    ).fetchall()
    by_level = db.execute(
        "SELECT label.level, item.part, COUNT(*) AS boxes FROM label"
        " JOIN item ON item.sha256 = label.item AND item.shard = label.shard"
        " GROUP BY label.level, item.part ORDER BY label.level, item.part"
    ).fetchall()
    test = db.execute("SELECT person, frame_count FROM person WHERE part = 'test' ORDER BY person").fetchall()
    return {
        "by_source_and_part": [dict(r) for r in by_part],
        "by_level_and_part": [dict(r) for r in by_level],
        "test_persons": [dict(r) for r in test],
    }


def export(db, table, out):
    """One table as JSONL, for a notebook or a Parquet conversion where pyarrow is present."""
    if table not in TABLES:
        raise CatalogError(f"{table} is not a table of the catalog")
    with Path(out).open("w", encoding="utf-8") as handle:
        count = 0
        for row in db.execute(f"SELECT * FROM {table}"):
            handle.write(json.dumps({k: v for k, v in dict(row).items() if not isinstance(v, bytes)},
                                    sort_keys=True) + "\n")
            count += 1
    return count


def positive(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("a whole number above zero")
    return value


def count(text):
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("a count is not negative")
    return value


def add_query_arguments(parser):
    for name in ("levels", "regions", "views", "modalities", "device-classes", "sources", "parts",
                 "persons", "shards"):
        parser.add_argument(f"--{name}", default="", help="comma-separated")
    parser.add_argument("--kvp-band", type=int, default=None)
    parser.add_argument("--kvp-band-width", type=positive, default=10)
    parser.add_argument("--labelled-only", action="store_true")
    parser.add_argument("--count", action="store_true", help="print the count alone")


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate the registry and the split files")
    sub.add_parser("schema", help="print the catalog's SQL")
    sub.add_parser("part", help="where a person's frames go under the split rule").add_argument("person")
    build_p = sub.add_parser("build", help="build the catalog from the manifests")
    build_p.add_argument("--out", required=True)
    build_p.add_argument("--manifest", action="append", default=[])
    build_p.add_argument("--root", default="", help="where the registry's manifest paths start")
    build_p.add_argument("--code-commit", default=None)
    for name in ("query", "similar", "summary", "export", "embed"):
        sub.add_parser(name).add_argument("catalog")
    add_query_arguments(sub.choices["query"])
    sub.choices["similar"].add_argument("--model", required=True)
    sub.choices["similar"].add_argument("--item", required=True)
    sub.choices["similar"].add_argument("--k", type=count, default=24)
    sub.choices["similar"].add_argument("--parts", default="", help="comma-separated; train,validation unless named")
    sub.choices["export"].add_argument("--table", required=True)
    sub.choices["export"].add_argument("--out", required=True)
    sub.choices["embed"].add_argument("--model", required=True)
    sub.choices["embed"].add_argument("--vectors", required=True)
    return top


def command_check(args):
    inputs = load_inputs()
    print(f"registry: {len(inputs.registry)} sources; test persons: {len(inputs.test_persons)};"
          f" validation share: {inputs.rule.validation_share}")
    return 0


def command_part(args):
    inputs = load_inputs()
    part, _ = person_part(args.person.strip(), inputs.test_persons, inputs.rule)
    print(part.value)
    return 0


def command_build(args):
    inputs = load_inputs()
    manifests = manifest_paths(inputs.registry, args.manifest, args.root)
    if not manifests:
        raise CatalogError("no manifest to read: name one with --manifest, or register a shard")
    digest = build(args.out, manifests, inputs, args.code_commit)
    print(json.dumps({"catalog": str(args.out), "sha256": digest, "manifests": len(manifests)}))
    return 0


def command_query(args):
    rows = run_query(open_catalog(args.catalog), query_from_args(args))
    if args.count:
        print(len(rows))
    else:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    return 0


def command_embed(args):
    open_catalog(args.catalog).close()
    loaded, digest = embed(args.catalog, args.model, args.vectors)
    print(json.dumps({"model": args.model, "vectors": loaded, "sha256": digest}))
    return 0


def command_read(args):
    db = open_catalog(args.catalog)
    if args.command == "similar":
        result = similar(db, args.model, args.item, args.k, split_list(args.parts, Part) or DEFAULT_PARTS)
    elif args.command == "summary":
        result = summary(db)
    else:
        result = {"table": args.table, "rows": export(db, args.table, args.out), "out": args.out}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


HANDLERS = {"check": command_check, "part": command_part, "build": command_build,
            "query": command_query, "embed": command_embed}


def main(argv=None):
    args = parser().parse_args(argv)
    if args.command == "schema":
        print(SCHEMA.strip())
        return 0
    try:
        return HANDLERS.get(args.command, command_read)(args)
    except CatalogError as error:
        print(f"catalog: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
