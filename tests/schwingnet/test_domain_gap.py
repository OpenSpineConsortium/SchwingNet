"""The DRR domain-gap study's pure rules (schwingnet.domain_gap): the group table, who a file
belongs to, which files a group gives the study, the separation statistics' arithmetic, and the
report line that grid/redact.sed must leave as it is.

The report line is checked against the filter itself: thousands of lines built from the words,
shapes and punctuation the filter keys on are made safe and run through `sed -r -f
grid/redact.sed`, as grid/gate.sh's status runs it, and every one must come back unchanged.
"""

import hashlib
import random
import string
import subprocess
from fractions import Fraction
from math import floor, inf, nan
from pathlib import Path
from typing import Any

import pytest
from beartype.roar import BeartypeCallHintParamViolation
from icontract import ViolationError
from pydantic import ValidationError

from schwingnet import domain_gap as gap
from schwingnet.witness import rank

ROOT = Path(__file__).resolve().parents[2]
REDACT = ROOT / "grid" / "redact.sed"
SALT = "schwingnet-drr-gap-v1"


# --- the group table ---------------------------------------------------------------------------


def film(**fields: Any) -> dict[str, Any]:
    """A real film group read from the sample index, with fields replaced as given."""
    row: dict[str, Any] = {
        "id": "vindr_spinexr",
        "label": "VinDr-SpineXR",
        "family": "film",
        "source": "index",
        "index_sources": ["vindr_spinexr"],
        "person": "dicom:patient",
    }
    row.update(fields)
    return row


RENDER = {
    "id": "flexray_raw",
    "label": "FleXray raw DRRs",
    "family": "synthetic",
    "source": "render",
    "folder": "totalsegmentator_v201",
    "person": r"regex:^(?P<person>[^/]+?)__r\d+",
    "cap": 1000,
    "per_person": 4,
}


def render(**fields: Any) -> dict[str, Any]:
    """A render group, FleXray's recipe through this project's blocks, with fields replaced."""
    row = dict(RENDER)
    row.update(fields)
    return row


def table(*groups: dict[str, Any], **fields: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"version": 1, "salt": SALT, "groups": list(groups)}
    row.update(fields)
    return row


def test_a_table_of_two_families_reads_with_its_defaults() -> None:
    parsed = gap.GroupTable.model_validate(table(film(), RENDER))
    vindr, flexray = parsed.groups
    assert (vindr.cap, vindr.per_person, vindr.min_side) == (1000, 4, 256)
    assert vindr.exclude_words == ("mask", "label", "seg", "crop", "preview", "thumb", "overlay")
    assert (vindr.globs, vindr.formats, vindr.modalities, vindr.folder) == ((), (), (), "")
    assert (vindr.blocks, vindr.engine, vindr.subjects_from) == ((), "blocks", "")
    assert flexray.family == "synthetic" and flexray.source in gap.SYNTHETIC_SOURCES
    assert (flexray.blocks, flexray.engine, flexray.subjects_from) == ((), "blocks", "")
    again = gap.GroupTable.model_validate_json(parsed.model_dump_json())
    assert again == parsed


# --- render groups: blocks, engine and shared subjects ----------------------------------------


def test_a_render_group_reads_its_blocks_engine_and_shared_subjects() -> None:
    physical = gap.GroupSpec.model_validate(render(blocks=["attenuation=off"]))
    assert (physical.blocks, physical.engine, physical.subjects_from) == (
        ("attenuation=off",),
        "blocks",
        "",
    )
    reference = gap.GroupSpec.model_validate(
        render(id="flexray_reference", engine="flexray-runtime", subjects_from="flexray_raw")
    )
    assert (reference.engine, reference.subjects_from) == ("flexray-runtime", "flexray_raw")
    two_views = gap.GroupSpec.model_validate(render(blocks=["views=2"], per_person=2))
    assert two_views.per_person == 2
    # The segmenter is a block like any other: MOOSE's masks for a replication of FleXray's
    # dataset, the project's SPINEPS when no word names one; TotalSegmentator is no value.
    moose = gap.GroupSpec.model_validate(
        render(blocks=["segmenter=moose"], engine="flexray-runtime")
    )
    assert moose.blocks == ("segmenter=moose",)


@pytest.mark.parametrize(
    ("fields", "says"),
    [
        ({"per_person": 2}, "views"),
        ({"blocks": ["views=2"]}, "views"),
        ({"blocks": ["detector=abc"]}, "blocks"),
        ({"blocks": ["colour=red"]}, "blocks"),
        ({"blocks": ["segmenter=totalsegmentator"]}, "segmenter"),
        ({"blocks": ["attenuation=off", "attenuation=off"]}, "twice"),
        ({"blocks": ["isocentre=vertebra"], "engine": "flexray-runtime"}, "isocentre"),
        ({"engine": "nanodrr"}, "engine"),
        ({"subjects_from": "flexray_raw"}, "itself"),
        ({"subjects_from": "Bad Id"}, "pattern"),
    ],
)
def test_a_render_group_refuses_a_recipe_that_does_not_hold(
    fields: dict[str, Any], says: str
) -> None:
    with pytest.raises(ValidationError, match=says):
        gap.GroupSpec.model_validate(render(**fields))


def test_the_engines_are_the_render_blocks_engines() -> None:
    # The table reads an engine against the renderer's own list, so a third engine added there
    # is read here with no change.
    from schwingnet import render_blocks

    assert "blocks" in render_blocks.ENGINES and "flexray-runtime" in render_blocks.ENGINES
    for engine in render_blocks.ENGINES:
        assert render_blocks.engine_problems(engine, render_blocks.DEFAULT) == []


@pytest.mark.parametrize(
    "fields",
    [
        {"blocks": ["attenuation=off"]},
        {"engine": "flexray-runtime"},
        {"subjects_from": "flexray_raw"},
    ],
)
def test_blocks_an_engine_and_shared_subjects_are_a_render_groups_alone(
    fields: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="only for a render group"):
        gap.GroupSpec.model_validate(film(**fields))


def test_a_table_holds_shared_subjects_to_a_render_group_of_the_same_shape() -> None:
    replica = render(id="replica", subjects_from="flexray_raw")
    held = gap.GroupTable.model_validate(table(film(), RENDER, replica))
    assert held.groups[2].subjects_from == "flexray_raw"
    # A chain is no cycle: a from b, b from the first render group.
    chained = render(id="chained", subjects_from="replica")
    gap.GroupTable.model_validate(table(film(), RENDER, replica, chained))
    with pytest.raises(ValidationError, match="no render group"):
        gap.GroupTable.model_validate(
            table(film(), RENDER, render(id="replica", subjects_from="missing"))
        )
    with pytest.raises(ValidationError, match="no render group"):
        gap.GroupTable.model_validate(
            table(film(), RENDER, render(id="replica", subjects_from="vindr_spinexr"))
        )
    for other in ({"cap": 500}, {"folder": "other_cts"}, {"per_person": 2, "blocks": ["views=2"]}):
        with pytest.raises(ValidationError, match="folder, cap and per_person"):
            gap.GroupTable.model_validate(
                table(film(), RENDER, render(id="replica", subjects_from="flexray_raw", **other))
            )
    with pytest.raises(ValidationError, match="cycle"):
        gap.GroupTable.model_validate(
            table(film(), render(id="a", subjects_from="b"), render(id="b", subjects_from="a"))
        )


# FluXray's raw render stream as the paper gives it, every word spelled out so the record reads
# whole: MOOSE's labels, the whole volume drawn uniformly, one of the 90 fixed poses, the volume's
# centre, a cone beam, the attenuation randomisation off, min-max scaling, 4 views at 1024 pixels.
FLUXRAY_RAW_WORDS = (
    "segmenter=moose",
    "crop=whole",
    "crop_sampler=uniform",
    "pose=fluxray-grid",
    "isocentre=volume-centre",
    "projection=cone",
    "attenuation=off",
    "scale=minmax",
    "views=4",
    "detector=1024",
)
# The six render groups of the study's table: each one's blocks, engine and the group whose CTs it
# shares, and the pair its note says it isolates.
STUDY_RENDERS = {
    "flexray_drr": (("segmenter=moose", "attenuation=off"), "blocks", "", "flexray_replica"),
    "flexray_replica": (("segmenter=moose",), "blocks", "flexray_drr", "flexray_reference"),
    "flexray_reference": (
        ("segmenter=moose",),
        "flexray-runtime",
        "flexray_drr",
        "flexray_replica",
    ),
    "flexray_spineps": ((), "blocks", "flexray_drr", "flexray_replica"),
    "fluxray_raw": (FLUXRAY_RAW_WORDS, "blocks", "flexray_drr", "fluxray_raw_reference"),
    "fluxray_raw_reference": (FLUXRAY_RAW_WORDS, "flexray-runtime", "flexray_drr", "fluxray"),
}


def test_the_studys_own_table_holds_and_names_the_six_render_groups() -> None:
    from dataclasses import replace

    from schwingnet import render_blocks

    parsed = gap.GroupTable.model_validate_json(
        (ROOT / "data" / "domain_gap" / "groups.json").read_text(encoding="utf-8")
    )
    renders = {g.id: g for g in parsed.groups if g.source == "render"}
    assert {i: (g.blocks, g.engine, g.subjects_from) for i, g in renders.items()} == {
        i: (blocks, engine, shares) for i, (blocks, engine, shares, _) in STUDY_RENDERS.items()
    }
    for i, (_, _, _, pair) in STUDY_RENDERS.items():
        assert pair in renders[i].note, i
    # The recipes are the presets they stand for: FleXray's with MOOSE's labels (its own), the
    # same with the attenuation randomisation off, the project's default (SPINEPS) and FluXray's
    # raw render stream; and the folder names both segmenters, so the CTs are chosen among those
    # with masks under both.
    assert render_blocks.parse(renders["flexray_replica"].blocks) == render_blocks.FLEXRAY
    assert render_blocks.parse(renders["flexray_reference"].blocks) == render_blocks.FLEXRAY
    assert render_blocks.parse(renders["flexray_drr"].blocks) == replace(
        render_blocks.PHYSICAL, segmenter="moose"
    )
    assert render_blocks.parse(renders["flexray_spineps"].blocks) == render_blocks.DEFAULT
    assert render_blocks.parse(renders["fluxray_raw"].blocks) == render_blocks.FLUXRAY_RAW
    assert gap.segmenters_named([g.blocks for g in renders.values()]) == ("moose", "spineps")
    assert len({(g.folder, g.cap, g.per_person, g.licence) for g in renders.values()}) == 1
    assert all(g.cap // g.per_person == 250 for g in renders.values())
    assert [g.id for g in parsed.groups[:7]] == [*STUDY_RENDERS, "fluxray"]
    assert len(parsed.groups) == 22


# --- the choice of CTs -------------------------------------------------------------------------


def test_the_segmenters_named_are_each_recipes_once_in_order() -> None:
    assert gap.segmenters_named([]) == ()
    assert gap.segmenters_named([()]) == ("spineps",)
    assert gap.segmenters_named([("segmenter=moose",), (), ("segmenter=moose", "views=2")]) == (
        "moose",
        "spineps",
    )
    with pytest.raises(ViolationError):
        gap.segmenters_named([("segmenter=totalsegmentator",)])
    with pytest.raises(ViolationError):
        gap.segmenters_named([(), ("colour=red",)])


def test_with_masks_keeps_the_subjects_every_segmenter_has_masks_for() -> None:
    subjects = frozenset({"s1", "s2", "s3", "s4"})
    masked = {
        "spineps": frozenset({"s1", "s2", "s3", "s9"}),
        "moose": frozenset({"s2", "s3", "s4"}),
    }
    assert gap.with_masks(subjects, masked) == {"s2", "s3"}
    assert gap.with_masks(subjects, {"spineps": masked["spineps"]}) == {"s1", "s2", "s3"}
    assert gap.with_masks(subjects, {}) == subjects
    assert gap.with_masks(subjects, {"moose": frozenset()}) == frozenset()
    assert gap.with_masks(frozenset(), masked) == frozenset()


def subject_order(salt: str, subject: str) -> tuple[str, str]:
    return gap.rank_key(f"{salt}:subjects", subject), subject


def test_a_choice_of_subjects_is_the_first_in_the_salted_order_with_every_mask() -> None:
    subjects = frozenset(f"s{n:04d}" for n in range(40))
    masked = {
        "spineps": frozenset(f"s{n:04d}" for n in range(0, 36)),
        "moose": frozenset(f"s{n:04d}" for n in range(4, 40)),
    }
    both = sorted(gap.with_masks(subjects, masked), key=lambda s: subject_order(SALT, s))
    assert len(both) == 32
    chosen = gap.choose_subjects(subjects, masked, 10, SALT)
    assert list(chosen) == both[:10]
    assert set(chosen) <= {f"s{n:04d}" for n in range(4, 36)}
    assert gap.choose_subjects(subjects, masked, 100, SALT) == tuple(both)
    assert gap.choose_subjects(subjects, masked, 0, SALT) == ()
    assert gap.choose_subjects(frozenset(), masked, 5, SALT) == ()
    # With no segmenter named, every subject is a candidate; the salt decides who comes first.
    assert set(gap.choose_subjects(subjects, {}, 40, SALT)) == subjects
    assert gap.choose_subjects(subjects, masked, 10, "other") != chosen
    assert gap.choose_subjects(subjects, masked, 10, "other") == tuple(
        sorted(both, key=lambda s: subject_order("other", s))[:10]
    )


def test_a_choice_of_subjects_refuses_a_count_below_zero_and_what_is_no_set() -> None:
    with pytest.raises(ViolationError):
        gap.choose_subjects(frozenset({"s1"}), {}, -1, SALT)
    with pytest.raises(BeartypeCallHintParamViolation):
        gap.choose_subjects(["s1"], {}, 1, SALT)
    with pytest.raises(BeartypeCallHintParamViolation):
        gap.choose_subjects(frozenset({"s1"}), {"spineps": ["s1"]}, 1, SALT)


def test_the_families_and_sources_are_the_studys() -> None:
    assert gap.FAMILIES == ("synthetic", "fluoroscopy", "film")
    assert gap.SOURCES == ("render", "thunderdb", "index", "walk")


@pytest.mark.parametrize(
    ("fields", "says"),
    [
        ({"id": "VinDr"}, "pattern"),
        ({"id": "x" * 41}, "pattern"),
        ({"label": "café"}, "pattern"),
        ({"label": "x" * 61}, "pattern"),
        ({"family": "ct"}, "family"),
        ({"source": "ftp"}, "source"),
        ({"source": "render", "folder": "ts", "person": "file"}, "synthetic"),
        ({"source": "thunderdb", "folder": "fx", "person": "file"}, "synthetic"),
        ({"index_sources": []}, "names its sources"),
        ({"source": "walk", "person": "file"}, "names it"),
        ({"source": "walk", "folder": "../etc", "person": "file"}, "under the data root"),
        ({"source": "walk", "folder": "/rs/data", "person": "file"}, "under the data root"),
        ({"source": "walk", "folder": "a\\b", "person": "file"}, "under the data root"),
        ({"person": "patient"}, "person rule"),
        ({"person": "dir:x"}, "person rule"),
        ({"person": "dir:1234"}, "person rule"),
        ({"person": "regex:(?P<who>x)"}, "person rule"),
        ({"person": "regex:("}, "person rule"),
        ({"source": "walk", "folder": "lumos"}, "DICOM"),
        ({"formats": ["jpg"]}, "formats"),
        ({"modalities": ["dx"]}, "modality"),
        ({"exclude_words": ["Mask"]}, "lower case"),
        ({"globs": [""]}, "empty"),
        ({"index_sources": [""]}, "empty"),
        ({"cap": 0}, "greater than or equal"),
        ({"cap": 5001}, "less than or equal"),
        ({"per_person": 0}, "greater than or equal"),
        ({"per_person": 101}, "less than or equal"),
        ({"min_side": -1}, "greater than or equal"),
        ({"note": "café"}, "pattern"),
        ({"licence": "x" * 2001}, "at most"),
        ({"weights": "x"}, "Extra inputs"),
    ],
)
def test_a_group_refuses_fields_that_do_not_hold_together(
    fields: dict[str, Any], says: str
) -> None:
    with pytest.raises(ValidationError, match=says):
        gap.GroupSpec.model_validate(film(**fields))


def test_a_table_refuses_a_repeated_id_one_family_and_another_version() -> None:
    with pytest.raises(ValidationError, match="named twice"):
        gap.GroupTable.model_validate(table(film(), film(), RENDER))
    with pytest.raises(ValidationError, match="two families"):
        gap.GroupTable.model_validate(table(film(), film(id="buu", index_sources=["buu"])))
    with pytest.raises(ValidationError):
        gap.GroupTable.model_validate(table(film(), RENDER, version=2))
    with pytest.raises(ValidationError):
        gap.GroupTable.model_validate(table(film()))
    with pytest.raises(ValidationError):
        gap.GroupTable.model_validate(table(film(), RENDER, salt=""))


def test_a_group_and_a_table_are_frozen() -> None:
    parsed = gap.GroupTable.model_validate(table(film(), RENDER))
    with pytest.raises(ValidationError):
        parsed.groups[0].cap = 10
    with pytest.raises(ValidationError):
        parsed.salt = "other"


# --- persons -----------------------------------------------------------------------------------


def test_a_patient_rule_gives_the_patient_id_without_its_padding() -> None:
    assert gap.person_key("dicom:patient", "a/b.dcm", "  P0123 ", "1.2.3") == "P0123"
    assert gap.person_key("dicom:patient", "a/b.dcm", "P0123\x00", "") == "P0123"


@pytest.mark.parametrize(
    "placeholder", ["", "   ", "ANONYMOUS", "Anonymous^", "0000", "0", "-", "^^", "n/a", "Unknown"]
)
def test_a_placeholder_patient_id_names_nobody(placeholder: str) -> None:
    assert gap.person_key("dicom:patient", "a/b.dcm", placeholder, "1.2.840.1") == ""


def test_a_study_rule_gives_the_study_uid() -> None:
    assert gap.person_key("dicom:study", "a/b.dcm", "P1", "1.2.840.10008.1 \x00") == (
        "1.2.840.10008.1"
    )
    assert gap.person_key("dicom:study", "a/b.dcm", "P1", "") == ""


def test_a_folder_rule_gives_a_whole_folder_and_never_the_file() -> None:
    relative = "case12/frames/f001.png"
    assert gap.person_key("dir:0", relative, "", "") == "case12"
    assert gap.person_key("dir:1", relative, "", "") == "frames"
    assert gap.person_key("dir:2", relative, "", "") == ""
    assert gap.person_key("dir:0", "./case12//f001.png", "", "") == "case12"
    assert gap.person_key("dir:0", "f001.png", "", "") == ""


def test_a_regex_rule_gives_its_person_group() -> None:
    rule = r"regex:^(?P<person>[^/]+?)__r\d+"
    assert gap.person_key(rule, "s0012__r03.npy", "", "") == "s0012"
    assert gap.person_key(rule, "s0012.npy", "", "") == ""
    assert gap.person_key("regex:(?P<person>x)?y", "y.png", "", "") == ""
    assert gap.person_key(r"regex:patient(?P<person>\d+)/", "lumos/patient7/a.dcm", "", "") == "7"


def test_a_file_rule_names_nobody_but_the_file() -> None:
    assert gap.person_key("file", "case12/f001.png", "P1", "1.2") == ""


@pytest.mark.parametrize(
    "rule",
    [
        "patient",
        "dir:",
        "dir:1234",
        "dir:٣",
        "dir:-1",
        "regex:(?P<who>x)",
        "regex:(",
        "regex:a{4294967296}",
        "dicom:series",
    ],
)
def test_a_person_rule_the_study_does_not_read_is_refused(rule: str) -> None:
    with pytest.raises(ViolationError):
        gap.person_key(rule, "a/b.png", "", "")


NOT_TEXT: tuple[Any, ...] = (None, "", "")


def test_a_person_key_refuses_what_is_not_text() -> None:
    with pytest.raises(BeartypeCallHintParamViolation):
        gap.person_key("file", *NOT_TEXT)


# --- the choice of files -----------------------------------------------------------------------


def test_a_rank_is_the_witness_frames_rank() -> None:
    for text in ("case12/f001.png", "vindr:abc", ""):
        assert gap.rank_key(SALT, text) == rank(SALT, text)
    assert gap.rank_key(SALT, "a") != gap.rank_key("other", "a")


def test_a_name_the_system_decoded_with_surrogates_is_ranked() -> None:
    name = "scan\udcff.png"
    expected = hashlib.sha256(f"{SALT}:{name}".encode("utf-8", "surrogatepass")).hexdigest()
    assert gap.rank_key(SALT, name) == expected


def in_turns(
    candidates: tuple[tuple[str, str], ...], cap: int, per_person: int, salt: str
) -> tuple[tuple[str, str], ...]:
    """The rule as a person reads it: turn by turn, every person in hash order gives its next
    file in hash order, until the cap."""
    files: dict[str, list[str]] = {}
    for file, person in candidates:
        files.setdefault(person, []).append(file)
    persons = sorted(files, key=lambda p: (gap.rank_key(salt, p), p))
    for person in persons:
        files[person].sort(key=lambda f: (gap.rank_key(salt, f), f))
    chosen: list[tuple[str, str]] = []
    for turn in range(per_person):
        for person in persons:
            if turn < len(files[person]) and len(chosen) < cap:
                chosen.append((files[person][turn], person))
    return tuple(chosen)


def pairs(sizes: dict[str, int]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (f"{person}/f{n:03d}.png", person) for person, size in sizes.items() for n in range(size)
    )


def test_a_choice_takes_every_person_once_before_anyone_twice() -> None:
    candidates = pairs({"a": 5, "b": 1, "c": 3})
    chosen = gap.choose(candidates, 6, 2, SALT)
    assert len(chosen) == 5
    assert {person for _, person in chosen[:3]} == {"a", "b", "c"}
    assert sorted(person for _, person in chosen) == ["a", "a", "b", "c", "c"]
    assert chosen == in_turns(candidates, 6, 2, SALT)


def test_a_cap_stops_the_choice_within_a_turn() -> None:
    candidates = pairs({"a": 3, "b": 3, "c": 3})
    chosen = gap.choose(candidates, 4, 3, SALT)
    counts = sorted(sum(1 for _, p in chosen if p == person) for person in "abc")
    assert counts == [1, 1, 2]
    assert chosen == in_turns(candidates, 4, 3, SALT)


def test_the_order_of_the_candidates_does_not_matter() -> None:
    candidates = list(pairs({"a": 4, "b": 7, "c": 2, "d": 9}))
    first = gap.choose(tuple(candidates), 10, 3, SALT)
    random.Random(4).shuffle(candidates)
    assert gap.choose(tuple(candidates), 10, 3, SALT) == first


def test_a_choice_is_the_turn_by_turn_rule_on_random_groups() -> None:
    rnd = random.Random(11)
    for _ in range(40):
        sizes = {f"p{n}": rnd.randint(1, 9) for n in range(rnd.randint(1, 12))}
        cap, per_person = rnd.randint(0, 60), rnd.randint(1, 6)
        candidates = pairs(sizes)
        assert gap.choose(candidates, cap, per_person, SALT) == in_turns(
            candidates, cap, per_person, SALT
        )


def test_the_salt_decides_who_comes_first() -> None:
    candidates = pairs({f"p{n}": 1 for n in range(30)})
    assert gap.choose(candidates, 5, 1, "one") != gap.choose(candidates, 5, 1, "two")


def test_nothing_offered_or_a_cap_of_zero_chooses_nothing() -> None:
    assert gap.choose((), 10, 4, SALT) == ()
    assert gap.choose(pairs({"a": 3}), 0, 4, SALT) == ()


def test_a_choice_refuses_a_file_twice_and_a_count_below_its_floor() -> None:
    with pytest.raises(ViolationError):
        gap.choose((("a.png", "p"), ("a.png", "q")), 5, 1, SALT)
    with pytest.raises(ViolationError):
        gap.choose(pairs({"a": 2}), 5, 0, SALT)
    with pytest.raises(ViolationError):
        gap.choose(pairs({"a": 2}), -1, 1, SALT)


# --- the separation statistics -----------------------------------------------------------------


def auc_by_pairs(positive: tuple[float, ...], negative: tuple[float, ...]) -> float:
    """The AUC by its definition: every pair counted, a tie one half, exactly."""
    wins = sum(
        Fraction(1) if p > n else Fraction(1, 2) if p == n else Fraction(0)
        for p in positive
        for n in negative
    )
    return float(wins / (len(positive) * len(negative)))


def test_an_auc_is_one_zero_or_one_half_at_the_extremes() -> None:
    assert gap.mann_whitney_auc((0.9, 0.8), (0.1, 0.2)) == 1.0
    assert gap.mann_whitney_auc((0.1, 0.2), (0.9, 0.8)) == 0.0
    assert gap.mann_whitney_auc((0.5,), (0.5,)) == 0.5
    assert gap.mann_whitney_auc((0.3, 0.3), (0.3, 0.3, 0.3)) == 0.5


def test_an_auc_is_the_share_of_pairs_a_positive_wins() -> None:
    positive, negative = (0.1, 0.4, 0.35, 0.8), (0.2, 0.4, 0.05)
    assert gap.mann_whitney_auc(positive, negative) == auc_by_pairs(positive, negative)
    rnd = random.Random(3)
    for _ in range(60):
        positive = tuple(rnd.choice((0.0, 0.25, 0.5, 0.75, 1.0)) for _ in range(rnd.randint(1, 30)))
        negative = tuple(rnd.random() for _ in range(rnd.randint(1, 30))) + (-0.0, 0.5)
        assert gap.mann_whitney_auc(positive, negative) == auc_by_pairs(positive, negative)


@pytest.mark.parametrize(
    ("positive", "negative"), [((), (0.1,)), ((0.1,), ()), ((nan,), (0.1,)), ((0.1,), (inf,))]
)
def test_an_auc_refuses_an_empty_side_and_a_score_that_is_no_number(
    positive: tuple[float, ...], negative: tuple[float, ...]
) -> None:
    with pytest.raises(ViolationError):
        gap.mann_whitney_auc(positive, negative)


def test_a_permutation_p_counts_the_observed_among_the_permuted() -> None:
    assert gap.permutation_p(0.9, (0.1, 0.95, 0.9)) == 0.75
    assert gap.permutation_p(5.0, (1.0, 2.0)) == 1 / 3
    assert gap.permutation_p(0.0, (0.0, 1.0)) == 1.0
    assert gap.permutation_p(inf, (1.0,) * 999) == 1 / 1000


def test_a_permutation_p_refuses_no_permutations_and_nan() -> None:
    with pytest.raises(ViolationError):
        gap.permutation_p(0.5, ())
    with pytest.raises(ViolationError):
        gap.permutation_p(nan, (0.1,))
    with pytest.raises(ViolationError):
        gap.permutation_p(0.5, (0.1, nan))


def bh_by_definition(pvalues: tuple[float, ...]) -> tuple[float, ...]:
    """Each adjusted p as the least p_j m / rank_j over the ps no smaller, capped at one."""
    count = len(pvalues)
    ranked = sorted(pvalues)
    return tuple(
        min(1.0, min(ranked[j] * count / (j + 1) for j in range(count) if ranked[j] >= p))
        for p in pvalues
    )


def test_benjamini_hochberg_on_a_worked_example() -> None:
    adjusted = gap.benjamini_hochberg((0.01, 0.04, 0.03, 0.005))
    assert adjusted == pytest.approx((0.02, 0.04, 0.04, 0.02))


def test_benjamini_hochberg_is_its_definition_and_keeps_the_order() -> None:
    rnd = random.Random(5)
    for _ in range(60):
        pvalues = tuple(
            rnd.choice((rnd.random(), 0.05, 1.0, 0.0)) for _ in range(rnd.randint(1, 25))
        )
        adjusted = gap.benjamini_hochberg(pvalues)
        expected = bh_by_definition(pvalues)
        assert adjusted == pytest.approx(expected, rel=1e-12, abs=0.0)
        assert all(p <= q <= 1.0 for p, q in zip(pvalues, adjusted, strict=True))


def test_benjamini_hochberg_of_nothing_one_p_and_ties() -> None:
    assert gap.benjamini_hochberg(()) == ()
    assert gap.benjamini_hochberg((0.3,)) == (0.3,)
    assert gap.benjamini_hochberg((1.0, 1.0)) == (1.0, 1.0)
    tied = gap.benjamini_hochberg((0.02, 0.02, 0.9))
    assert tied[0] == tied[1] == pytest.approx(0.03)


@pytest.mark.parametrize("pvalues", [(1.5,), (-0.1,), (nan,)])
def test_benjamini_hochberg_refuses_a_p_outside_zero_and_one(pvalues: tuple[float, ...]) -> None:
    with pytest.raises(ViolationError):
        gap.benjamini_hochberg(pvalues)


def linear_quantile(values: tuple[float, ...], share: float) -> float:
    """numpy's default quantile, as a person writes it."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * share
    below = floor(position)
    above = min(below + 1, len(ordered) - 1)
    return ordered[below] + (position - below) * (ordered[above] - ordered[below])


def test_a_percentile_interval_is_the_two_quantiles() -> None:
    values = tuple(float(v) for v in range(1, 12))
    assert gap.percentile_interval(values, 0.9) == (1.5, 10.5)
    rnd = random.Random(8)
    sample = tuple(rnd.gauss(0.7, 0.1) for _ in range(1000))
    low, high = gap.percentile_interval(sample, 0.95)
    assert low == pytest.approx(linear_quantile(sample, 0.025), rel=1e-12)
    assert high == pytest.approx(linear_quantile(sample, 0.975), rel=1e-12)
    assert gap.percentile_interval((3.0,), 0.95) == (3.0, 3.0)
    # Two values so large and of opposite sign that their difference overflows.
    assert gap.percentile_interval((-1e308, 1e308), 0.5) == (-5e307, 5e307)
    assert gap.percentile_interval((2.0, 2.0, 2.0), 0.95) == (2.0, 2.0)


@pytest.mark.parametrize(
    ("values", "level"), [((1.0, 2.0), 0.0), ((1.0, 2.0), 1.0), ((), 0.9), ((1.0, inf), 0.9)]
)
def test_a_percentile_interval_refuses_no_values_and_a_level_at_an_end(
    values: tuple[float, ...], level: float
) -> None:
    with pytest.raises(ViolationError):
        gap.percentile_interval(values, level)


def test_a_gap_ratio_is_the_distance_over_the_real_real_median() -> None:
    assert gap.gap_ratio(2.0, (1.0, 1.0, 3.0)) == 2.0
    assert gap.gap_ratio(3.0, (1.0, 2.0, 4.0, 10.0)) == 1.0
    assert gap.gap_ratio(0.0, (1.0,)) == 0.0
    assert gap.gap_ratio(1e308, (1e308, 1e308)) == 1.0


@pytest.mark.parametrize(
    ("cross", "baseline"),
    [(1.0, (0.0, 0.0, 1.0)), (-1.0, (1.0,)), (nan, (1.0,)), (1.0, ()), (1.0, (1.0, inf))],
)
def test_a_gap_ratio_refuses_a_median_of_zero_and_a_distance_below_zero(
    cross: float, baseline: tuple[float, ...]
) -> None:
    with pytest.raises(ViolationError):
        gap.gap_ratio(cross, baseline)


@pytest.mark.parametrize(
    ("auc_low", "median", "word"),
    [
        (0.55, 0.9, "indistinguishable"),
        (0.6, 0.9, "indistinguishable"),
        (0.7, 0.8, "closer than two real corpora"),
        (0.85, 0.8, "separable"),
        (0.8, 0.8, "separable"),
        (0.7, 0.5, "separable"),
    ],
)
def test_the_gap_word_is_pre_registered(auc_low: float, median: float, word: str) -> None:
    assert gap.gap_word(auc_low, median) == word


def test_the_gap_word_refuses_a_bound_that_is_no_probability() -> None:
    with pytest.raises(ViolationError):
        gap.gap_word(1.2, 0.8)
    with pytest.raises(ViolationError):
        gap.gap_word(0.7, nan)


@pytest.mark.parametrize(
    ("auc_low", "mmd_q", "word"),
    [
        (0.5, 0.5, "replicated"),
        (0.6, 0.05, "replicated"),
        (0.0, 1.0, "replicated"),
        (0.6000001, 0.05, "not replicated"),
        (0.6, 0.0499, "not replicated"),
        (0.6000001, 0.0499, "not replicated"),
        (1.0, 1.0, "not replicated"),
        (0.0, 0.0, "not replicated"),
    ],
)
def test_the_replication_word_is_pre_registered(auc_low: float, mmd_q: float, word: str) -> None:
    assert gap.REPLICATION_WORDS == ("replicated", "not replicated")
    assert (gap.REPLICATION_AUC, gap.REPLICATION_Q) == (0.6, 0.05)
    assert gap.replication_word(auc_low, mmd_q) == word


@pytest.mark.parametrize(
    ("auc_low", "mmd_q"), [(1.2, 0.5), (-0.1, 0.5), (0.5, 1.5), (0.5, nan), (nan, 0.5)]
)
def test_the_replication_word_refuses_what_is_no_probability(auc_low: float, mmd_q: float) -> None:
    with pytest.raises(ViolationError):
        gap.replication_word(auc_low, mmd_q)


# --- the report line ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "line"),
    [
        ("auc=0.93 lo=0.81", "auc 0.93 lo 0.81"),
        ("group vindr person rule dicom:patient", "group vindr person rule dicom: pa tient"),
        ("date 20261025 uid 1.2.3.4.5.6", "date 2026 1025 uid 1.2.3.4. 5.6"),
        ("x was 5", "x  was 5"),
        ("token: abc", "to ken: abc"),
        ("http://user@host/x", "http: //user@host/x"),
        ("tag (0010,0020) read", "tag ( 0010,0020) read"),
        ("sha " + "ab" * 20, "sha " + ("ab" * 20)[:31]),
        ("café\tno", "caf? no"),
        ("sk-abcdefghij and hf_" + "a" * 24, "sk- abcdefghij and hf_ " + "a" * 24),
        # The key is built in two parts, so the secret scan never sees its shape in this file.
        ("key " + "AKIA" + "ABCDEFGHIJKLMNOP!", "key AKIA ABCDEFGHIJKLMNOP!"),
        ("'2026-10-25' quoted", "' 2026-10-25' quoted"),
        ("Invalid value for VR", "In valid value for VR"),
    ],
)
def test_a_report_line_is_made_safe_as_the_rules_say(text: str, line: str) -> None:
    assert gap.safe_line(text) == line


def test_a_safe_line_is_kept_whole() -> None:
    line = "flexray: auc 0.97 [0.95, 0.99] p 0.001 q 0.004 fd64 12.3 word separable"
    assert gap.safe_line(line) == line
    assert gap.safe_line(gap._NOT_SHOWN) == gap._NOT_SHOWN


def test_a_line_no_fix_can_make_safe_is_never_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    # With every fix turned into nothing, an unsafe line cannot be made safe; it is replaced by
    # the line that says so, and a safe one still goes through whole.
    monkeypatch.setattr(gap, "_one_pass", lambda line: line)
    assert gap.safe_line("rule dicom:patient") == gap._NOT_SHOWN
    assert gap.safe_line("auc 0.93") == "auc 0.93"


def test_a_long_line_is_cut_back_to_the_end_of_a_word() -> None:
    assert gap.safe_line("abcdefgh " * 40) == "abcdefgh " * 22
    # Cut at 200, the line would end in 20261025, a date the filter withholds only because the
    # cut ended it; the cut goes back to the end of the word before.
    assert gap.safe_line("n " * 96 + "202610251") == "n " * 96


# The words, shapes and punctuation grid/redact.sed keys on, as pieces a line is built from.
WORDS = (
    "patient PATIENT token Token password passwd pwd secret api_key apikey api-key cookie"
    " credential authorization Bearer Basic : = / :// @ ( ) , 0010 abcd 20261025 19991231"
    " 2026-10-25 1.2.3.4.5 . ghp_ github_pat_ glpat- xoxb- sk- hf_ AKIA ASIA ABCDEFGHIJKLMNOP"
    " 0123456789 abcdefgh ' \" ?key= &code= input_value= input_type=str] a Z _ - + T 12:30"
    " StudyDate dicom:patient auc 0.93 [ ] X-Amz-Signature Expires"
).split()
PIECES = (
    *WORDS,
    *(" was ", "person ", " holds more than", "(first ", ", ", " ", " ", "\t", "\u00e9"),
    *("Invalid value for VR", "deadbeef" * 4, "deadbeef" * 5, "x" * 31, "y" * 33, "9" * 9),
)


def lines_to_make_safe(count: int, seed: int) -> list[str]:
    """Lines built from the words, shapes and punctuation the filter keys on, and lines of any
    printable characters."""
    rnd = random.Random(seed)
    built = ["".join(rnd.choice(PIECES) for _ in range(rnd.randint(1, 40))) for _ in range(count)]
    printable = string.printable[:95]
    noise = [
        "".join(rnd.choice(printable) for _ in range(rnd.randint(1, 260))) for _ in range(count)
    ]
    return built + noise


def filtered(lines: list[str]) -> list[str]:
    """The lines as grid/gate.sh's status shows them, through grid/redact.sed."""
    done = subprocess.run(
        ["sed", "-r", "-f", str(REDACT)],
        input="\n".join(lines) + "\n",
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.split("\n")[:-1]


def test_every_line_made_safe_passes_the_grid_filter_unchanged() -> None:
    lines = [gap.safe_line(text) for text in lines_to_make_safe(1500, 17)]
    assert filtered(lines) == lines
    assert gap._NOT_SHOWN not in lines
    assert all(gap.safe_line(line) == line for line in lines)


def test_the_filter_does_change_the_lines_before_they_are_made_safe() -> None:
    # The check above means something only if the filter bites on what it was given unmade.
    raw = [
        "rule dicom:patient",
        "token: abc",
        "uid 1.2.3.4.5.6",
        "date 20261025",
        "x was 5",
        "sha " + "ab" * 16,
    ]
    assert all(before != after for before, after in zip(raw, filtered(raw), strict=True))
