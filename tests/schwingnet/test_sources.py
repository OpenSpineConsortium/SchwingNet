"""The inventory's rules, and the page against the records (docs/research/datasets-inventory.md)."""

import importlib.util
import json
from pathlib import Path

import pytest
from icontract import ViolationError
from pydantic import ValidationError

from schwingnet.sources import (
    GROUP_TITLES,
    REACH_WORDS,
    Group,
    Reach,
    Source,
    bar,
    counts_cell,
    escape_cell,
    format_number,
    table_row,
    tally,
)

ROOT = Path(__file__).resolve().parents[2]


def test_a_cell_never_breaks_its_row() -> None:
    assert escape_cell("a | b\nc") == "a / b c"


def test_a_count_prints_with_thousands_and_a_size_keeps_its_decimals() -> None:
    assert format_number(375618) == "375,618"
    assert format_number(86.834) == "86.834"
    assert format_number(203.0) == "203"


def test_a_negative_count_is_refused() -> None:
    with pytest.raises(ViolationError):
        format_number(-1)


def test_counts_read_as_english_and_an_empty_record_prints_nothing() -> None:
    assert counts_cell({"spot_frames": 299, "size_gb": 86.834}) == "spot frames 299, size gb 86.834"
    assert counts_cell({}) == ""


def test_a_negative_count_in_a_record_is_refused() -> None:
    with pytest.raises(ViolationError):
        counts_cell({"frames": -1})
    with pytest.raises(ValidationError):
        Source.model_validate({"id": "x", "name": "x", "group": "ct", "what": "x", "level_truth": "x",
                               "reach": "held", "status": "x", "licence": "x", "counts": {"frames": -1}})


def test_a_tally_names_every_reach_and_loses_no_source() -> None:
    counted = tally((Reach.HELD, Reach.HELD, Reach.GET))
    assert counted[Reach.HELD] == 2 and counted[Reach.GET] == 1 and counted[Reach.NONE] == 0
    assert set(counted) == set(Reach)


def test_a_bar_is_as_wide_as_asked() -> None:
    assert bar(1, 4, 8) == "##......"
    assert bar(0, 0, 3) == "..."
    with pytest.raises(ViolationError):
        bar(5, 4, 8)


def test_a_row_is_fenced_and_escaped() -> None:
    assert table_row(("a", "b|c")) == "| a | b/c |"


def test_every_reach_has_a_word_and_every_group_a_title() -> None:
    assert set(REACH_WORDS) == set(Reach)
    assert set(GROUP_TITLES) == set(Group)


def test_a_record_needs_its_fields_and_a_known_reach() -> None:
    with pytest.raises(ValidationError):
        Source.model_validate({"id": "x", "name": "x", "group": "ct", "what": "x", "level_truth": "x",
                               "reach": "maybe", "status": "x", "licence": "x"})
    with pytest.raises(ValidationError):
        Source.model_validate({"id": "Not-An-Id"})


def test_every_record_on_disk_is_a_source_named_by_its_file() -> None:
    folder = ROOT / "data" / "sources"
    files = sorted(folder.glob("*.json"))
    assert files, "the registry holds records"
    for path in files:
        raw = path.read_bytes()
        assert raw.isascii() and b"\r" not in raw, f"{path.name}: ASCII with LF endings"
        source = Source.model_validate(json.loads(raw.decode("ascii")))
        assert source.id == path.stem
        if source.reach in (Reach.GET, Reach.GATED, Reach.EMBARGOED):
            assert source.how_to_get, f"{path.name}: a source not held says how to get it"


def test_the_page_is_what_the_records_render() -> None:
    spec = importlib.util.spec_from_file_location("sources_tool", ROOT / "tools" / "sources.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    page = ROOT / "docs" / "research" / "datasets-inventory.md"
    assert tool.render(tool.load(ROOT / "data" / "sources")) == page.read_text(encoding="ascii"), (
        "docs/research/datasets-inventory.md is out of date: run pixi run --locked python tools/sources.py render"
    )
