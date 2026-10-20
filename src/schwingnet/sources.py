"""The rules of the dataset inventory, which tools/sources.py renders from data/sources/.

Every number on docs/research/datasets-inventory.md is a record's number: a source is one JSON
record under data/sources/ (what it is, its level truth, its reach, its status, its licence, its
link, the steps to get it, its grid path, the counts the record states, and the fields a grid job
fills), the page is generated from the records, and the check fails when the two differ. The reading
and writing live in tools/sources.py; what is here is pure, so the gate proves it: the record's
shape at the boundary (pydantic), and the small rules the renderer rests on, a table cell that
cannot break its row, a number printed the way the record prints it, a tally that loses no source,
and a bar whose width is what was asked for.
"""

from enum import StrEnum
from typing import Annotated

from beartype import beartype
from beethoven_qa.contracts import ensure, require
from pydantic import BaseModel, Field

NonNegative = Annotated[int | float, Field(ge=0)]


class Reach(StrEnum):
    """How far the project reaches: on the grid, fetchable, gated, embargoed, nowhere, set aside."""

    HELD = "held"
    GET = "get"
    GATED = "gated"
    EMBARGOED = "embargoed"
    NONE = "none"
    EXCLUDED = "excluded"


class Group(StrEnum):
    """The six tables of the page, in the order they are printed."""

    FLUORO = "fluoro"
    VIDEO = "video"
    PROJECTIONS = "projections"
    FILMS = "films"
    CT = "ct"
    FUTURE = "future"


REACH_WORDS: dict[Reach, str] = {
    Reach.HELD: "HAVE",
    Reach.GET: "GET",
    Reach.GATED: "GATED",
    Reach.EMBARGOED: "EMBARGOED",
    Reach.NONE: "NONE",
    Reach.EXCLUDED: "EXCLUDED",
}

GROUP_TITLES: dict[Group, str] = {
    Group.FLUORO: "Real intraoperative fluoroscopy, stills (the target domain)",
    Group.VIDEO: "Video and cine (consecutive frames)",
    Group.PROJECTIONS: "Real projections with a registered CT (the COBRA kind)",
    Group.FILMS: "Plain films (lateral or AP radiographs)",
    Group.CT: "CT collections and their renders (3D truth, synthetic 2D)",
    Group.FUTURE: "Future directions",
}


class Source(BaseModel):
    """One record of data/sources/<id>.json, the boundary where a file becomes a row."""

    id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    group: Group
    what: str = Field(min_length=1)
    level_truth: str = Field(min_length=1)
    reach: Reach
    status: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    link: str | None = None
    how_to_get: list[str] = []
    grid_path: str | None = None
    counts: dict[str, NonNegative] = {}
    measured: dict[str, NonNegative] = {}
    record: str = ""


@beartype
@ensure(
    lambda result: "|" not in result and "\n" not in result and "\r" not in result,
    "a cell never breaks its row",
)
def escape_cell(text: str) -> str:
    """A table cell: a pipe would end the cell and a line break the row, so each becomes a space."""
    return text.replace("|", "/").replace("\r", " ").replace("\n", " ")


@beartype
@require(lambda value: value >= 0, "the record counts things; a count is never negative")
@ensure(lambda result: len(result) > 0, "a number prints as something")
def format_number(value: int | float) -> str:
    """A count as the record prints it: thousands separated, a size with its decimals kept."""
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.3f}".rstrip("0").rstrip(".")


@beartype
@require(lambda counts: all(value >= 0 for value in counts.values()), "the record counts things")
@ensure(
    lambda counts, result: (len(counts) == 0) == (result == ""),
    "an empty record prints an empty cell, a counted one prints every count",
)
def counts_cell(counts: dict[str, int | float]) -> str:
    """Every count of a record in one cell, the key read as English (spot_frames: spot frames)."""
    parts = [f"{key.replace('_', ' ')} {format_number(value)}" for key, value in counts.items()]
    return ", ".join(parts)


@beartype
@ensure(lambda reaches, result: sum(result.values()) == len(reaches), "a tally loses no source")
def tally(reaches: tuple[Reach, ...]) -> dict[Reach, int]:
    """How many sources stand at each reach, every reach present so the bars line up."""
    counted = {reach: 0 for reach in Reach}
    for reach in reaches:
        counted[reach] += 1
    return counted


@beartype
@require(lambda count, total: 0 <= count <= total, "a part is never more than its whole")
@require(lambda width: width > 0, "a bar has a width")
@ensure(lambda result, width: len(result) == width, "the bar is as wide as asked")
def bar(count: int, total: int, width: int) -> str:
    """A text bar of the share count takes of total, filled with # and padded with . to width.

    Integer arithmetic, rounding half up, so the postcondition holds for any width.
    """
    filled = 0 if total == 0 else (2 * width * count + total) // (2 * total)
    return "#" * filled + "." * (width - filled)


@beartype
@require(lambda cells: len(cells) > 0, "a row has at least one cell")
@ensure(lambda result: result.startswith("| ") and result.endswith(" |"), "a row is fenced")
def table_row(cells: tuple[str, ...]) -> str:
    """One Markdown table row, every cell escaped so the row stays one line."""
    return "| " + " | ".join(escape_cell(cell) for cell in cells) + " |"
