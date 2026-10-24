"""The book's search: version 1 by default, each block chosen by name, and the scoring held to the
fixture the browser's mirror is held to (tests/fixtures/rag-scoring.json)."""

import json
import math
from pathlib import Path

import pytest

from schwingnet.rag import (
    CHOICES,
    DEFAULT,
    FIELDS,
    OVERLAP_WORDS,
    PER_CHAPTER,
    STOPWORDS,
    Chapter,
    Chunk,
    Figure,
    RagError,
    Retrieval,
    anchor,
    as_record,
    build_index,
    chunk,
    index_record,
    instructions,
    parse,
    parts,
    plain_text,
    problems,
    prompt,
    recall_at,
    reciprocal_rank,
    retrieve,
    score,
    tokens,
    words_of,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rag-scoring.json"

ONE = "\n".join(
    [
        "# 01 One",
        "",
        "Label: schwingnet-internal",
        "",
        "The opening words of the chapter about anchors.",
        "",
        "## Counting from an anchor",
        "",
        "The sacrum is the *anchor* and the count runs up the sweep.",
        "",
        "![Figure 1.1](figures/01/a-figure.png)",
        "",
        "*Figure 1.1. A caption.*",
        "",
        "## A table, with `code`",
        "",
        "| a | b |",
        "|---|---|",
        "| [link text](x.md) | `code` |",
    ]
)


def one() -> Chapter:
    return Chapter("docs/textbook/01-one.md", "01", "One", ONE)


def long_chapter(words: int) -> Chapter:
    body = " ".join(f"w{i}" for i in range(words))
    return Chapter("docs/textbook/02-two.md", "02", "Two", f"# 02 Two\n\n## Long\n\n{body}\n")


def passage(key: str, chapter: str, text: str, heading: str = "H") -> Chunk:
    return Chunk(key, f"docs/textbook/{chapter}-x.md", chapter, "T", heading, "h", 1, text)


# The choices


def test_no_words_are_version_1():
    assert parse([]) == DEFAULT == Retrieval()
    assert as_record(DEFAULT) == {
        "chunk": "section",
        "tokens": "plain",
        "index": "bm25",
        "retrieve": "top",
        "answer": "cite",
        "embed": "none",
    }
    assert problems(DEFAULT) == []
    assert words_of(DEFAULT) == []


def test_words_choose_each_part_and_name_only_what_differs():
    choice = parse(["chunk=window", " tokens = stem ", "retrieve=spread"])
    assert (choice.chunk, choice.tokens, choice.retrieve) == ("window", "stem", "spread")
    assert words_of(choice) == ["chunk=window", "tokens=stem", "retrieve=spread"]
    assert parse(words_of(choice)) == choice


@pytest.mark.parametrize(
    ("words", "said"),
    [
        (["chunk"], "is not KEY=VALUE"),
        (["colour=red"], "is not KEY=VALUE"),
        (["index=bm25", "index=tfidf"], "named twice"),
        (["embed=openai"], "embed='openai' is not one of none"),
    ],
)
def test_a_fault_is_refused_in_words(words, said):
    with pytest.raises(RagError, match=said):
        parse(words)


def test_problems_name_every_part_that_does_not_hold():
    found = problems(Retrieval(chunk="page", index="dense"))
    assert len(found) == 2
    assert "chunk='page'" in found[0] and "index='dense'" in found[1]


def test_parts_lists_every_part_with_its_names_and_version_1():
    rows = parts()
    assert [r["part"] for r in rows] == list(FIELDS)
    assert {r["part"]: r["choices"] for r in rows}["chunk"] == "section, window, figure"
    assert all(r["default"] in CHOICES[r["part"]] for r in rows)


# Words


def test_plain_words_are_ascii_letters_and_digits_lowered_with_no_stop_word():
    assert tokens("The Sacrum is the ANCHOR; L5-S1 at 97 ms", "plain") == [
        "sacrum",
        "anchor",
        "l5",
        "s1",
        "97",
        "ms",
    ]
    assert tokens("café ÉCOLE", "plain") == ["caf", "cole"]
    assert tokens("", "plain") == []
    assert "the" in STOPWORDS and "sacrum" not in STOPWORDS


def test_stem_applies_one_light_rule_and_keeps_short_words():
    words = "trained training trains studies classes boxes matches wishes basis bus ties used"
    assert tokens(words, "stem") == [
        "train",
        "train",
        "train",
        "study",
        "class",
        "box",
        "match",
        "wish",
        "basis",
        "bus",
        "tie",
        "used",
    ]


def test_plain_text_keeps_what_a_reader_sees():
    text = (
        "See [the map](a.md), **bold** and `code`.\n\n| a | b |\n|---|---|\n![x](figures/01/f.png)"
    )
    assert plain_text(text) == "See the map, bold and code. a b"


def test_an_anchor_is_the_sites_heading_id():
    assert anchor("The R + C = 22 rule") == "the-r-c-22-rule"
    assert anchor("  Words: forbidden, or replaced!  ") == "words-forbidden-or-replaced"
    assert anchor("") == ""


# Passages


def test_a_chapter_is_cut_at_its_headings():
    cut = chunk([one()], [], "section")
    assert [c.id for c in cut] == ["01-1", "01-2", "01-3"]
    first, counting, table = cut
    assert (first.heading, first.anchor, first.line) == ("One", "", 1)
    assert first.text == "The opening words of the chapter about anchors."
    assert (counting.heading, counting.anchor, counting.line) == (
        "Counting from an anchor",
        "counting-from-an-anchor",
        7,
    )
    assert (
        counting.text
        == "The sacrum is the anchor and the count runs up the sweep. Figure 1.1. A caption."
    )
    assert counting.figures == ("01/a-figure",)
    assert (table.heading, table.anchor) == ("A table, with code", "a-table-with-code")
    assert table.text == "a b link text code"


def test_a_long_section_is_cut_into_even_pieces_that_overlap():
    cut = chunk([long_chapter(650)], [], "section")
    pieces = [c.text.split() for c in cut]
    assert [c.id for c in cut] == ["02-1", "02-2", "02-3"]
    assert [len(p) for p in pieces] == [217, 257, 256]
    assert pieces[1][:OVERLAP_WORDS] == pieces[0][-OVERLAP_WORDS:]
    assert pieces[2][-1] == "w649"


def test_windows_run_over_the_whole_chapter_and_name_where_they_start():
    cut = chunk([long_chapter(450)], [], "window")
    assert [c.id for c in cut] == ["02-w1", "02-w2", "02-w3"]
    assert [len(c.text.split()) for c in cut] == [200, 200, 50]
    assert {c.heading for c in cut} == {"Long"} and cut[2].text.split()[-1] == "w449"


def test_figures_are_passages_of_their_own_only_under_chunk_figure():
    figures = [
        Figure("01/a-figure", "01", "A figure", "Its *caption*."),
        Figure("01/untraced", "01", "Not placed", "Read in its chapter."),
        Figure("09/elsewhere", "09", "Far away", "A chapter the book does not hold."),
        Figure("01/blank", "01", "Blank", "  "),
    ]
    assert not [c for c in chunk([one()], figures, "section") if c.id.startswith("fig-")]
    extra = [c for c in chunk([one()], figures, "figure") if c.id.startswith("fig-")]
    placed, unplaced, far = extra
    assert [c.id for c in extra] == ["fig-01/a-figure", "fig-01/untraced", "fig-09/elsewhere"]
    assert (placed.file, placed.line, placed.anchor) == (
        "docs/textbook/01-one.md",
        7,
        "fig-01-a-figure",
    )
    assert (placed.heading, placed.text, placed.figures) == (
        "A figure",
        "Its caption.",
        ("01/a-figure",),
    )
    assert (unplaced.file, unplaced.line, unplaced.title) == ("docs/textbook/01-one.md", 1, "One")
    assert (far.file, far.chapter, far.title) == (
        "docs/textbook/figures/09/elsewhere.json",
        "09",
        "",
    )


# Scoring


CORPUS = [
    passage("a", "01", "anchor sacrum anchor", "Alpha"),
    passage("b", "01", "sweep anchor", "Beta"),
    passage("c", "02", "rib count", "Gamma"),
]


def bm25(tf: int, df: int, length: int, average: float, n: int = 3) -> float:
    idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
    return idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / average))


def test_bm25_scores_as_okapi_with_its_idf_never_negative():
    index = build_index(CORPUS, "bm25", "plain")
    assert index.lengths == (4, 3, 3)
    assert index.vocabulary == (
        "alpha",
        "anchor",
        "beta",
        "count",
        "gamma",
        "rib",
        "sacrum",
        "sweep",
    )
    ranked = score(index, "Where is the anchor?")
    assert [d for d, _s in ranked] == [0, 1]
    assert ranked[0][1] == pytest.approx(bm25(2, 2, 4, 10 / 3))
    assert ranked[1][1] == pytest.approx(bm25(1, 2, 3, 10 / 3))
    assert all(value >= 0 for value in index.idf)


def test_a_word_of_the_question_counts_once_and_unknown_words_add_nothing():
    index = build_index(CORPUS, "bm25", "plain")
    assert score(index, "anchor anchor ANCHOR") == score(index, "anchor")
    assert score(index, "zzz nothing") == []
    assert score(index, "") == []


def test_tfidf_scales_each_passage_to_length_one():
    index = build_index(CORPUS, "tfidf", "plain")
    weights = [0.0, 0.0, 0.0]
    for row in index.postings:
        for doc, value in row:
            weights[doc] += value * value
    assert weights == pytest.approx([1.0, 1.0, 1.0])
    assert [d for d, _s in score(index, "rib")] == [2]


def test_equal_scores_keep_the_index_order():
    twins = [passage("x", "01", "same words"), passage("y", "02", "same words")]
    ranked = score(build_index(twins, "bm25", "plain"), "same")
    assert [d for d, _s in ranked] == [0, 1] and ranked[0][1] == ranked[1][1]


def test_top_keeps_the_best_and_spread_keeps_two_of_a_chapter():
    ranked = [(0, 4.0), (1, 3.0), (2, 2.0), (3, 1.0)]
    chapters = ["01", "01", "01", "02"]
    assert retrieve(ranked, chapters, "top", 3) == [0, 1, 2]
    assert retrieve(ranked, chapters, "spread", 3) == [0, 1, 3]
    assert retrieve(ranked, chapters, "spread", 10) == [0, 1, 3]
    assert retrieve(ranked, chapters, "top", 0) == []
    assert PER_CHAPTER == 2


def test_the_measures():
    assert recall_at(["a", "b", "a", "c"], ["a", "c"], 3) == 0.5
    assert recall_at(["a", "b", "a", "c"], ["a", "c"], 4) == 1.0
    assert reciprocal_rank(["x", "y", "a"], ["a"]) == pytest.approx(1 / 3)
    assert reciprocal_rank(["x"], ["a"]) == 0.0


# What Claude is asked


def test_the_prompt_numbers_the_passages_and_ends_on_the_question():
    found = chunk([one()], [], "section")[1:2]
    text = prompt("cite", "How is the count made?", found)
    assert text.startswith(instructions("cite"))
    assert "[1] Chapter 01 One, Counting from an anchor (figure 01/a-figure):\nThe sacrum" in text
    assert text.endswith("\n\nQuestion: How is the count made?")


def test_the_answer_blocks_differ_only_in_length():
    cite, brief = instructions("cite"), instructions("brief")
    assert cite != brief and "five sentences" in brief and "250 words" in cite
    assert cite.split(" Plain prose")[0] == brief.split(" Plain prose")[0]
    assert "do not answer" in cite and "[2]" in cite


def test_the_index_record_is_plain_data_with_what_the_mirror_needs():
    bm = index_record(build_index(CORPUS, "bm25", "stem"))
    assert bm["postings"][bm["vocabulary"].index("anchor")] == [0, 2, 1, 1]
    assert all(isinstance(v, int) for row in bm["postings"] for v in row)
    assert {"stopwords", "suffixes", "keep", "shortest", "k1", "b", "per_chapter"} <= set(bm)
    tf = index_record(build_index(CORPUS, "tfidf", "plain"))
    assert isinstance(tf["postings"][0][1], float)
    assert json.loads(json.dumps(bm)) == bm


# The fixture the browser's mirror is held to


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fixture_chunks(data: dict) -> list[Chunk]:
    return [Chunk(**{**c, "figures": tuple(c["figures"])}) for c in data["chunks"]]


def test_the_fixtures_words_are_the_packages():
    for t in fixture()["texts"]:
        assert tokens(t["text"], "plain") == t["plain"]
        assert tokens(t["text"], "stem") == t["stem"]


def test_the_fixtures_indexes_rankings_and_scores_are_the_packages_to_the_bit():
    data = fixture()
    passages = fixture_chunks(data)
    chapters = [c.chapter for c in passages]
    for b in data["builds"]:
        index = build_index(passages, b["index"], b["tokens"])
        assert json.loads(json.dumps(index_record(index))) == b["record"]
        for q in b["queries"]:
            ranked = score(index, q["question"])
            assert [[passages[d].id, s] for d, s in ranked] == q["ranked"]
            kept = retrieve(ranked, chapters, b["retrieve"], b["k"])
            assert [passages[d].id for d in kept] == q["kept"]


def test_the_fixtures_prompt_is_the_packages():
    data = fixture()
    by_id = {c.id: c for c in fixture_chunks(data)}
    p = data["prompt"]
    assert instructions(p["answer"]) == p["instructions"]
    assert prompt(p["answer"], p["question"], [by_id[i] for i in p["passages"]]) == p["text"]
