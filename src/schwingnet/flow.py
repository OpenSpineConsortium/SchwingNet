"""The rules of a run: what a result row must carry, and what the jobs cost.

REFORMS (beethoven-research, BUILD_PLAN section 16): every result row carries n, a 95 percent
interval, the run id, the commit and the clean-tree flag, and a row from a dirty tree is refused.
These models and functions are those rules as code the gate proves: the run record is the
boundary where the runner's facts are read, the interval is the eval gate's Wilson rule, and the
spend is summed from the jobs' own records, never typed. tools/flow.py runs the steps and
writes the record; nothing here reads a file, starts a process or asks the clock.
"""

import hashlib
import math
from enum import StrEnum
from typing import Annotated

from beartype import beartype
from beethoven_qa.contracts import ensure, require
from pydantic import BaseModel, ConfigDict, Field, model_validator

HexDigest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Commit = Annotated[str, Field(pattern=r"^[0-9a-f]{7,40}$")]
Instant = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]
RUN_ID_LENGTH = 12
HEX = frozenset("0123456789abcdef")


def _is_hex(text: str) -> bool:
    """Hex digits only, checked on the result; the inputs are ASCII, which the hash needs."""
    return all(c in HEX for c in text)


class Step(StrEnum):
    """The steps of the flow, in the order they run; each is one job."""

    BUILD = "build"
    SPLIT_CHECK = "split-check"
    TRAIN = "train"
    EVALUATE = "evaluate"


STEPS: tuple[Step, ...] = (Step.BUILD, Step.SPLIT_CHECK, Step.TRAIN, Step.EVALUATE)


class Stage(StrEnum):
    """The model stages of docs/research/retraining-plan.md, section 3.4."""

    DETECTOR = "detector"
    ENCODER = "encoder"
    HEAD = "head"
    LEVEL = "level"


class JobClass(StrEnum):
    """hpcworker's job classes (issue #77): the site profile gives each its partitions and QoS."""

    CPU = "cpu"
    BATCH = "batch"
    GPU = "gpu"


class JobSpec(BaseModel):
    """What one step asks the scheduler for; the batch script is rendered from it.

    A step names a class and never a QoS: hpcworker's job submit takes the partitions, the QoS and
    the GPU request from the site profile, since a QoS guessed here was refused (issue #74).
    partition, when given, narrows the class to one of its own partitions.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: Step
    command: str = Field(min_length=1)
    job_class: JobClass
    partition: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.-]{1,64}$")
    cpus: int = Field(ge=1, le=256)
    memory_gb: int = Field(ge=1, le=2048)
    gpus: int = Field(ge=0, le=8)
    hours: Annotated[float, Field(gt=0, le=168)]
    environment: str = Field(pattern=r"^[a-z0-9-]+$")


class JobRecord(BaseModel):
    """What one job cost, as the scheduler and the runner recorded it, never estimated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step: Step
    job_id: str = Field(min_length=1)
    partition: str = Field(min_length=1)
    qos: str | None = None
    hours_requested: Annotated[float, Field(gt=0)]
    seconds_used: int = Field(ge=0)
    gpus: int = Field(ge=0)
    preemptions: int = Field(ge=0)
    exit_code: int


class RunRecord(BaseModel):
    """RUN.json of a run: the facts every result row of the run cites.

    A dirty tree is refused at the boundary, so no number can be written against code git does
    not hold; the catalog version is named by its sha256, so two runs that cite the same hash
    read the same bytes. A run that names the sha256 of its configuration is named by it and by
    the digest of the code it runs (configured_run_id, tools/run_code.py), so the same
    configuration of the same code on the same catalog is always the same run, and a cut-short
    run can be carried on in its own folder on any later commit that changed none of that code;
    the commit it cites is the one it started on. A record without a configuration was written
    before configurations were named, and its id is still the hash of its start (run_id), so every
    RUN.json written before keeps validating.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    code_commit: Commit
    clean_tree: bool
    catalog_version: int = Field(ge=1)
    catalog_sha256: HexDigest
    split_disjoint: bool
    stage: Stage
    seed: int = Field(ge=0)
    epochs: int = Field(ge=1)
    parent_weights: HexDigest | None = None
    configuration_sha256: HexDigest | None = None
    code_sha256: HexDigest | None = None
    started_at: Instant
    mode: str = Field(pattern=r"^(local|slurm)$")
    jobs: tuple[JobRecord, ...] = ()

    @model_validator(mode="after")
    def _trustworthy(self) -> "RunRecord":
        """A run cites a clean tree and a disjoint split, or it is no run."""
        if not self.clean_tree:
            raise ValueError("a run from a dirty tree is refused")
        if not self.split_disjoint:
            raise ValueError("a run on a split that is not disjoint is refused")
        if self.configuration_sha256 is not None:
            if self.code_sha256 is None:
                raise ValueError("a run named by its configuration names the code it runs too")
            named = configured_run_id(
                self.code_sha256, self.catalog_sha256, self.configuration_sha256
            )
            if self.run_id != named:
                raise ValueError(
                    "the run id is not the hash of its code, catalog and configuration"
                )
        elif self.code_sha256 is not None:
            raise ValueError("a run named by its start names no code")
        elif self.run_id != run_id(self.code_commit, self.catalog_sha256, self.started_at):
            raise ValueError("the run id is not the hash of its commit, catalog and start")
        return self


@beartype
@require(
    lambda commit: 7 <= len(commit) <= 40 and commit.isascii(), "a commit is 7 to 40 hex digits"
)
@require(lambda catalog_sha256: len(catalog_sha256) == 64 and catalog_sha256.isascii(), "a sha256")
@require(lambda started_at: len(started_at) == 20 and started_at.isascii(), "YYYY-MM-DDTHH:MM:SSZ")
@ensure(lambda result: len(result) == RUN_ID_LENGTH, "a run id is twelve hex digits")
@ensure(lambda result: _is_hex(result), "a run id is hex")
def run_id(commit: str, catalog_sha256: str, started_at: str) -> str:
    """The name of a run recorded before configurations were named: a hash of what it ran on and
    when, so no two such runs share one. tools/flow.py names every run since by configured_run_id;
    this one stays so that the records written before keep validating."""
    text = f"{commit}\n{catalog_sha256}\n{started_at}\n"
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:RUN_ID_LENGTH]


# The three digests are held to 64 ASCII characters, and not to hex: CrossHair 0.0.111 met no hex
# form of these preconditions within the gate's 20 s (a regular expression, a test of each
# character, sets, 2026-10-24), and it meets the ASCII form in only some runs (two of three,
# 2026-10-25), so the function is listed under [tool.beethoven-qa.unproven] in pyproject.toml.
# RunRecord's HexDigest holds each digest to hex where it is recorded.
@beartype
@require(lambda code_sha256: len(code_sha256) == 64 and code_sha256.isascii(), "the code's sha256")
@require(lambda catalog_sha256: len(catalog_sha256) == 64 and catalog_sha256.isascii(), "a sha256")
@require(
    lambda configuration_sha256: len(configuration_sha256) == 64 and configuration_sha256.isascii(),
    "the configuration's sha256",
)
@ensure(lambda result: len(result) == RUN_ID_LENGTH, "a run id is twelve hex digits")
@ensure(lambda result: _is_hex(result), "a run id is hex")
def configured_run_id(code_sha256: str, catalog_sha256: str, configuration_sha256: str) -> str:
    """The run's name from what it ran: its code's digest, the catalog and the configuration.

    No clock enters it, and no commit: the code is the digest of the files a run executes
    (tools/run_code.py), so a run started again with the same configuration on the same catalog
    finds its own folder and carries on what is done there instead of training a second time
    beside it, also after main has merged anything that changed none of those files. The first
    line says code, and the third configuration where a legacy id's third line is an instant, so
    the text hashed here is never the text run_id hashes.
    """
    text = f"code {code_sha256}\n{catalog_sha256}\nconfiguration {configuration_sha256}\n"
    return hashlib.sha256(text.encode("ascii")).hexdigest()[:RUN_ID_LENGTH]


@beartype
@require(lambda total: total > 0, "an interval needs at least one case")
@require(lambda correct, total: 0 <= correct <= total, "correct cases are a part of the total")
@require(lambda z: 0 < z <= 10, "z is a positive normal quantile")
@ensure(lambda result: 0.0 <= result[0] <= result[1] <= 1.0, "the bounds are ordered fractions")
@ensure(
    lambda result, correct, total: result[0] <= correct / total <= result[1],
    "the interval holds the point estimate",
)
def wilson(correct: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """The Wilson score interval, the eval gate's rule for every reported fraction."""
    p = correct / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    low = max(0.0, centre - half)
    high = min(1.0, centre + half)
    return (min(low, p), max(high, p))


@beartype
@ensure(lambda result: result >= 0.0, "hours are never negative")
def gpu_hours(jobs: tuple[JobRecord, ...]) -> float:
    """What the run spent on GPUs: the sum over its jobs of GPUs times seconds, in hours."""
    return sum(job.gpus * job.seconds_used for job in jobs) / 3600.0


@beartype
@ensure(lambda result: result >= 0.0, "hours are never negative")
def wall_hours(jobs: tuple[JobRecord, ...]) -> float:
    """How long the run's jobs ran in all, in hours."""
    return sum(job.seconds_used for job in jobs) / 3600.0


class ResultRow(BaseModel):
    """One reported number: a fraction with its interval and the facts that reproduce it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    measure: str = Field(min_length=1)
    stratum: str = Field(min_length=1)
    correct: int = Field(ge=0)
    total: int = Field(ge=1)
    persons: int = Field(ge=1)
    run_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    code_commit: Commit
    clean_tree: bool
    catalog_sha256: HexDigest

    @model_validator(mode="after")
    def _reportable(self) -> "ResultRow":
        """A row is at most its total and never from a dirty tree."""
        if self.correct > self.total:
            raise ValueError("correct cases are a part of the total")
        if not self.clean_tree:
            raise ValueError("a row from a dirty tree is refused")
        return self


@beartype
@ensure(lambda result: result.startswith("| "), "a ledger row is a Markdown table row")
@ensure(lambda result: result.count("|") == 10, "a ledger row has nine cells")
@ensure(lambda result: "\n" not in result, "a ledger row is one line")
def ledger_row(record: RunRecord, activity: str, verified: str) -> str:
    """One line of the ledger: what ran, on what, what it cost, and how it was verified."""
    cells = (
        record.started_at[:10],
        record.run_id,
        record.mode,
        activity.replace("|", "/").replace("\n", " "),
        record.code_commit[:12],
        f"catalog {record.catalog_version} {record.catalog_sha256[:12]}",
        f"{wall_hours(record.jobs):.2f} h wall, {gpu_hours(record.jobs):.2f} GPU h",
        str(len(record.jobs)),
        verified.replace("|", "/").replace("\n", " "),
    )
    return "| " + " | ".join(cells) + " |"


@beartype
@require(lambda row: row.total >= 1, "a result row has cases")
@ensure(lambda result: result.count("|") == 10, "a result line has nine cells")
def result_line(row: ResultRow) -> str:
    """One line of the result table: the fraction, its interval and its stamp."""
    low, high = wilson(row.correct, row.total)
    cells = (
        row.measure,
        row.stratum,
        f"{row.correct}/{row.total}",
        f"{row.correct / row.total:.3f}",
        f"{low:.3f} to {high:.3f}",
        str(row.persons),
        row.run_id,
        row.code_commit[:12],
        "clean",
    )
    return "| " + " | ".join(cells) + " |"
