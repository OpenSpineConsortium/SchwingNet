"""The frame catalog: build read-only, versioned SQLite indexes from the registry and the shard
manifests, and query them.

docs/research/data-catalog.md is the design. The pure rules (the shapes, the split, the bands, the
query predicates, the cosine ranking, the layout and the version names) are schwingnet.catalog under
beethoven-qa's gate; this script is the reading and writing around them: it validates the files
under data/registry/ and data/splits/, reads each shard's MANIFEST.json, writes one SQLite file per
version (the standard library's sqlite3, a plain file on whatever volume holds it, which DuckDB and
pandas open in place) and answers queries from it. A Metaflow step calls these commands by path and
passes the version's sha256 and a query's answer on as artifacts. The images never enter the file: a
row names a frame's shard, path and hash.

A catalog is a store, one directory: `versions/` holds every version ever built, each a file named
by its number and its content hash and made read-only the moment it is complete; `VERSIONS.jsonl`
is the append-only log, one line per version with its parent and its accounting; `CURRENT` names
the latest. Nothing is rewritten: a build or an embedding load that changes anything is a new
version, one that changes nothing is reported and leaves the store as it was, and a reader opens a
version with SQLite's read-only, immutable flags, so it can neither write nor lock it.

    pixi run --locked python tools/catalog.py check
    pixi run --locked python tools/catalog.py schema
    pixi run --locked python tools/catalog.py part carmlspine:case7
    pixi run --locked python tools/catalog.py build --store <dir> --manifest <shard>/MANIFEST.json ...
    pixi run --locked python tools/catalog.py versions <dir>
    pixi run --locked python tools/catalog.py query <dir> --levels L5,sacrum --views lateral
    pixi run --locked python tools/catalog.py embed <dir> --model v1 --vectors vectors.jsonl
    pixi run --locked python tools/catalog.py similar <dir> --model v1 --item <sha256> --k 24
    pixi run --locked python tools/catalog.py summary <dir> --version 3
    pixi run --locked python tools/catalog.py split-check <dir>
    pixi run --locked python tools/catalog.py export <dir> --table item --out item.jsonl
"""

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path
from urllib.parse import quote

from pydantic import ValidationError

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
    VersionRecord,
    View,
    best,
    changed_keys,
    cosine,
    is_transitional,
    part_of,
    region_of,
    shard_folder,
    version_file_name,
    view_band,
    where_clause,
)

REGISTRY = ROOT / "data" / "registry"
TEST_PERSONS = ROOT / "data" / "splits" / "test-persons.json"
RULE = ROOT / "data" / "splits" / "rule.json"
CATALOG_SCHEMA = 1
# PRAGMA application_id of every version file: "SCWN", so `file` and SQLite's own tools name it.
APPLICATION_ID = 0x5343574E
TABLES = ("build", "source", "shard", "person", "item", "label", "embedding")
VERSIONS_DIR = "versions"
VERSIONS_LOG = "VERSIONS.jsonl"
CURRENT = "CURRENT"
# The one writer at a time: a POSIX record lock on this file, held for the whole of a write.
LOCK = "LOCK"
VERSION_FILE = re.compile(r"^catalog-\d{6}-(?P<hash>[0-9a-f]{12})\.sqlite$")

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
    """Every registry entry, keyed by source, in alphabetical order; the layout rules hold."""
    registry = {}
    for path in sorted(Path(folder).glob("*.json")):
        try:
            entry = RegistryEntry.model_validate(read_json(path))
        except ValidationError as error:
            raise CatalogError(f"{path}: {error}") from error
        if path.stem != entry.source:
            raise CatalogError(f"{path}: the file is named {path.stem} but the source is {entry.source}")
        refuse_misplaced_shards(entry, path)
        registry[entry.source] = entry
    return registry


def refuse_misplaced_shards(entry, path):
    """A source's grid_root is the folder named by its id, and a shard's manifest is at
    `<grid_root>/shards/<shard>/MANIFEST.json` and nowhere else, so a new dataset is one folder
    in one place, the data root lists its sources alphabetically, and the tree reads from the
    catalog."""
    if not entry.grid_root.endswith("/" + entry.source):
        raise CatalogError(f"{path}: grid_root {entry.grid_root} is not the folder {entry.source}")
    for shard in entry.shards:
        expected = shard_folder(entry.grid_root, shard.name) + "/MANIFEST.json"
        if shard.manifest != expected:
            raise CatalogError(f"{path}: shard {shard.name} names its manifest {shard.manifest},"
                               f" but the layout puts it at {expected}")


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


def without_superseded(paths):
    """The named manifests less every one that another of them supersedes, so a stage that
    names every manifest under the data root reads each source's chain at its head alone; the
    build's own check still refuses a pair the caller named on purpose."""
    read = [(Path(p), json.loads(read_bytes(p))) for p in paths]
    superseded = {data.get("supersedes") for _, data in read if data.get("supersedes")}
    return [path for path, data in read if data.get("name") not in superseded]


def manifest_paths(registry, named, root, drop_superseded=False):
    """The manifests to read: those named on the command line, else every one the registry lists."""
    if named:
        return without_superseded(named) if drop_superseded else [Path(p) for p in named]
    paths = []
    for entry in registry.values():
        for shard in entry.shards:
            if shard.superseded_by is None:
                paths.append(Path(root) / shard.manifest if root else Path(shard.manifest))
    return paths


def store_paths(store):
    store = Path(store)
    return store / VERSIONS_DIR, store / VERSIONS_LOG, store / CURRENT


def read_versions(store):
    """The version log, oldest first, each line held to its shape and to the chain: line N is
    version N and its parent is line N-1's hash, so a line forged, dropped or written twice by a
    build that lost a race is refused, never served."""
    _, log, _ = store_paths(store)
    if not log.is_file():
        return []
    records = []
    for number, line in enumerate(log.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = VersionRecord.model_validate(json.loads(line))
        except (ValueError, ValidationError) as error:
            raise CatalogError(f"{log}: line {number}: {error}") from error
        refuse_broken_chain(log, number, record, records[-1] if records else None)
        records.append(record)
    return records


def refuse_broken_chain(log, number, record, previous):
    if record.version != number:
        raise CatalogError(f"{log}: line {number} is version {record.version}; the log counts 1, 2, 3")
    parent = previous.sha256 if previous else None
    if record.parent != parent:
        raise CatalogError(f"{log}: line {number}: version {number}'s parent is {record.parent},"
                           f" not the line before it ({parent})")


def check_current(store, records):
    """CURRENT names the log's last line, or the store was left half written or edited by hand."""
    _, _, current = store_paths(store)
    try:
        named = current.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise CatalogError(f"{current}: {error}") from error
    if named != records[-1].file:
        raise CatalogError(f"{current} names {named}, but the log's last line is {records[-1].file}")


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def refuse_changed_file(path, sha256):
    """The bytes are what the record says, or the file was replaced since it was sealed: the mode
    0444 stops nothing on a directory its owner may write, so the hash is the check."""
    found = file_sha256(path)
    if not found.startswith(sha256):
        raise CatalogError(f"{path}: its sha256 is {found}, not the {sha256} it was sealed with")


def version_path(store, version=None):
    """The file of one version: the latest unless a number is named, with its bytes checked."""
    records = read_versions(store)
    if not records:
        raise CatalogError(f"{store}: no catalog there; build one first")
    check_current(store, records)
    wanted = records[-1] if version is None else next((r for r in records if r.version == version), None)
    if wanted is None:
        raise CatalogError(f"{store}: no version {version}; the log holds 1 to {records[-1].version}")
    path = store_paths(store)[0] / wanted.file
    if not path.is_file():
        raise CatalogError(f"{path}: the log names it but it is not there")
    refuse_changed_file(path, wanted.sha256)
    return path, wanted


def accounting(db):
    """What a version holds, as the numbers its log line carries."""
    counts = summary(db)
    shards = tuple(r[0] for r in db.execute("SELECT name FROM shard ORDER BY name"))
    frames = db.execute("SELECT COUNT(*) FROM item").fetchone()[0]
    persons = db.execute("SELECT COUNT(*) FROM person").fetchone()[0]
    models = db.execute("SELECT model, COUNT(*) FROM embedding GROUP BY model ORDER BY model").fetchall()
    by_source_and_part = {f"{r['source']}|{r['part']}": r["frames"] for r in counts["by_source_and_part"]}
    return {"shards": shards, "frames": frames, "persons": persons,
            "frames_by_source_and_part": by_source_and_part,
            "embeddings_by_model": {m: n for m, n in models}}


def file_uri(path, flags):
    """A SQLite URI for a path: quoted, so a `?` or a `#` in a folder's name is part of the path
    and not the start of the flags."""
    return f"file:{quote(str(path))}?{flags}"


def describe(fresh, number, digest, parent, reason, code_commit, as_of):
    """The log line of a version just written, with what it adds to and drops from its parent."""
    db = sqlite3.connect(file_uri(fresh, "mode=ro"), uri=True)
    db.row_factory = sqlite3.Row
    try:
        facts = accounting(db)
        schema_version = db.execute("SELECT schema_version FROM build").fetchone()[0]
    finally:
        db.close()
    before = frozenset(parent.shards) if parent else frozenset()
    added, removed = changed_keys(before, frozenset(facts["shards"]))
    return VersionRecord(
        version=number, file=version_file_name(number, digest), sha256=digest,
        parent=parent.sha256 if parent else None, schema_version=schema_version,
        code_commit=code_commit, as_of=as_of, written_at=written_at(parent), reason=reason,
        bytes=Path(fresh).stat().st_size, added_shards=added, removed_shards=removed, **facts,
    )


def written_at(parent):
    """The clock, as a UTC second, never earlier than the parent's: the log reads in order
    even across machines whose clocks disagree."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return max(now, parent.written_at) if parent else now


@contextlib.contextmanager
def store_lock(store):
    """One writer at a time: an exclusive POSIX record lock on `<store>/LOCK`, held from the
    reading of the log to the writing of CURRENT, so two builds at once cannot both number
    themselves from one reading of the log. The lock reaches every machine that mounts the
    volume where the filesystem honours fcntl, as CephFS does through its metadata server."""
    with (Path(store) / LOCK).open("a") as handle:
        fcntl.lockf(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.lockf(handle, fcntl.LOCK_UN)


def write_version(store, writer, reason, code_commit=None, as_of=None):
    """Write a new version through `writer(path)` and record it; a version whose bytes the
    latest already has is dropped and the latest returned, so the store never holds two of
    one thing. Returns the record and whether it is new."""
    folder, log, current = store_paths(store)
    folder.mkdir(parents=True, exist_ok=True)
    with store_lock(store):
        records = read_versions(store)
        latest = records[-1] if records else None
        fresh = staging_file(folder)
        try:
            writer(fresh)
            digest = file_sha256(fresh)
            if latest is not None and latest.sha256 == digest:
                return latest, False
            record = describe(fresh, len(records) + 1, digest, latest, reason, code_commit, as_of)
            refuse_moved_store(store, records)
            seal(fresh, folder / record.file)
        finally:
            fresh.unlink(missing_ok=True)
        append_record(log, current, record)
    return record, True


def staging_file(folder):
    """A name of this build's own, made by the system: a name built from the pid could be an
    older run's file still being written, which must never be deleted or written over."""
    handle, name = tempfile.mkstemp(dir=folder, prefix=".building-")
    os.close(handle)
    return Path(name)


def refuse_moved_store(store, records):
    """The log is as it was read when the version was numbered, or another writer got past the
    lock (a lock a process cannot hold against itself, or a volume that honours none): the
    version is dropped rather than numbered twice."""
    if read_versions(store) != records:
        raise CatalogError(f"{store}: another build landed while this one was written; build again")


def append_record(log, current, record):
    with log.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json(exclude_none=True) + "\n")
    point = current.with_name(current.name + ".new")
    point.write_text(record.file + "\n", encoding="utf-8")
    os.replace(point, current)


def seal(fresh, final):
    """Move a complete version into place and make it read-only: nothing writes it again."""
    if final.exists():
        raise CatalogError(f"{final}: a file of that name is already there")
    os.chmod(fresh, 0o444)
    os.replace(fresh, final)


def build(store, manifests, inputs, code_commit=None, as_of=None):
    """A new version of the catalog from the manifests and the inputs."""
    def writer(fresh):
        db = sqlite3.connect(fresh)
        try:
            fill(db, manifests, inputs, code_commit)
            db.commit()
            stamp(db)
        finally:
            db.close()
    return write_version(store, writer, "build", code_commit, as_of)


def stamp(db):
    """Mark the file as a catalog and pack it: the same facts give the same bytes."""
    db.execute(f"PRAGMA application_id = {APPLICATION_ID}")
    db.execute(f"PRAGMA user_version = {CATALOG_SCHEMA}")
    db.commit()
    db.execute("VACUUM")


def fill(db, manifests, inputs, code_commit):
    db.executescript(SCHEMA)
    db.execute(
        "INSERT INTO build VALUES (?, ?, ?, ?, ?, ?)",
        (CATALOG_SCHEMA, code_commit, inputs.rule.salt, inputs.rule.validation_share,
         inputs.test_persons_sha256, inputs.rule_sha256),
    )
    # The manifests go in by shard name and by their resolved paths, so the order they were named
    # in and the directory they were named from change no byte of the file: the same facts give
    # the same hash, which is what the dedupe against the latest version compares. That dedupe
    # looks at the latest alone, on purpose: a build equal to an older version is still a new
    # version, since the log reads as a line of time and a step names what it read by number.
    loaded = sorted(((Path(path).resolve(), *load_manifest(path)) for path in manifests),
                    key=lambda entry: entry[1].name)
    refuse_superseded(loaded)
    insert_sources(db, inputs.registry, {manifest.source for _, manifest, _ in loaded})
    for path, manifest, manifest_sha256 in loaded:
        refuse_mixed_shard(manifest, path, inputs.test_persons)
        insert_shard(db, manifest, path, manifest_sha256)
        parts = insert_persons(db, manifest, inputs.test_persons, inputs.rule)
        insert_items(db, manifest, parts)
    refuse_frames_in_two_places(db)


def refuse_frames_in_two_places(db):
    """One frame's bytes sit under one person and in one part, whichever shards hold them: the
    item table is keyed by shard and hash, so the same bytes may be in a train shard and a
    review shard, but a frame that is one person's in one shard and another's in another, or in
    the test part here and the training part there, would leak at the byte level and pass a
    check that reads persons alone."""
    rows = db.execute(
        "SELECT sha256, GROUP_CONCAT(DISTINCT person), GROUP_CONCAT(DISTINCT part) FROM item"
        " GROUP BY sha256 HAVING COUNT(DISTINCT person) > 1 OR COUNT(DISTINCT part) > 1"
        " ORDER BY sha256 LIMIT 5"
    ).fetchall()
    if rows:
        found = "; ".join(f"{sha}: persons {persons}, parts {parts}" for sha, persons, parts in rows)
        raise CatalogError(f"a frame's bytes sit under two persons or in two parts: {found}")


def open_catalog(path, version=None):
    """A version, read-only and immutable: a store's latest, one of its versions by number, or
    one version file by path. The immutable flag tells SQLite the file cannot change under it,
    so it takes no lock, which a network filesystem may not honour, and never writes."""
    path = Path(path)
    if path.is_dir():
        path, _ = version_path(path, version)
    elif not path.is_file():
        raise CatalogError(f"{path}: no catalog there; build one first")
    elif VERSION_FILE.match(path.name):
        # A version file named alone has no log line to check against, but its name carries the
        # start of its hash, which a replaced file does not have.
        refuse_changed_file(path, VERSION_FILE.match(path.name)["hash"])
    db = sqlite3.connect(file_uri(path, "mode=ro&immutable=1"), uri=True)
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


def stored_vector(row, model):
    """An embedding read back with a direction, or a row an older tool loaded unchecked."""
    vector = unpack(row["vector"], row["dim"])
    if not any(vector) or not all(math.isfinite(x) for x in vector):
        raise CatalogError(f"model {model} holds a vector with no direction for {row['item']}")
    return vector


def read_vectors(path):
    """JSONL lines {"item": sha256, "vector": [...]}, every vector of one length, none empty, each
    with a direction: finite, within float32, not all zero, as the embedding table holds it."""
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        row = json.loads(line)
        vector = [float(x) for x in row["vector"]]
        if not vector or (rows and len(vector) != len(rows[0][1])):
            raise CatalogError(f"{path}: line {number}: every vector has the same length, above zero")
        rows.append((str(row["item"]), as_stored(vector, f"{path}: line {number}")))
    return rows


def as_stored(vector, where):
    """A vector as the table keeps it, float32, and refused where cosine is undefined on it: a
    component that is not a number, one beyond float32, or a vector that packs to all zeros."""
    if not all(math.isfinite(x) for x in vector):
        raise CatalogError(f"{where}: a vector holds a value that is not a number")
    try:
        stored = list(unpack(pack(vector), len(vector)))
    except OverflowError as error:
        raise CatalogError(f"{where}: a component is beyond float32") from error
    if not any(stored):
        raise CatalogError(f"{where}: a vector of zeros has no direction")
    return stored


def embed(store, model, vectors_path, code_commit=None, as_of=None):
    """Load one model's embeddings into a new version whose parent is the latest."""
    rows = read_vectors(vectors_path)

    def writer(fresh):
        # The parent is resolved inside the write, under the store's lock, so it is the version
        # the new one is recorded as the child of.
        source, _ = version_path(store)
        shutil.copyfile(source, fresh)
        os.chmod(fresh, 0o644)
        db = sqlite3.connect(fresh)
        try:
            known = {r[0] for r in db.execute("SELECT DISTINCT sha256 FROM item")}
            for item, vector in rows:
                if item not in known:
                    raise CatalogError(f"{item} is no frame of the catalog")
                db.execute("INSERT OR REPLACE INTO embedding VALUES (?, ?, ?, ?)",
                           (item, model, len(vector), pack(vector)))
            db.commit()
            stamp(db)
        finally:
            db.close()

    return len(rows), write_version(store, writer, f"embed {model}", code_commit, as_of)


def similar(db, model, item, k, parts=DEFAULT_PARTS):
    """The k frames nearest `item` in `model`'s embedding space, by cosine, best first.

    Only frames of the named parts are ranked (never the test set unless asked), so a
    selection fed by this answer cannot carry a test frame into training.
    """
    marks = ", ".join("?" for _ in parts)
    names = tuple(p.value for p in parts)
    # A frame whose bytes also sit in a part outside those asked for is left out, however the
    # row in an asked-for part names it: the bytes are what a selection carries into training.
    rows = db.execute(
        "SELECT DISTINCT embedding.item, dim, vector FROM embedding JOIN item ON item.sha256 = embedding.item"
        f" WHERE embedding.model = ? AND item.part IN ({marks}) AND NOT EXISTS"
        f" (SELECT 1 FROM item AS other WHERE other.sha256 = item.sha256 AND other.part NOT IN ({marks}))",
        (model, *names, *names),
    ).fetchall()
    anchor = db.execute("SELECT item, dim, vector FROM embedding WHERE model = ? AND item = ?", (model, item)).fetchone()
    if anchor is None:
        raise CatalogError(f"{item} has no embedding under model {model}")
    reference = stored_vector(anchor, model)
    vectors = {row["item"]: stored_vector(row, model) for row in rows if row["item"] != item}
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


def split_check(db, inputs):
    """The REFORMS split check over one version: no person in two parts, no frame's bytes in two
    parts, every test person frozen and every frozen person present held out, counted per source
    at its identity level.

    The answer is a record a result row cites: the counts per part, the four lists that must be
    empty, and a verdict; beethoven-research's splits.disjoint is the same rule over groups, and
    this is it over the catalog's own person table, before any training step reads a frame.
    """
    levels = {r["source"]: r["identity_level"] for r in db.execute("SELECT source, identity_level FROM source")}
    in_two_parts = [r[0] for r in db.execute(
        "SELECT person FROM item GROUP BY person HAVING COUNT(DISTINCT part) > 1 ORDER BY person")]
    # The same bytes in two parts under two persons: a leak the person table alone never shows.
    frames_in_two_parts = [r[0] for r in db.execute(
        "SELECT sha256 FROM item GROUP BY sha256 HAVING COUNT(DISTINCT part) > 1 ORDER BY sha256")]
    test_rows = db.execute("SELECT person FROM person WHERE part = 'test' ORDER BY person").fetchall()
    not_frozen = [r[0] for r in test_rows if r[0] not in inputs.test_persons]
    marks = ", ".join("?" for _ in inputs.test_persons) or "''"
    leaked = [r[0] for r in db.execute(
        f"SELECT person FROM person WHERE part != 'test' AND person IN ({marks}) ORDER BY person",
        tuple(sorted(inputs.test_persons)))]
    per_source = {}
    for row in db.execute("SELECT source, part, COUNT(DISTINCT person) AS persons, COUNT(*) AS frames"
                          " FROM item GROUP BY source, part ORDER BY source, part"):
        per_source.setdefault(row["source"], {"identity_level": levels[row["source"]], "parts": {}})
        per_source[row["source"]]["parts"][row["part"]] = {"persons": row["persons"], "frames": row["frames"]}
    return {"per_source": per_source, "persons_in_two_parts": in_two_parts,
            "frames_in_two_parts": frames_in_two_parts,
            "test_persons_not_frozen": not_frozen, "frozen_persons_not_held_out": leaked,
            "disjoint": not (in_two_parts or frames_in_two_parts or not_frozen or leaked)}


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


def add_version_arguments(parser):
    parser.add_argument("--code-commit", default=None)
    parser.add_argument("--as-of", default=None, help="the date the log line carries, YYYY-MM-DD")


def parser():
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate the registry, the split files and the layout")
    sub.add_parser("schema", help="print the catalog's SQL")
    sub.add_parser("part", help="where a person's frames go under the split rule").add_argument("person")
    build_p = sub.add_parser("build", help="build a new version of the catalog from the manifests")
    build_p.add_argument("--store", required=True, help="the catalog's directory")
    build_p.add_argument("--manifest", action="append", default=[])
    build_p.add_argument("--root", default="", help="where the registry's manifest paths start")
    build_p.add_argument("--drop-superseded", action="store_true",
                         help="leave out each named manifest that another named one supersedes")
    add_version_arguments(build_p)
    sub.add_parser("versions", help="print the version log").add_argument("store")
    for name in ("query", "similar", "summary", "export", "embed", "split-check"):
        sub.add_parser(name).add_argument("catalog", help="a store, or one version's file")
    for name in ("query", "similar", "summary", "export", "split-check"):
        sub.choices[name].add_argument("--version", type=positive, default=None, help="a store's version")
    add_query_arguments(sub.choices["query"])
    sub.choices["similar"].add_argument("--model", required=True)
    sub.choices["similar"].add_argument("--item", required=True)
    sub.choices["similar"].add_argument("--k", type=count, default=24)
    sub.choices["similar"].add_argument("--parts", default="", help="comma-separated; train,validation unless named")
    sub.choices["export"].add_argument("--table", required=True)
    sub.choices["export"].add_argument("--out", required=True)
    sub.choices["embed"].add_argument("--model", required=True)
    sub.choices["embed"].add_argument("--vectors", required=True)
    add_version_arguments(sub.choices["embed"])
    return top


def version_line(record, new):
    return json.dumps({"version": record.version, "file": record.file, "sha256": record.sha256,
                       "new": new, "frames": record.frames, "shards": len(record.shards),
                       "added_shards": list(record.added_shards),
                       "removed_shards": list(record.removed_shards)}, sort_keys=True)


def command_check(args):
    inputs = load_inputs()
    print(f"registry: {len(inputs.registry)} sources ({', '.join(inputs.registry)});"
          f" test persons: {len(inputs.test_persons)}; validation share: {inputs.rule.validation_share}")
    return 0


def command_part(args):
    inputs = load_inputs()
    part, _ = person_part(args.person.strip(), inputs.test_persons, inputs.rule)
    print(part.value)
    return 0


def command_build(args):
    inputs = load_inputs()
    manifests = manifest_paths(inputs.registry, args.manifest, args.root, args.drop_superseded)
    if not manifests:
        raise CatalogError("no manifest to read: name one with --manifest, or register a shard")
    record, new = build(args.store, manifests, inputs, args.code_commit, args.as_of)
    print(version_line(record, new))
    return 0


def command_versions(args):
    records = read_versions(args.store)
    if not records:
        raise CatalogError(f"{args.store}: no catalog there; build one first")
    for record in records:
        print(record.model_dump_json(exclude_none=True))
    return 0


def command_query(args):
    rows = run_query(open_catalog(args.catalog, args.version), query_from_args(args))
    if args.count:
        print(len(rows))
    else:
        for row in rows:
            print(json.dumps(row, sort_keys=True))
    return 0


def command_embed(args):
    loaded, (record, new) = embed(args.catalog, args.model, args.vectors, args.code_commit, args.as_of)
    print(json.dumps({"model": args.model, "vectors": loaded, "version": record.version,
                      "sha256": record.sha256, "new": new}, sort_keys=True))
    return 0


def command_read(args):
    db = open_catalog(args.catalog, args.version)
    if args.command == "similar":
        result = similar(db, args.model, args.item, args.k, split_list(args.parts, Part) or DEFAULT_PARTS)
    elif args.command == "summary":
        result = summary(db)
    elif args.command == "split-check":
        result = split_check(db, load_inputs())
        if not result["disjoint"]:
            print(json.dumps(result, indent=2, sort_keys=True))
            raise CatalogError("the split is not disjoint; no training step reads this version")
    else:
        result = {"table": args.table, "rows": export(db, args.table, args.out), "out": args.out}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


HANDLERS = {"check": command_check, "part": command_part, "build": command_build,
            "versions": command_versions, "query": command_query, "embed": command_embed}


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
