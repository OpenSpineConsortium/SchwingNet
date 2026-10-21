"""The rules of the frame catalog: what a shard records, how a person is split, what a query asks.

docs/research/data-catalog.md says why the registry of task #10 is a catalog and not a pile of
files: every frame the workflow may train or test on is a row with its facts (its source, its
person's pseudonym, its level labels, the region they span, the view angle, the device and the
exposure that made it, the shard that holds it), a run names a query and reads only its answer,
and the nuisance factors that tell a C-arm frame from a film from a cone-beam projection are
columns, so the mapping of every device into one domain can be measured per device, per exposure
band and per angle band instead of believed. The reading and writing (the manifests on the grid,
the SQLite file, the hashing of bytes) live in tools/catalog.py; what is here is pure, so the gate
proves it: the shapes at the boundary (pydantic), the split of a person by a hash already taken,
the bands a continuous fact falls into, the SQL a query turns into, and the cosine rule a
similarity query ranks by.
"""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from math import isfinite, sqrt
from typing import Annotated

from beartype import beartype
from beethoven_qa.contracts import ensure, require
from pydantic import BaseModel, ConfigDict, Field, model_validator

HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Unit = Annotated[float, Field(ge=0.0, le=1.0)]
Positive = Annotated[float, Field(gt=0)]


class IdentityLevel(StrEnum):
    """The unit a split must not share, per source; the names are beethoven-research's."""

    PATIENT = "patient"
    STUDY = "study"
    CADAVER = "cadaver"
    SOURCE_VOLUME = "source_volume"


class Part(StrEnum):
    """Where a person's frames go: a trainer reads train, selection validation, no one test."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class ShardKind(StrEnum):
    """A shard is one of these, never a mix: training persons, test persons, frames for review."""

    TRAIN = "train"
    TEST = "test"
    REVIEW = "review"


class Region(StrEnum):
    """The part of the spine a level belongs to."""

    CERVICAL = "cervical"
    THORACIC = "thoracic"
    LUMBAR = "lumbar"
    SACRUM = "sacrum"


class View(StrEnum):
    """The band a view angle falls into, so frontal and lateral frames are asked for by name."""

    FRONTAL = "frontal"
    LATERAL = "lateral"
    OBLIQUE = "oblique"


class Modality(StrEnum):
    """What made the frame: the record's words, one per source of nuisance."""

    XA = "xa"  # a C-arm spot frame (DICOM XA): C-ArmLSpine
    RF = "rf"  # fluoroscopy: DeepFluoro, Geneva
    CBCT_PROJECTION = "cbct_projection"  # one projection of a cone-beam sweep: COBRA, the sweeps
    DX = "dx"  # a digital plain film: VinDr, BUU, CSXA
    CR = "cr"  # a computed-radiography or scanned film: NHANES II
    RENDER = "render"  # a DRR or other synthetic image: every CT render


class DeviceClass(StrEnum):
    """The coarse device family, so a query spans makes and models without naming them."""

    MOBILE_C_ARM = "mobile_c_arm"
    FIXED_C_ARM = "fixed_c_arm"
    CBCT_GANTRY = "cbct_gantry"
    FILM = "film"
    SYNTHETIC = "synthetic"


# The 27 classes the level encoder names (spine-program DATASET_USAGE.md, section 1), in order.
LEVELS: tuple[str, ...] = (
    *(f"C{i}" for i in range(1, 8)),
    *(f"T{i}" for i in range(1, 14)),
    *(f"L{i}" for i in range(1, 7)),
    "sacrum",
)
# The rare classes the owner annotates as they arrive: a thirteenth thoracic, a sixth lumbar body.
TRANSITIONAL: tuple[str, ...] = ("T13", "L6")
HASH_SPACE = 2**64
MANIFEST_SCHEMA = 1


@beartype
@require(lambda level: level in LEVELS, "a level is one of the 27 classes")
@ensure(
    lambda result, level: (result is Region.SACRUM) == (level == "sacrum"),
    "the sacrum is its own region",
)
@ensure(
    lambda result, level: level == "sacrum" or result.value[0] == level[0].lower(),
    "a vertebra's region starts with its letter",
)
def region_of(level: str) -> Region:
    """The region a level belongs to, read from its letter."""
    if level == "sacrum":
        return Region.SACRUM
    return {"C": Region.CERVICAL, "T": Region.THORACIC, "L": Region.LUMBAR}[level[0]]


@beartype
@require(lambda level: level in LEVELS, "a level is one of the 27 classes")
@ensure(lambda result, level: result == (level in TRANSITIONAL), "transitional means T13 or L6")
def is_transitional(level: str) -> bool:
    """Whether a level is one of the rare classes the registry counts persons for separately."""
    return level in TRANSITIONAL


@beartype
@require(lambda hash_value: 0 <= hash_value < HASH_SPACE, "a hash is a 64-bit value")
@require(lambda validation_share: 0.0 < validation_share < 1.0, "a share leaves both sides some")
@ensure(lambda result: result is not Part.TEST, "a hash never sends a person to the test set")
@ensure(
    lambda result, hash_value, validation_share: (
        (result is Part.VALIDATION) == (hash_value < validation_share * HASH_SPACE)
    ),
    "the lowest share of the hash space is validation, the rest training",
)
def hash_part(hash_value: int, validation_share: float) -> Part:
    """Train or validation for a person, from the hash of its key: stable whoever ingests it."""
    if hash_value < validation_share * HASH_SPACE:
        return Part.VALIDATION
    return Part.TRAIN


@beartype
@require(lambda person: person != "" and person == person.strip(), "a person key is named exactly")
@require(lambda hash_value: 0 <= hash_value < HASH_SPACE, "a hash is a 64-bit value")
@require(lambda validation_share: 0.0 < validation_share < 1.0, "a share leaves both sides some")
@ensure(
    lambda result, person, test_persons: (result is Part.TEST) == (person in test_persons),
    "the frozen list alone decides who is a test person",
)
def part_of(
    person: str, hash_value: int, validation_share: float, test_persons: frozenset[str]
) -> Part:
    """Where a person's frames go: the frozen test list first, the hash for everyone else."""
    if person in test_persons:
        return Part.TEST
    return hash_part(hash_value, validation_share)


@beartype
@require(lambda lat_from_ap_deg: -360.0 <= lat_from_ap_deg <= 360.0, "an angle is in degrees")
@ensure(
    lambda result, lat_from_ap_deg: (
        (result is View.FRONTAL)
        == (abs(lat_from_ap_deg) % 180.0 <= 15.0 or abs(lat_from_ap_deg) % 180.0 >= 165.0)
    ),
    "within 15 degrees of AP or PA is frontal",
)
@ensure(
    lambda result, lat_from_ap_deg: (
        (result is View.LATERAL) == (75.0 <= abs(lat_from_ap_deg) % 180.0 <= 105.0)
    ),
    "within 15 degrees of a true lateral is lateral",
)
def view_band(lat_from_ap_deg: float) -> View:
    """The band of a view angle measured from AP (0 is AP, 90 a lateral, 180 PA)."""
    folded = abs(lat_from_ap_deg) % 180.0
    if folded <= 15.0 or folded >= 165.0:
        return View.FRONTAL
    if 75.0 <= folded <= 105.0:
        return View.LATERAL
    return View.OBLIQUE


@beartype
@require(lambda value: 0.0 <= value < 1_000_000.0, "a measured value is finite and not negative")
@require(lambda width: 1 <= width <= 1000, "a band has a width in whole units")
@ensure(lambda result, value, width: result <= value < result + width, "the value lies in its band")
@ensure(lambda result, width: result % width == 0, "a band starts at a multiple of its width")
def band(value: float, width: int) -> int:
    """The lower edge of the band a continuous fact falls into (a kVp of 73 at width 10 is 70)."""
    return int(value // width) * width


def _has_direction(vector: tuple[float, ...]) -> bool:
    """Whether a vector's cosine is defined: finite, some component not zero, none extreme.

    A component below 1e-150 squares to zero in a float and one above 1e150 squares to
    infinity, so a norm could vanish or overflow where real arithmetic says it does not;
    an embedding never holds such a value, and CrossHair found both (the gate reasons over
    reals, so the bound is stated on the components, where it holds either way).
    """
    return (
        any(x != 0.0 for x in vector)
        and all(isfinite(x) for x in vector)
        and all(x == 0.0 or 1e-150 <= abs(x) <= 1e150 for x in vector)
    )


@beartype
@require(lambda a, b: len(a) == len(b) > 0, "two vectors of the same length")
@require(lambda a: _has_direction(a), "the first vector has a direction")
@require(lambda b: _has_direction(b), "the second vector has a direction")
@ensure(lambda result: -1.0 - 1e-9 <= result <= 1.0 + 1e-9, "a cosine lies between -1 and 1")
def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """The cosine of two embedding vectors, which a similarity query ranks by."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (sqrt(sum(x * x for x in a)) * sqrt(sum(y * y for y in b)))


@beartype
@require(lambda k: k >= 0, "a count is not negative")
@require(lambda scored: len({name for name, _ in scored}) == len(scored), "each name scored once")
@require(lambda scored: all(isfinite(score) for _, score in scored), "every score is a number")
@ensure(lambda result, scored, k: len(result) == min(k, len(scored)), "the k best, or all")
@ensure(
    lambda result, scored: all(
        dict(scored)[x] >= dict(scored)[y] for x, y in zip(result, result[1:], strict=False)
    ),
    "the best first",
)
def best(scored: tuple[tuple[str, float], ...], k: int) -> tuple[str, ...]:
    """The names of the k highest scores, best first; ties keep the order they were given in."""
    ranked = sorted(scored, key=lambda pair: -pair[1])
    return tuple(name for name, _ in ranked[:k])


@beartype
@require(lambda source: source != "" and "/" not in source, "a source id has no slash")
@require(lambda ingest_date: ingest_date != "" and "/" not in ingest_date, "nor has a date")
@require(lambda content_hash: len(content_hash) >= 12, "a content hash gives twelve characters")
@require(lambda content_hash: "/" not in content_hash, "and holds no slash")
@ensure(lambda result, source: result.startswith(source + "/"), "a shard is named under its source")
@ensure(lambda result, content_hash: result.endswith(content_hash[:12]), "and by its content")
@ensure(lambda result: result.count("/") == 1, "one slash: the source, then the shard")
def shard_name(source: str, ingest_date: str, content_hash: str) -> str:
    """The name of a shard: its source, the day it was ingested and its content hash's start.

    The exact spellings (a lowercase source id, a YYYY-MM-DD date, a sha256 digest) are the
    manifest's pydantic shape, checked where a file is read; here the contract states only what
    the name's structure needs, which CrossHair can build and prove.
    """
    return f"{source}/{ingest_date}-{content_hash[:12]}"


@beartype
@require(lambda sha256: len(sha256) == 64, "a frame is named by its sha256 hex digest")
@require(
    lambda extension: extension != "" and "/" not in extension and "." not in extension,
    "an extension is a bare word",
)
@ensure(lambda result, sha256: result.startswith(sha256[:2] + "/"), "fanned out by the first two")
@ensure(
    lambda result, sha256, extension: result == sha256[:2] + "/" + sha256 + "." + extension,
    "then the whole digest and the extension",
)
def frame_path(sha256: str, extension: str) -> str:
    """Where a frame lives inside its shard: a folder of its first two hex digits, then its digest.

    Two hex digits fan a shard of a million frames into 256 folders of about four thousand, the
    size a directory listing on CephFS stays quick at, and the name is the content, so the same
    bytes land in the same place in every shard and a path is checked against its digest by eye.
    """
    return f"{sha256[:2]}/{sha256}.{extension}"


@beartype
@require(
    lambda root: root.startswith("/") and not root.endswith("/"),
    "a root is an absolute path with no trailing slash",
)
@require(
    lambda name: name.count("/") == 1 and not name.startswith("/") and not name.endswith("/"),
    "a shard is named source/shard",
)
@require(
    lambda root, name: root.endswith("/" + name.split("/")[0]),
    "a source's root is the folder named by its id",
)
@ensure(lambda result, root: result.startswith(root + "/shards/"), "in the source's shards folder")
@ensure(lambda result, name: result.endswith("/" + name.split("/")[1]), "named by the shard")
def shard_folder(root: str, name: str) -> str:
    """Where a shard lives on the volume: `<data root>/<source>/shards/<date-hash>`.

    The registry's grid_root is the source's own folder, the last segment of which is the
    source's id, so the data root lists its sources alphabetically by id; one shards folder
    under it, so the raw copy a source came with and the shards cut from it never mix; and the
    shard's own name, so the folder is found from the catalog row alone.
    """
    return f"{root}/shards/{name.split('/')[1]}"


@beartype
@require(lambda number: number >= 1, "versions count from one")
@require(
    lambda content_sha256: len(content_sha256) >= 12 and "/" not in content_sha256,
    "a content hash gives twelve characters and holds no slash",
)
@ensure(
    lambda result: result.startswith("catalog-") and result.endswith(".sqlite"),
    "a catalog file, by its name",
)
@ensure(lambda result, content_sha256: content_sha256[:12] in result, "named by its content")
@ensure(lambda result: "/" not in result, "a file name, not a path")
def version_file_name(number: int, content_sha256: str) -> str:
    """The file name of one catalog version: its number, zero-padded so names sort, and its hash.

    The number says which came first and the hash says what it is, so a run's artifact (the
    hash) finds the file and a person's eye finds the latest; a file whose hash does not match
    its name has been changed, which a read-only file on a read-only mount never is.
    """
    return f"catalog-{number:06d}-{content_sha256[:12]}.sqlite"


@beartype
@ensure(
    lambda result, before, after: set(result[0]) == after - before, "added is what after has new"
)
@ensure(
    lambda result, before, after: set(result[1]) == before - after, "removed is what before lost"
)
@ensure(
    lambda result: all(list(part) == sorted(part) for part in result),
    "each list sorted, so two runs print the same accounting",
)
def changed_keys(
    before: frozenset[str], after: frozenset[str]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What one version adds to and removes from its parent, as two sorted lists of keys.

    Shards, persons and sources are accounted this way between versions, the way a table
    snapshot lists its added and deleted files, so the version log says what moved and not
    only how much.
    """
    return tuple(sorted(after - before)), tuple(sorted(before - after))


# What a query reads when it names no part: never the test set, which a query asks for by name.
DEFAULT_PARTS: tuple[Part, ...] = (Part.TRAIN, Part.VALIDATION)


def _digest(hashes: tuple[str, ...]) -> str:
    return sha256("\n".join(hashes).encode("utf-8")).hexdigest()


@beartype
@require(lambda hashes: len(hashes) > 0, "a shard holds at least one frame")
@require(lambda hashes: all(len(h) == 64 for h in hashes), "each hash is a sha256 hex digest")
@ensure(lambda result: len(result) == 64, "the content hash is a sha256 hex digest")
@ensure(
    lambda result, hashes: result == _digest(tuple(sorted(hashes))),
    "the order the hashes are given in does not change the result",
)
def content_digest(hashes: tuple[str, ...]) -> str:
    """The hash of a shard's content: the sha256 over its frames' hashes in sorted order.

    Sorted, so two ingests of the same bytes name the same shard whatever order they walked
    the files in; the name of a shard carries its first twelve characters.
    """
    return _digest(tuple(sorted(hashes)))


@dataclass(frozen=True)
class Query:
    """What a run asks the catalog for; every field narrows, an empty one leaves its axis open.

    The one axis that is never open is the part: a query that names none reads DEFAULT_PARTS,
    so a trainer that forgets to say which part it wants can never be handed a test frame.
    """

    levels: tuple[str, ...] = ()
    regions: tuple[Region, ...] = ()
    views: tuple[View, ...] = ()
    modalities: tuple[Modality, ...] = ()
    device_classes: tuple[DeviceClass, ...] = ()
    sources: tuple[str, ...] = ()
    parts: tuple[Part, ...] = ()
    persons: tuple[str, ...] = ()
    shards: tuple[str, ...] = ()
    kvp_band: int | None = None
    kvp_band_width: int = 10
    labelled_only: bool = False


def _in_clause(column: str, values: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    marks = ", ".join("?" for _ in values)
    return f"{column} IN ({marks})", values


def _axes(query: Query) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """The IN clauses of every set-valued axis the query narrows."""
    columns = (
        ("item.part", tuple(p.value for p in (query.parts or DEFAULT_PARTS))),
        ("label.level", query.levels),
        ("label.region", tuple(r.value for r in query.regions)),
        ("item.view", tuple(v.value for v in query.views)),
        ("item.modality", tuple(m.value for m in query.modalities)),
        ("item.device_class", tuple(d.value for d in query.device_classes)),
        ("item.source", query.sources),
        ("item.person", query.persons),
        ("item.shard", query.shards),
    )
    return tuple(_in_clause(column, values) for column, values in columns if values)


@beartype
@require(lambda query: query.kvp_band_width >= 1, "a band has a width")
@ensure(
    lambda result: result[0].count("?") == len(result[1]),
    "one placeholder per parameter, so the SQL never carries a value",
)
@ensure(lambda result: result[0].startswith(" WHERE "), "every query narrows at least the part")
@ensure(
    lambda result, query: (
        Part.TEST in query.parts
        or Part.TEST.value not in result[1][: len(query.parts or DEFAULT_PARTS)]
    ),
    "the part clause comes first and names the test part only when the query does",
)
def where_clause(query: Query) -> tuple[str, tuple[str | int, ...]]:
    """The WHERE clause of a query over the catalog's item and label tables, with its parameters.

    A query over levels or regions needs a frame to carry such a label; the rest are facts of the
    frame itself. The values travel as parameters, so a person key or a source id is never
    spliced into SQL.
    """
    parts: list[str] = []
    params: list[str | int] = []
    for clause, values in _axes(query):
        parts.append(clause)
        params.extend(values)
    if query.kvp_band is not None:
        parts.append("item.kvp >= ? AND item.kvp < ?")
        params.extend((query.kvp_band, query.kvp_band + query.kvp_band_width))
    if query.labelled_only or query.levels or query.regions:
        parts.append("label.level IS NOT NULL")
    return " WHERE " + " AND ".join(parts), tuple(params)


class Device(BaseModel):
    """What made the frame, as the source's metadata names it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    device_class: DeviceClass
    make: str | None = None
    model: str | None = None
    detector: str | None = None


class Exposure(BaseModel):
    """The exposure that made the frame: the nuisance the catalog keeps as columns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kvp: Positive | None = None
    mas: Positive | None = None
    px_mm: Positive | None = None


class Label(BaseModel):
    """One vertebral body in a frame: its level and its box in the frame's own unit square."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: str = Field(pattern=r"^(C[1-7]|T([1-9]|1[0-3])|L[1-6]|sacrum)$")
    box: tuple[Unit, Unit, Unit, Unit]
    labeller: str = Field(min_length=1)


class Item(BaseModel):
    """One frame of a shard: the boundary where a manifest row becomes catalog facts.

    The person is the study-local pseudonym the registry's key rule produced, never an
    identifier, since this row reaches the catalog and the catalog's answers reach logs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    path: str = Field(pattern=r"^[0-9a-f]{2}/[0-9a-f]{64}\.[a-z0-9]+$")
    sha256: HexDigest
    person: str = Field(min_length=1, pattern=r"^\S.*\S$|^\S$")
    modality: Modality
    device: Device
    exposure: Exposure = Exposure()
    lat_from_ap_deg: Annotated[float, Field(ge=-360, le=360)] | None = None
    gantry_deg: Annotated[float, Field(ge=-360, le=360)] | None = None
    acquired: str | None = None
    labels: tuple[Label, ...] = ()

    @model_validator(mode="after")
    def _at_its_content_address(self) -> "Item":
        """A frame's path is frame_path of its own digest, so a path never leaves its shard and
        a row's path and hash cannot disagree."""
        expected = frame_path(self.sha256, self.path.rsplit(".", 1)[1])
        if self.path != expected:
            raise ValueError(f"the frame is at {self.path} but its digest puts it at {expected}")
        return self


class ShardManifest(BaseModel):
    """MANIFEST.json of one shard on the grid: never rewritten, superseded by name."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    schema_version: int = Field(ge=1, le=MANIFEST_SCHEMA)
    name: str = Field(pattern=r"^[a-z0-9_]+/\d{4}-\d{2}-\d{2}-[0-9a-f]{12}$")
    source: str = Field(pattern=r"^[a-z0-9_]+$")
    kind: ShardKind
    ingest_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    code_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{7,40}$")]
    supersedes: str | None = None
    items: tuple[Item, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _named_by_its_facts(self) -> "ShardManifest":
        """The name is the source, the ingest date and the content hash; nothing else may say so."""
        expected = shard_name(self.source, self.ingest_date, content_digest(self.hashes()))
        if self.name != expected:
            raise ValueError(f"the shard is named {self.name} but its facts name it {expected}")
        if self.supersedes == self.name:
            raise ValueError("a shard cannot supersede itself")
        return self

    def hashes(self) -> tuple[str, ...]:
        """The frames' hashes, which name the shard."""
        return tuple(item.sha256 for item in self.items)


class ShardRef(BaseModel):
    """A shard the registry lists: its name, where its manifest is on the grid, and its kind."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z0-9_]+/\d{4}-\d{2}-\d{2}-[0-9a-f]{12}$")
    manifest: str = Field(min_length=1)
    kind: ShardKind
    superseded_by: str | None = None


class RegistryEntry(BaseModel):
    """One file of data/registry/<source>.json: how a source enters the workflow."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(pattern=r"^[a-z0-9_]+$")
    identity_level: IdentityLevel
    person_key_rule: str = Field(min_length=1)
    access: str = Field(min_length=1)
    modality: Modality
    device_class: DeviceClass
    regions: tuple[Region, ...] = Field(min_length=1)
    grid_root: str = Field(pattern=r"^/")
    shards: tuple[ShardRef, ...] = ()
    notes: str = ""


class SplitRule(BaseModel):
    """data/splits/rule.json: the salt and the share that decide everyone not on the test list."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    salt: str = Field(min_length=1)
    validation_share: Annotated[float, Field(gt=0, lt=1)]
    hash: str = Field(min_length=1)


class FrozenPerson(BaseModel):
    """One frozen test person and why: extended only by a pull request, never by the hash."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    person: str = Field(min_length=1, pattern=r"^\S.*\S$|^\S$")
    why: str = Field(min_length=1)


class VersionRecord(BaseModel):
    """One line of a catalog store's VERSIONS.jsonl: what a version is, came from and holds.

    The store is append-only and every version file is read-only, so this line is the one
    place a version's accounting is written: its parent, when it was written, the shards it
    added and dropped beside its running totals (the shape of a table snapshot's summary), and
    its counts per source and part, which are the numbers a result row carries.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    file: str = Field(pattern=r"^catalog-\d{6}-[0-9a-f]{12}\.sqlite$")
    sha256: HexDigest
    parent: HexDigest | None = None
    schema_version: int = Field(ge=1)
    code_commit: str | None = None
    as_of: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    written_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    reason: str = Field(min_length=1)
    bytes: int = Field(ge=1)
    shards: tuple[str, ...] = ()
    added_shards: tuple[str, ...] = ()
    removed_shards: tuple[str, ...] = ()
    frames: int = Field(ge=0)
    persons: int = Field(ge=0)
    frames_by_source_and_part: dict[str, int] = {}
    embeddings_by_model: dict[str, int] = {}

    @model_validator(mode="after")
    def _named_by_its_facts(self) -> "VersionRecord":
        """The file is named by the version's number and its hash; nothing else may say so."""
        expected = version_file_name(self.version, self.sha256)
        if self.file != expected:
            raise ValueError(
                f"version {self.version} is in {self.file} but its facts name it {expected}"
            )
        if self.parent == self.sha256:
            raise ValueError("a version cannot be its own parent")
        return self
