"""The leak checks at ingestion: near-duplicates across a split (CHK-6) and undeclared aliases
(CHK-7).

spine-program's LEAKAGE.md (sections 1 and 2) states the rule: an evaluation item is held out only
if no frame of it, under any name, is on the other side, and unknown is not clean. Two of its
nine checks were never run on the real corpus: CHK-6, near-duplicates across splits, found by a
perceptual hash and confirmed by the normalised cross-correlation of a 64 x 64 reduction at 0.97
or more; and CHK-7, groups of frames that share their bytes (the store key) or their pixels (the
pixel key, the sha256 of a 0.5-99.5 percentile 8-bit reduction) while spanning persons or sources
nobody declared to be one. This module is those rules, pure, so the gate proves them; reading a
shard, decoding a frame and reducing it are tools/leaks.py's, which hands the rules the
reductions as bytes.

The candidate search is multi-index hashing: the 64 bits of a perceptual hash are cut into four
bands of 16, and two hashes within distance d share, by the pigeonhole principle, at least one
band within distance d // 4, so probing each band's neighbours within that radius finds every
pair within d without comparing every frame with every other, which a join of a million frames
could not afford. The verdicts are rows, never prose: a finding names its check, the frames, their
persons, parts and sources, the key or the scores that tied them, and why it fails.
"""

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from math import cos, pi, sqrt
from operator import mul
from statistics import median

from beartype import beartype
from beethoven_qa.contracts import ensure, require
from pydantic import BaseModel, ConfigDict, Field

HASH_BITS = 64
HASH_SPACE = 2**HASH_BITS
# The low-frequency block a perceptual hash keeps: 8 x 8 DCT coefficients, one bit each.
HASH_SIDE = 8
BANDS = 4
BAND_BITS = HASH_BITS // BANDS
BAND_MASK = (1 << BAND_BITS) - 1
# LEAKAGE.md's confirmation threshold for a near-duplicate, on the 64 x 64 reduction.
NCC_MIN = 0.97
NCC_SIDE = 64
# The perceptual-hash distance under which a pair is a candidate for the NCC confirmation: wide
# enough that a resized or re-exposed copy is a candidate, since NCC_MIN is what decides. A hash
# sets 32 of its 64 bits, so distances are even and 6 probes one bit around each band, as 4 does
# (grid/README.md, The leak checks, has what was measured).
DEFAULT_DISTANCE = 6
PASS, FAIL = "PASS", "FAIL"
CHK6, CHK7, UNKNOWN = "CHK-6", "CHK-7", "UNKNOWN"


@dataclass(frozen=True)
class Print:
    """One frame as the checks see it: who it is, where it is split, and its three keys."""

    frame: str
    person: str
    part: str
    source: str
    store_key: str
    pixel_key: str
    phash: int


@dataclass(frozen=True)
class Scored:
    """A candidate pair, by index into the prints, with its hash distance and its NCC64."""

    first: int
    second: int
    distance: int
    ncc: float


@dataclass(frozen=True)
class Finding:
    """One failing row of a check: the frames it ties, and what ties them."""

    check: str
    reason: str
    frames: tuple[str, ...]
    persons: tuple[str, ...]
    parts: tuple[str, ...]
    sources: tuple[str, ...]
    key: str = ""
    distance: int | None = None
    ncc: float | None = None


class PersonAlias(BaseModel):
    """Person keys a person declared to be one person, with why (a crosswalk, a release note)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    persons: tuple[str, ...] = Field(min_length=2)
    why: str = Field(min_length=1)


class SourceAlias(BaseModel):
    """Sources a person declared to be one collection under two names, with why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sources: tuple[str, ...] = Field(min_length=2)
    why: str = Field(min_length=1)


class DeclaredAliases(BaseModel):
    """data/splits/aliases.json: what the checks take as one, and nothing else."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    persons: tuple[PersonAlias, ...] = ()
    sources: tuple[SourceAlias, ...] = ()


@beartype
@require(lambda a: 0 <= a < HASH_SPACE, "a hash is a 64-bit value")
@require(lambda b: 0 <= b < HASH_SPACE, "a hash is a 64-bit value")
@ensure(lambda result: 0 <= result <= HASH_BITS, "a distance counts differing bits")
@ensure(lambda result, a, b: (result == 0) == (a == b), "zero exactly for the same hash")
def hamming(a: int, b: int) -> int:
    """The number of bits two hashes differ in."""
    return (a ^ b).bit_count()


@lru_cache(maxsize=8)
def _cosines(side: int) -> tuple[tuple[float, ...], ...]:
    """The DCT-II basis rows of the low frequencies a hash keeps, for an image of this side."""
    return tuple(
        tuple(cos(pi * (2 * x + 1) * u / (2 * side)) for x in range(side)) for u in range(HASH_SIDE)
    )


def _low_frequencies(grey: bytes, side: int) -> list[float]:
    """The 8 x 8 low-frequency DCT-II coefficients of a square grey image, row by row.

    Only the kept frequencies are computed, a row transform then a column transform, so a
    32 x 32 reduction costs about ten thousand products. Each coefficient is rounded to six
    places, so the floating-point noise of a flat image is zero and never sets a bit.
    """
    basis = _cosines(side)
    rows = [grey[y * side : (y + 1) * side] for y in range(side)]
    across = [[sum(map(mul, row, wave)) for row in rows] for wave in basis]
    return [
        round(sum(map(mul, basis[v], across[u])), 6)
        for v in range(HASH_SIDE)
        for u in range(HASH_SIDE)
    ]


@beartype
@require(lambda side: HASH_SIDE <= side <= 64, "a reduction of 8 to 64 pixels a side")
@require(lambda grey, side: len(grey) == side * side, "a square image, row by row")
@ensure(lambda result: 0 <= result < HASH_SPACE, "a 64-bit hash")
@ensure(
    lambda result, grey: len(set(grey)) > 1 or result in (0, 1 << (HASH_BITS - 1)),
    "a flat image sets at most the bit of its mean",
)
def phash(grey: bytes, side: int) -> int:
    """The perceptual hash of a square 8-bit grey reduction: one bit per low frequency of its
    DCT, set where the coefficient stands above the median of the 64, the first bit the mean's.
    """
    coefficients = _low_frequencies(grey, side)
    middle = median(coefficients)
    code = 0
    for value in coefficients:
        code = (code << 1) | (1 if value > middle else 0)
    return code


Moments = tuple[int, int]


@beartype
@ensure(lambda result, r: 0 <= result[0] <= 255 * len(r), "a sum of bytes")
@ensure(lambda result, r: result[0] ** 2 <= len(r) * result[1], "Cauchy-Schwarz holds")
def moments(r: bytes) -> Moments:
    """The sum and the sum of squares of a reduction, which every NCC of it reuses: a join
    scores each frame against many, so the two are taken once a frame, not once a pair."""
    total: int = sum(map(mul, r, r))
    return sum(r), total


def _consistent(r: bytes, m: Moments) -> bool:
    """What moments' contracts promise, cheap enough to ask of every pair."""
    return 0 <= m[0] <= 255 * len(r) and m[0] ** 2 <= len(r) * m[1]


@beartype
@require(lambda a, b: len(a) == len(b) > 0, "two reductions of the same size")
@require(lambda a, of_a: _consistent(a, of_a), "the first reduction's moments")
@require(lambda b, of_b: _consistent(b, of_b), "the second reduction's moments")
@ensure(lambda result: -1.0 <= result <= 1.0, "a correlation lies between -1 and 1")
@ensure(lambda result, a, b: a != b or result == 1.0, "a reduction matches itself exactly")
def ncc_with(a: bytes, b: bytes, of_a: Moments, of_b: Moments) -> float:
    """The normalised cross-correlation of two reductions given their moments, in integers until
    the last division.

    Two identical reductions are 1, flat ones included, since a flat frame copied under two
    persons is a copy; a flat reduction against any other is 0, since it correlates with nothing.
    """
    if a == b:
        return 1.0
    n, (sum_a, squares_a), (sum_b, squares_b) = len(a), of_a, of_b
    spread_a, spread_b = n * squares_a - sum_a * sum_a, n * squares_b - sum_b * sum_b
    if spread_a <= 0 or spread_b <= 0:
        return 0.0
    covariance: int = n * sum(map(mul, a, b)) - sum_a * sum_b
    return max(-1.0, min(1.0, covariance / (sqrt(spread_a) * sqrt(spread_b))))


@beartype
@require(lambda a, b: len(a) == len(b) > 0, "two reductions of the same size")
@ensure(lambda result: -1.0 <= result <= 1.0, "a correlation lies between -1 and 1")
@ensure(lambda result, a, b: a != b or result == 1.0, "a reduction matches itself exactly")
def ncc(a: bytes, b: bytes) -> float:
    """NCC64 of two reductions: LEAKAGE.md's confirmation of a near-duplicate at 0.97 or more."""
    return ncc_with(a, b, moments(a), moments(b))


@beartype
@require(lambda code: 0 <= code < HASH_SPACE, "a hash is a 64-bit value")
@ensure(lambda result: len(result) == BANDS, "one value per band")
@ensure(
    lambda result, code: sum(v << (BAND_BITS * k) for k, v in enumerate(result)) == code,
    "the bands put back together are the hash",
)
def bands(code: int) -> tuple[int, ...]:
    """The four 16-bit bands of a hash, the lowest first."""
    return tuple((code >> (BAND_BITS * k)) & BAND_MASK for k in range(BANDS))


@beartype
@require(lambda threshold: 0 <= threshold <= HASH_BITS, "a distance between hashes")
@ensure(
    lambda result, threshold: BANDS * (result + 1) > threshold,
    "two hashes within the threshold share a band within the radius (pigeonhole)",
)
@ensure(lambda result, threshold: result == 0 or BANDS * result <= threshold, "and no wider")
def probe_radius(threshold: int) -> int:
    """How far around each band the search looks so that no pair within the threshold is missed."""
    return threshold // BANDS


def _neighbours(value: int, radius: int) -> tuple[int, ...]:
    """Every 16-bit value within the radius of this one, itself first."""
    found = [value]
    for flips in range(1, radius + 1):
        for bits in combinations(range(BAND_BITS), flips):
            found.append(value ^ sum(1 << bit for bit in bits))
    return tuple(found)


def _index(codes: tuple[int, ...]) -> list[dict[int, list[int]]]:
    """For each band, the indices of the hashes that hold each value of it."""
    index: list[dict[int, list[int]]] = [defaultdict(list) for _ in range(BANDS)]
    for position, code in enumerate(codes):
        for band, value in enumerate(bands(code)):
            index[band][value].append(position)
    return index


def _all_hashes(codes: tuple[int, ...]) -> bool:
    return all(0 <= code < HASH_SPACE for code in codes)


def _distance(a: int, b: int) -> int:
    """hamming without its contracts, for the loops that call it a million times."""
    return (a ^ b).bit_count()


def _close(codes: tuple[int, ...], probe: int, other: int, threshold: int) -> bool:
    return other != probe and _distance(codes[probe], codes[other]) <= threshold


def _pairs_of(
    probe: int, codes: tuple[int, ...], index: list[dict[int, list[int]]], reach: tuple[int, int]
) -> set[tuple[int, int]]:
    """The pairs one probe makes with the hashes that share a band with it within the radius and
    lie within the threshold of it; reach is the radius and the threshold."""
    radius, threshold = reach
    found = set()
    for band, value in enumerate(bands(codes[probe])):
        for near in _neighbours(value, radius):
            for other in index[band].get(near, ()):
                if _close(codes, probe, other, threshold):
                    found.add((min(probe, other), max(probe, other)))
    return found


@beartype
@require(lambda codes: _all_hashes(codes), "every hash is a 64-bit value")
@require(lambda threshold: 0 <= threshold <= HASH_BITS, "a distance between hashes")
@require(lambda codes, probes: all(0 <= p < len(codes) for p in probes), "probes index the codes")
@require(lambda limit: limit >= 0, "a budget of pairs")
@ensure(lambda result: list(result) == sorted(set(result)), "sorted, each pair once")
@ensure(lambda result: all(i < j for i, j, _ in result), "each pair in index order")
@ensure(
    lambda result, codes, threshold: all(
        d == _distance(codes[i], codes[j]) <= threshold for i, j, d in result
    ),
    "every pair is within the threshold, at the distance it gives",
)
@ensure(
    lambda result, probes: all(i in probes or j in probes for i, j, _ in result),
    "every pair holds a probe",
)
@ensure(lambda result, limit: len(result) <= limit + 1, "past the budget by one pair at most")
def candidate_pairs(
    codes: tuple[int, ...], threshold: int, probes: frozenset[int], limit: int
) -> tuple[tuple[int, int, int], ...]:
    """Every pair of hashes within the threshold that holds a probe, with its distance, by
    multi-index hashing.

    A whole join probes every index; a new shard against the registered ones probes only its own
    frames. The search stops once it holds more pairs than the limit, so a corpus whose hashes
    crowd together answers with limit + 1 pairs, which the caller reads as a check that did not
    finish, instead of running for days. The tests compare the answer with the all-pairs search,
    which the contracts cannot afford at a million frames.
    """
    index, radius = _index(codes), probe_radius(threshold)
    found: set[tuple[int, int]] = set()
    for probe in sorted(probes):
        found.update(_pairs_of(probe, codes, index, (radius, threshold)))
        if len(found) > limit:
            break
    pairs = sorted(found)[: limit + 1]
    return tuple((i, j, _distance(codes[i], codes[j])) for i, j in pairs)


@beartype
@require(lambda groups: all(len(g) >= 2 for g in groups), "an alias names two or more")
@ensure(
    lambda result, groups: all(len({result[name] for name in g}) == 1 for g in groups),
    "every declared group is one class",
)
@ensure(lambda result: all(result[r] == r for r in result.values()), "a class is named by a member")
@ensure(lambda result: all(r <= name for name, r in result.items()), "by its first name in order")
def alias_classes(groups: tuple[tuple[str, ...], ...]) -> dict[str, str]:
    """The class of every name a declaration groups, joined across declarations (union-find),
    each named by its alphabetically first member; a name no declaration groups is its own."""
    parent: dict[str, str] = {}

    def root(name: str) -> str:
        while parent.setdefault(name, name) != name:
            name = parent[name]
        return name

    for group in groups:
        for name in group[1:]:
            low, high = sorted((root(group[0]), root(name)))
            parent[high] = low
    return {name: root(name) for name in parent}


Columns = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]


def _the(prints: tuple[Print, ...], members: tuple[int, ...]) -> Columns:
    """The frames, persons, parts and sources of some prints, each sorted and each once."""
    chosen = [prints[i] for i in members]
    return (
        tuple(sorted({p.frame for p in chosen})),
        tuple(sorted({p.person for p in chosen})),
        tuple(sorted({p.part for p in chosen})),
        tuple(sorted({p.source for p in chosen})),
    )


def _valid_pairs(prints: tuple[Print, ...], scored: tuple[Scored, ...]) -> bool:
    return all(0 <= s.first < s.second < len(prints) for s in scored)


def _crosses(a: Print, b: Print, persons: dict[str, str]) -> bool:
    return a.part != b.part or persons.get(a.person, a.person) != persons.get(b.person, b.person)


def _valid_indices(prints: tuple[Print, ...], pairs: tuple[tuple[int, int, int], ...]) -> bool:
    return all(0 <= i < j < len(prints) for i, j, _ in pairs)


@beartype
@require(lambda prints, pairs: _valid_indices(prints, pairs), "pairs index the prints")
@ensure(lambda result, pairs: set(result) <= set(pairs), "a selection of the pairs")
@ensure(
    lambda result, prints, persons: all(
        prints[i].part != prints[j].part
        or persons.get(prints[i].person, prints[i].person)
        != persons.get(prints[j].person, prints[j].person)
        for i, j, _ in result
    ),
    "each on two parts or under two persons no declaration joins",
)
def crossing(
    prints: tuple[Print, ...], pairs: tuple[tuple[int, int, int], ...], persons: dict[str, str]
) -> tuple[tuple[int, int, int], ...]:
    """The pairs whose two frames stand on two sides of the split: two parts, or two persons no
    declaration joins (whom the hash may put on two sides whenever another frame comes). A pair
    on one side is never scored, since no NCC could make it fail."""
    return tuple(pair for pair in pairs if _crosses(prints[pair[0]], prints[pair[1]], persons))


@beartype
@require(lambda prints, scored: _valid_pairs(prints, scored), "pairs index the prints")
@ensure(lambda result: all(f.check == CHK6 for f in result), "CHK-6 rows")
@ensure(
    lambda result: all(f.ncc is not None and f.ncc >= NCC_MIN for f in result),
    "every row is confirmed by NCC64",
)
@ensure(lambda result, scored: len(result) <= len(scored), "at most one row per pair")
def near_duplicates(
    prints: tuple[Print, ...], scored: tuple[Scored, ...], persons: dict[str, str]
) -> tuple[Finding, ...]:
    """CHK-6: each candidate pair whose NCC64 confirms it and that crosses the split; a
    near-copy of one person in one part is the same acquisition seen twice, which the split
    already keeps together. A pair with one pixel key is CHK-7's to report, which reports it
    whenever this check would, so no leak is counted twice."""
    rows = []
    for pair in scored:
        a, b = prints[pair.first], prints[pair.second]
        if pair.ncc < NCC_MIN or a.pixel_key == b.pixel_key or not _crosses(a, b, persons):
            continue
        same = persons.get(a.person, a.person) == persons.get(b.person, b.person)
        reason = "near-duplicate across parts" if same else "near-duplicate under two persons"
        columns = _the(prints, (pair.first, pair.second))
        rows.append(Finding(CHK6, reason, *columns, distance=pair.distance, ncc=pair.ncc))
    return tuple(rows)


def _groups(prints: tuple[Print, ...], kind: str) -> list[tuple[str, tuple[int, ...]]]:
    """The keys of one kind held by more than one print, with the prints that hold them."""
    holders: dict[str, list[int]] = defaultdict(list)
    for position, item in enumerate(prints):
        holders[getattr(item, kind)].append(position)
    return sorted((key, tuple(members)) for key, members in holders.items() if len(members) > 1)


def _why_shared(
    prints: tuple[Print, ...], members: tuple[int, ...], classes: dict[str, str]
) -> str:
    """Why a group of prints sharing a key fails, or the empty string where it does not."""
    chosen = [prints[i] for i in members]
    if len({classes.get(p.person, p.person) for p in chosen}) > 1:
        return "undeclared alias: one key under two persons"
    sources = {"source:" + p.source for p in chosen}
    if len({classes.get(source, source) for source in sources}) > 1:
        return "undeclared alias: one key under two sources"
    if len({p.part for p in chosen}) > 1:
        return "declared alias split across parts"
    return ""


@beartype
@ensure(lambda result: all(f.check == CHK7 for f in result), "CHK-7 rows")
@ensure(lambda result: all(len(f.frames) >= 2 for f in result), "a row ties two frames or more")
def shared_keys(prints: tuple[Print, ...], classes: dict[str, str]) -> tuple[Finding, ...]:
    """CHK-7: every group of frames sharing a store key or a pixel key that spans persons or
    sources no declaration joins, or one declared person split across parts. A pixel-key group
    that is exactly a store-key group's frames is the same finding and is not repeated.

    The classes hold persons by their keys and sources as "source:<id>", so one declaration
    file joins both without a person key ever being read as a source.
    """
    rows, seen = [], set()
    for kind in ("store_key", "pixel_key"):
        for key, members in _groups(prints, kind):
            reason = _why_shared(prints, members, classes)
            if not reason or members in seen:
                continue
            seen.add(members)
            rows.append(Finding(CHK7, f"{reason} ({kind})", *_the(prints, members), key=key))
    return tuple(rows)


@beartype
@ensure(lambda result, frames: len(result) == len(frames), "one row per frame not fingerprinted")
@ensure(lambda result: all(f.check == UNKNOWN for f in result), "UNKNOWN rows")
def unfingerprinted(frames: tuple[tuple[str, str, str, str], ...]) -> tuple[Finding, ...]:
    """A row for each frame (frame, person, source, why) no key could be taken from: unknown is
    not clean, so a frame that cannot be read fails the check rather than passing unseen."""
    return tuple(
        Finding(UNKNOWN, f"not fingerprinted: {why}", (frame,), (person,), (), (source,))
        for frame, person, source, why in frames
    )


@beartype
@ensure(lambda result, findings: (result == PASS) == (len(findings) == 0), "PASS only when empty")
def verdict(findings: tuple[Finding, ...]) -> str:
    """PASS when no row fails, FAIL otherwise."""
    return FAIL if findings else PASS


@beartype
@require(
    lambda findings: all(f.check in (CHK6, CHK7, UNKNOWN) for f in findings), "rows of the checks"
)
@ensure(lambda result, findings: sum(result.values()) == len(findings), "every row counted once")
@ensure(lambda result: set(result) == {CHK6, CHK7, UNKNOWN}, "every check named, zero or not")
def counts(findings: tuple[Finding, ...]) -> dict[str, int]:
    """The failing rows per check."""
    tally = {CHK6: 0, CHK7: 0, UNKNOWN: 0}
    for finding in findings:
        tally[finding.check] += 1
    return tally
