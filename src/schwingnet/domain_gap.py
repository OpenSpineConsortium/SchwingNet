"""The DRR domain-gap study's pure rules: the group table, who a file belongs to, which files a
group gives the study, the separation statistics' arithmetic and the report line that leaves the
grid.

The owner asked for FleXray's synthetic DRRs to be set beside every held real X-ray corpus, plain
film and fluoroscopy, in dimension-reduction maps and in the separation tests a machine-learning
reviewer expects. The images stay on the Wayne State grid and the study runs there as one job
(tools/domain_gap.py); what is decided rather than computed lives here, so the gate proves it and
the job only applies it. Files are chosen by person, round-robin in a salted hash order, so a
corpus with one person of a thousand images cannot fill a group, and the choice depends on no
order of reading and no clock. The AUC is the Mann-Whitney statistic counted in integers, the
permutation p-value is never zero, the Benjamini-Hochberg adjustment never makes a smaller p
larger, and the gap's word is fixed before the numbers come back. Only printable text leaves the
grid, through grid/redact.sed, so a report line is made to pass that filter unchanged: a line the
filter would rewrite would lose the number it carries.
"""

import re
from collections import Counter
from collections.abc import Callable
from hashlib import sha256
from itertools import groupby
from math import floor, isfinite, isnan

from beartype import beartype
from beethoven_qa.contracts import ensure, require
from pydantic import BaseModel, ConfigDict, Field, model_validator

FAMILIES: tuple[str, ...] = ("synthetic", "fluoroscopy", "film")
SOURCES: tuple[str, ...] = ("render", "thunderdb", "index", "walk")
# Sources that make images rather than find them: their groups can only be synthetic.
SYNTHETIC_SOURCES: tuple[str, ...] = ("render", "thunderdb")
# The image formats tools/sample_index.py's sniff names, and the renders' arrays.
IMAGE_FORMATS: tuple[str, ...] = (
    "png",
    "jpeg",
    "jpeg2000",
    "tiff",
    "bigtiff",
    "bmp",
    "dicom",
    "npy",
)
# The pre-registered words of the gap, and the AUC lower bound at or under which a synthetic
# group cannot be told from a real one.
INDISTINGUISHABLE_AUC = 0.6
GAP_WORDS: tuple[str, ...] = ("indistinguishable", "closer than two real corpora", "separable")
# A report line's limits: the bench report keeps 200 characters a line, and a run of 32 word
# characters could be a hashed identifier grid/redact.sed withholds.
LINE_LIMIT = 200
RUN_LIMIT = 31

_PERSON_RULES = ("file", "dicom:patient", "dicom:study")
# What DICOM's padding leaves around a value: spaces and, after a UID, a NUL.
_PAD = " \x00\t\n\r\x0b\x0c"
# Patient ids that name nobody: anonymisers write these in place of an id.
_PLACEHOLDERS = frozenset(
    {
        "anonymous",
        "anonymous^",
        "anonymized",
        "anonymised",
        "anon",
        "none",
        "unknown",
        "unknown_patient",
        "na",
        "n/a",
        "null",
        "nil",
        "noname",
        "no_name",
        "patient",
        "removed",
        "redacted",
    }
)
_REGEX_FAULTS = (re.error, OverflowError, RecursionError, ValueError)


def _rule_pattern(source: str) -> re.Pattern[str] | None:
    """The compiled person regex, or None when it does not compile or names no group person."""
    try:
        pattern = re.compile(source)
    except _REGEX_FAULTS:
        return None
    return pattern if "person" in pattern.groupindex else None


def _known_rule(rule: str) -> bool:
    """Whether a person rule is one this module reads."""
    if rule in _PERSON_RULES:
        return True
    if rule.startswith("dir:"):
        place = rule[4:]
        return 1 <= len(place) <= 3 and all("0" <= c <= "9" for c in place)
    if rule.startswith("regex:"):
        return _rule_pattern(rule[6:]) is not None
    return False


def _safe_folder(folder: str) -> bool:
    """A folder under the data root: relative, no part of it climbing out, no backslash."""
    parts = folder.split("/")
    return not folder.startswith("/") and "\\" not in folder and ".." not in parts


def _all_match(values: tuple[str, ...], pattern: str) -> bool:
    return all(re.fullmatch(pattern, value) for value in values)


class GroupSpec(BaseModel):
    """One group of the study: a synthetic set or a real corpus, where its candidates come from,
    which of them it keeps, who each belongs to and how many it gives the study."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]{1,40}$")
    label: str = Field(pattern=r"^[ -~]{1,60}$")
    family: str
    source: str
    index_sources: tuple[str, ...] = ()
    folder: str = ""
    globs: tuple[str, ...] = ()
    exclude_words: tuple[str, ...] = ("mask", "label", "seg", "crop", "preview", "thumb", "overlay")
    formats: tuple[str, ...] = ()
    modalities: tuple[str, ...] = ()
    min_side: int = Field(default=256, ge=0, le=65536)
    person: str = "file"
    cap: int = Field(default=1000, ge=1, le=5000)
    per_person: int = Field(default=4, ge=1, le=100)
    licence: str = Field(default="", max_length=2000, pattern=r"^[ -~]*$")
    note: str = Field(default="", max_length=2000, pattern=r"^[ -~]*$")

    @model_validator(mode="after")
    def _holds_together(self) -> "GroupSpec":
        problems = _spec_problems(self)
        if problems:
            raise ValueError(f"group {self.id}: " + "; ".join(problems))
        return self


def _spec_problems(spec: GroupSpec) -> list[str]:
    """Every way a group's fields disagree with each other, as sentences."""
    checks = (
        (spec.family in FAMILIES, f"family {spec.family!r} is not one of {FAMILIES}"),
        (spec.source in SOURCES, f"source {spec.source!r} is not one of {SOURCES}"),
        (
            spec.source not in SYNTHETIC_SOURCES or spec.family == "synthetic",
            "a rendered or FluXray group is synthetic",
        ),
        (spec.source != "index" or bool(spec.index_sources), "an index group names its sources"),
        (spec.source == "index" or bool(spec.folder), "a group read from a folder names it"),
        (_safe_folder(spec.folder), "the folder stays under the data root"),
        (_known_rule(spec.person), f"person rule {spec.person!r} is not one this study reads"),
        (
            spec.source == "index" or not spec.person.startswith("dicom:"),
            "only the sample index carries DICOM ids",
        ),
        (set(spec.formats) <= set(IMAGE_FORMATS), f"formats are among {IMAGE_FORMATS}"),
        (_all_match(spec.modalities, r"[A-Z0-9]{1,16}"), "a modality is a DICOM code"),
        (_all_match(spec.exclude_words, r"[a-z0-9]{1,40}"), "an excluded word is lower case"),
        (all(spec.index_sources) and all(spec.globs), "no source or glob is empty"),
    )
    return [message for holds, message in checks if not holds]


class GroupTable(BaseModel):
    """data/domain_gap/groups.json: the groups, the salt every choice is ranked by, and the
    table's version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1, le=1)
    salt: str = Field(pattern=r"^[ -~]{1,100}$")
    groups: tuple[GroupSpec, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _holds_together(self) -> "GroupTable":
        ids = [group.id for group in self.groups]
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        if repeated:
            raise ValueError(f"group ids are named twice: {repeated}")
        if len({group.family for group in self.groups}) < 2:
            raise ValueError("a study sets at least two families beside each other")
        return self


def _trimmed(value: str) -> str:
    return value.strip(_PAD)


def _identifier(value: str) -> str:
    """A DICOM id with its padding taken off, or nothing when it is a placeholder."""
    found = _trimmed(value)
    low = found.lower()
    if low in _PLACEHOLDERS or set(low) <= {"0"} or not any(c.isalnum() for c in low):
        return ""
    return found


def _folder_at(relative: str, place: int) -> str:
    """The place-th folder of a relative path, from 0; the file's own name is no folder."""
    parts = [part for part in relative.split("/") if part not in ("", ".")]
    folders = parts[:-1]
    return folders[place] if place < len(folders) else ""


def _searched(source: str, relative: str) -> str:
    """The group person of the first match of the rule's regex in the relative path."""
    match = re.search(source, relative)
    if match is None:
        return ""
    return match.group("person") or ""


@beartype
@require(lambda rule: _known_rule(rule), "the rule is one the study reads")
@ensure(
    lambda result, relative, patient_id, study_uid: (
        result == "" or result in relative or result in patient_id or result in study_uid
    ),
    "a person is found in the file's own path or ids, never made up",
)
@ensure(
    lambda result, rule: rule != "file" or result == "", "a file rule names nobody but the file"
)
@ensure(
    lambda result, rule, patient_id: (
        rule != "dicom:patient" or result in ("", _trimmed(patient_id))
    ),
    "a patient rule gives the patient id or nothing",
)
@ensure(
    lambda result, rule, study_uid: rule != "dicom:study" or result in ("", _trimmed(study_uid)),
    "a study rule gives the study uid or nothing",
)
@ensure(
    lambda result, rule, relative: (
        not rule.startswith("dir:") or result == "" or result in relative.split("/")
    ),
    "a folder rule gives a whole folder of the path",
)
def person_key(rule: str, relative: str, patient_id: str, study_uid: str) -> str:
    """The person a file belongs to under a group's rule, or "" when the rule finds none and the
    caller takes the file as its own person.

    A patient id an anonymiser wrote in place of one (ANONYMOUS, 0000, -) names nobody, so it
    gives ""; when every file of a group gives "", the caller falls back to the study uid.
    """
    if rule == "dicom:patient":
        return _identifier(patient_id)
    if rule == "dicom:study":
        return _identifier(study_uid)
    if rule.startswith("dir:"):
        return _folder_at(relative, int(rule[4:]))
    if rule.startswith("regex:"):
        return _searched(rule[6:], relative)
    return ""


@beartype
@ensure(lambda result: len(result) == 64, "a rank is a sha256 hex digest")
@ensure(lambda result: all(c in "0123456789abcdef" for c in result), "in lower-case hex")
def rank_key(salt: str, text: str) -> str:
    """A file's or a person's place in the choosing order: the hash of the salt and its name, as
    schwingnet.witness.rank ranks a frame. A name that is not valid UTF-8, such as a file name
    the operating system decoded with surrogates, is hashed by its code points instead of
    stopping the job."""
    return sha256(f"{salt}:{text}".encode("utf-8", "surrogatepass")).hexdigest()


def _files_unique(candidates: tuple[tuple[str, str], ...]) -> bool:
    return len({file for file, _ in candidates}) == len(candidates)


def _available(candidates: tuple[tuple[str, str], ...], per_person: int) -> int:
    """How many files the candidates can give with no person giving more than per_person."""
    counts = Counter(person for _, person in candidates)
    return sum(min(count, per_person) for count in counts.values())


def _most_per_person(result: tuple[tuple[str, str], ...]) -> int:
    return max(Counter(person for _, person in result).values(), default=0)


def _in_turn(
    result: tuple[tuple[str, str], ...], candidates: tuple[tuple[str, str], ...], per_person: int
) -> bool:
    """No person is two behind the most-chosen one while it had a file left to give."""
    chosen = Counter(person for _, person in result)
    offered = Counter(person for _, person in candidates)
    behind = _most_per_person(result) - 1
    return all(chosen[p] >= min(offered[p], per_person, behind) for p in offered)


@beartype
@require(lambda candidates: _files_unique(candidates), "a file is a candidate once")
@require(lambda cap: cap >= 0, "a cap is a count")
@require(lambda per_person: per_person >= 1, "every person may give at least one file")
@ensure(lambda result, cap: len(result) <= cap, "never more than the cap")
@ensure(lambda result, candidates: set(result) <= set(candidates), "only candidates")
@ensure(lambda result: _files_unique(result), "no file twice")
@ensure(
    lambda result, per_person: _most_per_person(result) <= per_person,
    "no person gives more than per_person files",
)
@ensure(
    lambda result, candidates, cap, per_person: (
        len(result) == min(cap, _available(candidates, per_person))
    ),
    "as many as the cap and the persons allow, none left out",
)
@ensure(
    lambda result, candidates, per_person: _in_turn(result, candidates, per_person),
    "persons are taken in turn, a second file of anyone only after a first of everyone",
)
def choose(
    candidates: tuple[tuple[str, str], ...], cap: int, per_person: int, salt: str
) -> tuple[tuple[str, str], ...]:
    """The (file, person) pairs a group gives the study, persons taken in turn.

    Persons are ordered by the salted hash of their name and each person's files by the salted
    hash of theirs; the first file of every person comes first, then every second file, and so
    on, never more than per_person of one person, until the cap. The order of the candidates
    does not matter, since only the hashes order them.
    """
    seen: dict[str, int] = {}
    keyed: list[tuple[int, str, str, str]] = []
    for file, person in sorted(candidates, key=lambda c: (rank_key(salt, c[0]), c[0])):
        turn = seen.get(person, 0)
        seen[person] = turn + 1
        if turn < per_person:
            keyed.append((turn, rank_key(salt, person), person, file))
    keyed.sort()
    return tuple((file, person) for _, _, person, file in keyed[:cap])


def _finite(values: tuple[float, ...]) -> bool:
    return all(isfinite(v) for v in values)


def _twice_rank_sum(positive: tuple[float, ...], negative: tuple[float, ...]) -> int:
    """Twice the sum of the positives' ranks in the pooled scores, ties given their mean rank;
    twice, so a mean rank of a tie is an integer and nothing is rounded."""
    pooled = sorted([(v, 1) for v in positive] + [(v, 0) for v in negative])
    total, seen = 0, 0
    for _, run in groupby(pooled, key=lambda pair: pair[0]):
        flags = [flag for _, flag in run]
        total += (2 * seen + len(flags) + 1) * sum(flags)
        seen += len(flags)
    return total


@beartype
@require(lambda positive: len(positive) > 0, "there is at least one positive score")
@require(lambda negative: len(negative) > 0, "there is at least one negative score")
@require(
    lambda positive, negative: _finite(positive) and _finite(negative),
    "every score is a finite number",
)
@ensure(lambda result: 0.0 <= result <= 1.0, "an AUC is a probability")
@ensure(
    lambda result, positive, negative: min(positive) <= max(negative) or result == 1.0,
    "every positive above every negative is an AUC of one",
)
@ensure(
    lambda result, positive, negative: max(positive) >= min(negative) or result == 0.0,
    "every positive below every negative is an AUC of zero",
)
@ensure(
    lambda result, positive, negative: (
        min(positive + negative) != max(positive + negative) or result == 0.5
    ),
    "scores that are all equal say nothing: an AUC of one half",
)
def mann_whitney_auc(positive: tuple[float, ...], negative: tuple[float, ...]) -> float:
    """The chance a positive scores above a negative, a tie counting one half: the Mann-Whitney
    U over the product of the two counts, from the ranks, counted in integers until the last
    division so the answer is the exact fraction rounded once."""
    count_positive, count_negative = len(positive), len(negative)
    twice_u = _twice_rank_sum(positive, negative) - count_positive * (count_positive + 1)
    return twice_u / (2 * count_positive * count_negative)


@beartype
@require(lambda null: len(null) >= 1, "there is at least one permuted statistic")
@require(
    lambda observed, null: not isnan(observed) and not any(isnan(v) for v in null),
    "no statistic is NaN",
)
@ensure(lambda result: 0.0 < result <= 1.0, "a p-value lies above zero and at most one")
@ensure(
    lambda result, null: result >= 1 / (1 + len(null)),
    "never below one over the permutations plus one",
)
@ensure(
    lambda result, observed, null: (
        not all(v < observed for v in null) or result == 1 / (1 + len(null))
    ),
    "an observed statistic above every permuted one gets the smallest p",
)
@ensure(
    lambda result, observed, null: not all(v >= observed for v in null) or result == 1.0,
    "an observed statistic no greater than any permuted one gets a p of one",
)
def permutation_p(observed: float, null: tuple[float, ...]) -> float:
    """The permutation p-value: the share of permuted statistics at or above the observed one,
    the observed counted among them, so a p is never zero (Phipson and Smyth 2010)."""
    at_or_above = sum(1 for v in null if v >= observed)
    return (1 + at_or_above) / (1 + len(null))


def _monotone(pvalues: tuple[float, ...], adjusted: tuple[float, ...]) -> bool:
    """A smaller p never gets a larger adjusted p, and equal ps get equal ones."""
    ordered = sorted(zip(pvalues, adjusted, strict=True))
    pairs = list(zip(ordered, ordered[1:], strict=False))
    rising = all(low[1] <= high[1] for low, high in pairs)
    return rising and all(low[1] == high[1] for low, high in pairs if low[0] == high[0])


@beartype
@require(lambda pvalues: all(0.0 <= p <= 1.0 for p in pvalues), "every p lies in [0, 1]")
@ensure(lambda result, pvalues: len(result) == len(pvalues), "one adjusted p for each p")
@ensure(
    lambda result, pvalues: all(p <= q <= 1.0 for p, q in zip(pvalues, result, strict=True)),
    "an adjusted p is at least its p and at most one",
)
@ensure(lambda result, pvalues: _monotone(pvalues, result), "the adjustment keeps the order")
def benjamini_hochberg(pvalues: tuple[float, ...]) -> tuple[float, ...]:
    """The Benjamini-Hochberg adjusted p-values, in the order given: each p times the count over
    its rank, then the smallest of those at or above it, capped at one.

    The adjusted value is never let below its own p, which the arithmetic promises and a float's
    rounding could otherwise break by a last bit.
    """
    count = len(pvalues)
    ranked = sorted(enumerate(pvalues), key=lambda pair: pair[1])
    adjusted = list(pvalues)
    running = 1.0
    for place, (index, p) in reversed(list(enumerate(ranked, start=1))):
        running = min(running, p * count / place)
        adjusted[index] = max(p, running)
    return tuple(adjusted)


def _between(low: float, high: float, weight: float) -> float:
    """The point weight of the way from low to high, kept between the two: a float's rounding
    could otherwise put it a last bit outside, and the step between two very large values of
    opposite sign, which overflows, is taken as two shares instead."""
    if weight == 0.0:
        return low
    step = high - low
    value = low + weight * step if isfinite(step) else low * (1.0 - weight) + high * weight
    return min(max(value, low), high)


def _quantile(ordered: list[float], share: float) -> float:
    """The share-quantile of sorted values by linear interpolation between neighbours, numpy's
    default."""
    position = share * (len(ordered) - 1)
    below = floor(position)
    above = min(below + 1, len(ordered) - 1)
    return _between(ordered[below], ordered[above], position - below)


@beartype
@require(lambda values: len(values) > 0, "an interval needs at least one value")
@require(lambda values: _finite(values), "every value is a finite number")
@require(lambda level: 0.0 < level < 1.0, "a level lies strictly between 0 and 1")
@ensure(lambda result: result[0] <= result[1], "the lower end is not above the upper end")
@ensure(
    lambda result, values: min(values) <= result[0] and result[1] <= max(values),
    "the interval lies within the values",
)
@ensure(
    lambda result, values: len(values) != 1 or result == (values[0], values[0]),
    "one value is its own interval",
)
def percentile_interval(values: tuple[float, ...], level: float) -> tuple[float, float]:
    """The central level interval of values: their (1 - level) / 2 and (1 + level) / 2 quantiles,
    as a bootstrap's percentile interval is read. The upper end is never let below the lower,
    which the arithmetic promises and a float's rounding could otherwise break by a last bit."""
    ordered = sorted(values)
    low = _quantile(ordered, (1.0 - level) / 2)
    return low, max(low, _quantile(ordered, (1.0 + level) / 2))


def _median(values: tuple[float, ...]) -> float:
    """The middle value, or the mean of the two middle ones, each halved first so two large
    values never overflow."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return ordered[middle - 1] / 2 + ordered[middle] / 2


def _median_above_zero(values: tuple[float, ...]) -> bool:
    """Whether there are values and their median is above zero; a helper, so a broken condition's
    message, which icontract makes by evaluating every part of it, never takes the median of
    nothing."""
    return len(values) > 0 and _median(values) > 0.0


@beartype
@require(lambda cross: isfinite(cross) and cross >= 0.0, "a distance is finite and not negative")
@require(lambda baseline: len(baseline) > 0, "there is at least one real-real distance")
@require(lambda baseline: _finite(baseline), "every real-real distance is a finite number")
@require(lambda baseline: _median_above_zero(baseline), "the real-real median is above zero")
@ensure(lambda result: result >= 0.0, "a ratio of distances is not negative")
@ensure(
    lambda result, cross, baseline: cross != _median(baseline) or result == 1.0,
    "a distance equal to the real-real median is a ratio of one",
)
@ensure(lambda result, cross: cross != 0.0 or result == 0.0, "no distance is a ratio of zero")
def gap_ratio(cross: float, baseline: tuple[float, ...]) -> float:
    """A synthetic-real distance over the median distance between two real corpora: how many
    times further the synthetic set lies than real corpora lie from each other."""
    return cross / _median(baseline)


@beartype
@require(lambda auc_low: 0.0 <= auc_low <= 1.0, "an AUC bound is a probability")
@require(lambda real_real_median: 0.0 <= real_real_median <= 1.0, "a median AUC is a probability")
@ensure(lambda result: result in GAP_WORDS, "one of the pre-registered words")
@ensure(
    lambda result, auc_low: (result == GAP_WORDS[0]) == (auc_low <= INDISTINGUISHABLE_AUC),
    "indistinguishable exactly when the AUC's lower bound is at most 0.6",
)
@ensure(
    lambda result, auc_low, real_real_median: (
        (result == GAP_WORDS[1]) == (INDISTINGUISHABLE_AUC < auc_low < real_real_median)
    ),
    "closer than two real corpora exactly when separable but less than real corpora are",
)
def gap_word(auc_low: float, real_real_median: float) -> str:
    """The pre-registered word for a synthetic-real contrast, from its AUC's lower bound and the
    median AUC between two real corpora of the family."""
    if auc_low <= INDISTINGUISHABLE_AUC:
        return GAP_WORDS[0]
    if auc_low < real_real_median:
        return GAP_WORDS[1]
    return GAP_WORDS[2]


# --- the report line: what grid/redact.sed leaves alone -------------------------------------------
#
# Each pattern below is a rule of grid/redact.sed in Python's syntax (sed's [[:space:]] is \s under
# re.ASCII, and a rule sed runs twice for overlapping dates is one look-around search here). A
# line none of them matches passes the filter unchanged, since every rule of the filter acts only
# where its pattern matches.

_IGNORING_CASE = re.ASCII | re.IGNORECASE
_TAG = re.compile(r"\([0-9A-Fa-f]{4}, ?[0-9A-Fa-f]{4}\)", re.ASCII)
_ELEMENT = re.compile(
    r"Patient|Accession|Institution|Physician|Operators|StationName|DeviceSerial|InstanceUID"
    r"|StudyDate|SeriesDate|AcquisitionDate|ContentDate|StudyTime|StudyID|Invalid value for VR",
    _IGNORING_CASE,
)
_URL_USER = re.compile(r"://[^/@\s]+@", re.ASCII)
_SIGNED_QUERY = re.compile(
    r"[?&;](?:X-Amz-[A-Za-z-]+|Signature|signature|Sig|sig|token|access_token|auth|key|apikey"
    r"|api_key|Expires|Key-Pair-Id|Policy|Credential|code)=[^&\s\"']+",
    re.ASCII,
)
_SECRET_VALUE = re.compile(
    r"(?:password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization|cookie|credential)"
    r"s?[\"']?\s*[:=]\s*[\"']?[^\s\"',;]+",
    _IGNORING_CASE,
)
_PASSWORD_WORD = re.compile(r"\b(?:password|passwd)\s+\S+", _IGNORING_CASE)
_BEARER = re.compile(r"\b(?:Bearer|Basic|token)\s+[A-Za-z0-9._~+/=-]{8,}", _IGNORING_CASE)
_TOKEN_PREFIX = re.compile(
    r"\b(ghp_|gho_|ghs_|ghu_|ghr_|github_pat_|glpat-|xox[abprs]-|sk-)[A-Za-z0-9_-]{8,}", re.ASCII
)
_HF_TOKEN = re.compile(r"\bhf_[A-Za-z0-9]{20,}", re.ASCII)
_AWS_KEY = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", re.ASCII)
_PERSON_REFUSAL = re.compile(r"\bperson \S+ holds more than", re.ASCII)
_FIRST = re.compile(r"\(first [^)]*\)", re.ASCII)
_KEY_VALUE = re.compile(r"\b([a-z][a-z0-9_]*:)[A-Za-z0-9][^\s,;)'\"]*", re.ASCII)
_HEX_ID = re.compile(r"\b(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{40})\b", re.ASCII)
_UID = re.compile(r"\b[0-9]+(?:\.[0-9]+){4,}\b", re.ASCII)
_DATE = re.compile(
    r"(?<![0-9])(?:19|20)[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])(?![0-9])", re.ASCII
)
_QUOTED_DATE = re.compile(
    r"[\"'](?:19|20)[0-9]{2}-?(?:0[1-9]|1[0-2])-?(?:0[1-9]|[12][0-9]|3[01])(?:[T ][0-9:.]*)?[\"']",
    re.ASCII,
)
_INPUT_TYPE = re.compile(r"input_value=.*, input_type=[A-Za-z_]+\]", re.ASCII)
_INPUT_VALUE = re.compile(r"input_value=[^<]", re.ASCII)
_WAS = re.compile(r"^(\s*[A-Za-z_][A-Za-z0-9_.]*(?:\[[^\]]*\])?) was ", re.ASCII)
_SED_RULES = (
    _TAG,
    _ELEMENT,
    _URL_USER,
    _SIGNED_QUERY,
    _SECRET_VALUE,
    _PASSWORD_WORD,
    _BEARER,
    _TOKEN_PREFIX,
    _HF_TOKEN,
    _AWS_KEY,
    _PERSON_REFUSAL,
    _FIRST,
    _KEY_VALUE,
    _HEX_ID,
    _UID,
    _DATE,
    _QUOTED_DATE,
    _INPUT_TYPE,
    _INPUT_VALUE,
    _WAS,
)
_RUN = re.compile(r"[A-Za-z0-9_+=-]{32,}", re.ASCII)
_TRAILING_WORD = re.compile(r"[A-Za-z0-9_]+\Z", re.ASCII)
# The words a rule keys on are split by a space two characters in (three for "(first"), a space
# because it can lengthen no run and starts no rule; the colon of a word:value gets one after it.
_WORD_SPLITS = (
    (_URL_USER, 1),
    (_TAG, 1),
    (_ELEMENT, 2),
    (_SECRET_VALUE, 2),
    (_PASSWORD_WORD, 2),
    (_BEARER, 2),
    (_PERSON_REFUSAL, 2),
    (_FIRST, 3),
)
_SPACES = "\t\n\r\x0b\x0c"
_SCAN = 4 * LINE_LIMIT
_ROUNDS = 8
_NOT_SHOWN = "[a line not shown, since it could not be made safe for the report]"


def _printable(text: str) -> str:
    """Printable ASCII only: a tab or a line break becomes a space, anything else a question
    mark, so the line stays one line and shows where something was."""
    return "".join(c if " " <= c <= "~" else " " if c in _SPACES else "?" for c in text)


def _survives(line: str) -> bool:
    """Whether a line is a safe report line: printable, short, no "=", no long run, and matched
    by no rule of grid/redact.sed."""
    if len(line) > LINE_LIMIT or "=" in line or _RUN.search(line):
        return False
    if not all(" " <= c <= "~" for c in line):
        return False
    return not any(rule.search(line) for rule in _SED_RULES)


def _with_space(text: str, at: int) -> str:
    return f"{text[:at]} {text[at:]}"


def _space_in(line: str, pattern: re.Pattern[str], at: int) -> str:
    """Every match of the pattern with a space put in at characters from its start."""
    return pattern.sub(lambda match: _with_space(match.group(0), at), line)


def _space_after_head(line: str, pattern: re.Pattern[str]) -> str:
    """Every match with a space put in after its first group, the part the rule keys on."""
    return pattern.sub(
        lambda match: _with_space(match.group(0), match.end(1) - match.start()), line
    )


def _short_runs(line: str) -> str:
    """Every run of 32 or more word characters, plus and minus cut to its first 31."""
    return _RUN.sub(lambda match: match.group(0)[:RUN_LIMIT], line)


def _settled(line: str, fix: Callable[[str], str]) -> str:
    """A fix applied until it changes nothing more: a split can make a new match for its own rule
    (a prefix split opens a second prefix in its tail, a word split joins two words another rule
    keys on). The rounds are bounded, so a line that never settles still ends, and safe_line then
    sends the line that says it is not shown."""
    for _ in range(_SCAN):
        fixed = fix(line)
        if fixed == line:
            break
        line = fixed
    return line


def _prefixes_split(line: str) -> str:
    """A space after every token prefix the filter keys on: GitHub's, Slack's, OpenAI's, Hugging
    Face's and AWS's."""
    line = _space_after_head(line, _TOKEN_PREFIX)
    line = _space_in(line, _HF_TOKEN, 3)
    return _space_in(line, _AWS_KEY, 4)


def _words_split(line: str) -> str:
    """A space after the colon of every word:value, and in every word a rule keys on."""
    line = _space_after_head(line, _KEY_VALUE)
    for pattern, at in _WORD_SPLITS:
        line = _space_in(line, pattern, at)
    return line


def _dots_spaced(number: str) -> str:
    """A dotted number with a space after every fourth dot, so no part has five numbers."""
    first, *rest = number.split(".")
    return first + "".join(
        (". " if place % 4 == 0 else ".") + part for place, part in enumerate(rest, start=1)
    )


def _one_pass(line: str) -> str:
    """The rules' fixes, each a space put in, in an order where a later fix seldom makes a match
    an earlier one took away: the dates first, since a date's space can end an AWS key; then the
    token prefixes, since a prefix ending in an underscore can hide a word another rule keys on
    behind it; then the words, then the dotted numbers, which a prefix's space can start. What
    an order cannot settle, a word split ending an AWS key, the next pass does."""
    line = _short_runs(line.replace("=", " "))
    line = _space_in(_space_in(line, _DATE, 4), _QUOTED_DATE, 1)
    line = _settled(_settled(line, _prefixes_split), _words_split)
    line = _UID.sub(lambda match: _dots_spaced(match.group(0)), line)
    return _space_after_head(line, _WAS)


def _cut(line: str) -> str:
    """A line over the limit cut to it and back to the end of a word, so the cut leaves no word
    or number whose end the cut itself made, which a rule bounded by its end could match."""
    if len(line) <= LINE_LIMIT:
        return line
    return _TRAILING_WORD.sub("", line[:LINE_LIMIT])


@beartype
@ensure(lambda result: len(result) <= LINE_LIMIT, "a report line is at most 200 characters")
@ensure(lambda result: all(" " <= c <= "~" for c in result), "printable ASCII only")
@ensure(lambda result: "=" not in result, "no key=value is left")
@ensure(lambda result: not _RUN.search(result), "no run of 32 word characters, plus or minus")
@ensure(lambda result: _survives(result), "grid/redact.sed leaves the line as it is")
@ensure(
    lambda result, text: result == text or not _survives(text),
    "a line that is safe already is kept whole",
)
def safe_line(text: str) -> str:
    """One report line that passes grid/redact.sed unchanged, so the number it carries reaches
    the bench report: printable ASCII, at most 200 characters, a space after the colon of every
    word:value and in place of every "=", runs of 32 or more word characters cut to 31, a space
    after the year of a date written as eight digits, and the words the filter keys on split by
    a space (pa tient, to ken). A line no fix can make safe, which the tests have not found, is
    replaced by a line that says so, never sent as it is."""
    line = _printable(text[:_SCAN])
    for _ in range(_ROUNDS):
        if _survives(line):
            return line
        line = _cut(_one_pass(line))
    return line if _survives(line) else _NOT_SHOWN
