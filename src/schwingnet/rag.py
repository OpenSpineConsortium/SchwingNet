"""Retrieval over the textbook: each way of finding the passages a question needs, chosen by name.

The owner's ask of 2026-10-24: "A RAG trained on the textbook should help. Use a similar plug and
play method package". The book under docs/textbook/ is some 270,000 words, too much to read whole
for each question, so a question is answered from the passages a search finds, and each part of
that search is a block, chosen by name as the trainer's blocks are (schwingnet.blocks):

- chunk: how the book is cut into passages, "section" (one passage for each heading's section, a
  section longer than about 300 words cut into even pieces, each after the first opening with the
  40 words before it), "window" (fixed windows of 200 words over a chapter's whole text, wherever
  its headings fall) or "figure" (the sections, and each figure's record as a passage of its own);
- tokens: how a text becomes the words matched, "plain" (runs of ASCII letters and digits in lower
  case, a short list of stop words left out) or "stem" (plain, then at most one light suffix rule
  for each word, so trained and training both match train);
- index: how a passage scores for a question, "bm25" (Okapi BM25 with k1 1.5 and b 0.75 and the
  idf that is never negative) or "tfidf" (each word weighed 1 + ln tf times ln(1 + N / df), a
  passage's weights scaled to length 1, the question's words weighing alike);
- retrieve: which passages are kept, "top" (the k best) or "spread" (the best, at most two from
  any one chapter, so an answer sees several chapters);
- answer: what Claude is asked with the passages, "cite" (answer from the passages alone, cite each
  one used by its number, name its chapter and figure, and say so when they do not answer) or
  "brief" (the same in at most five sentences);
- embed: "none" only. It is the slot for a dense retriever: a local embedding model is a later name,
  run in the train environment, never an API key, since the repository keeps no key and the
  subscription token mints no embeddings.

DEFAULT is version 1: section, plain, bm25, top, cite and none. The index is plain data, the
vocabulary, each word's idf, each passage's length and the postings, built by the pure functions
here from the passages, so tools/rag.py builds it on the runner and the book's pages score it in the
reader's browser with a JavaScript mirror of `tokens`, `score`, `retrieve` and `prompt`, which the
shared fixture tests/fixtures/rag-scoring.json holds equal to this code. Nothing here reads a file:
the tool reads the chapters and the figure records and hands their text in. A new way of doing a
part is one name added to its tuple and one branch where the part is applied (`_cut_chapter` for a
chunk, `_stem` for tokens, `_idf` and `_postings` for an index, `retrieve`, `instructions`), and the
same in the mirror for tokens, index and retrieve; `problems` checks the choices and `parts` lists
them for tools/rag.py.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, fields, replace

from beartype import beartype
from beethoven_qa.contracts import ensure, require

CHUNK = ("section", "window", "figure")
TOKENS = ("plain", "stem")
INDEX = ("bm25", "tfidf")
RETRIEVE = ("top", "spread")
ANSWER = ("cite", "brief")
EMBED = ("none",)

# The sizes the chunk blocks cut at, in words, and how many passages "spread" keeps of a chapter.
SECTION_WORDS = 300
OVERLAP_WORDS = 40
WINDOW_WORDS = 200
PER_CHAPTER = 2
# Okapi BM25's two settings, at the values most implementations ship.
K1 = 1.5
B = 0.75
# Words too common to tell one passage from another; the browser reads the same list from the index.
STOPWORDS = frozenset(
    (
        "a about all also an and any are as at be been but by can could did do does each for from"
        " had has have he her his how i if in into is it its may me might more most my no not of"
        " on or our she should so some such than that the their them then there these they this"
        " those to us was we were what when where which who whom why will with would you your"
    ).split()
)
# The light suffix rules of the stem block, tried in order, the first that fits applied alone.
_SUFFIXES = (
    ("sses", "ss"),
    ("ies", "y"),
    ("ches", "ch"),
    ("shes", "sh"),
    ("xes", "x"),
    ("ing", ""),
    ("ed", ""),
    ("s", ""),
)
_KEEP_ENDINGS = ("ss", "us", "is")
_SHORTEST_STEM = 3
# A bound on every number an index holds, far above any a book gives, so a score stays finite.
_BOUND = 1e9
_LOWER = {code: code + 32 for code in range(ord("A"), ord("Z") + 1)}
_WORD = re.compile(r"[a-z0-9]+")
_ANCHOR_GAP = re.compile(r"[^a-z0-9]+")
_HEADING = re.compile(r"^#{2,6} +(.*)$")
_FIGURE_RECORDS = "docs/textbook/figures"
_FIGURE_LINE = re.compile(r"^!\[[^\]]*\]\(figures/(\d\d/[a-z0-9-]+)\.(?:png|svg)\)\s*$")
_TABLE_RULE = re.compile(r"^\s*\|?[\s:|-]*-{3}[\s:|-]*$")
_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_MARKS = re.compile(r"[*`|]")


class RagError(ValueError):
    """A block named that does not exist, or a word that names no block, said in words."""


@dataclass(frozen=True)
class Retrieval:
    """One choice for each part of retrieval; the defaults are version 1's."""

    chunk: str = "section"
    tokens: str = "plain"
    index: str = "bm25"
    retrieve: str = "top"
    answer: str = "cite"
    embed: str = "none"


DEFAULT = Retrieval()
CHOICES = {
    "chunk": CHUNK,
    "tokens": TOKENS,
    "index": INDEX,
    "retrieve": RETRIEVE,
    "answer": ANSWER,
    "embed": EMBED,
}
FIELDS = tuple(f.name for f in fields(Retrieval))


@dataclass(frozen=True)
class Chapter:
    """One chapter as the tool reads it: its file, its number, its title and its Markdown."""

    file: str
    number: str
    title: str
    text: str


@dataclass(frozen=True)
class Figure:
    """One figure's record as a passage: its id (such as 35/experiments), the chapter its record
    names, its title and the record's prose."""

    id: str
    chapter: str
    title: str
    text: str


@dataclass(frozen=True)
class Chunk:
    """One passage: where it is read (the chapter's file and number, the chapter's title, the
    heading it falls under, that heading's anchor on the site and its line in the file), its text
    as a reader sees it, and the figures it places or is."""

    id: str
    file: str
    chapter: str
    title: str
    heading: str
    anchor: str
    line: int
    text: str
    figures: tuple[str, ...] = ()


@dataclass(frozen=True)
class Index:
    """The index of the passages as plain data: the index and tokens blocks it was built with, the
    vocabulary in sorted order with each word's idf and postings, a posting being a passage's place
    and the word's count in it (bm25) or its weight there (tfidf), and each passage's length."""

    kind: str
    tokens: str
    vocabulary: tuple[str, ...]
    idf: tuple[float, ...]
    lengths: tuple[int, ...]
    postings: tuple[tuple[tuple[int, float], ...], ...]


@dataclass(frozen=True)
class _Section:
    heading: str
    anchor: str
    line: int
    text: str
    figures: tuple[str, ...]


# The choices


@beartype
@ensure(lambda result: all(isinstance(line, str) and line for line in result), "each said in words")
@ensure(lambda result, choice: choice != DEFAULT or not result, "version 1 holds")
def problems(choice: Retrieval) -> list[str]:
    """Every part whose name is not one of its part's names, in words; empty when all hold."""
    return [
        f"{name}={getattr(choice, name)!r} is not one of {', '.join(names)}"
        for name, names in CHOICES.items()
        if getattr(choice, name) not in names
    ]


@beartype
@ensure(lambda result: not problems(result), "the choices returned hold")
@ensure(lambda result, pairs: bool(pairs) or result == DEFAULT, "no word is version 1")
def parse(pairs: Sequence[str]) -> Retrieval:
    """The choices from KEY=VALUE words, each part named at most once, refused whole on a fault.

    :raises RagError: a word that is not KEY=VALUE with KEY a part, a part named twice, or a name
        its part does not have.
    """
    chosen: dict[str, str] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or key.strip() not in FIELDS:
            raise RagError(f"{pair!r} is not KEY=VALUE with KEY one of {', '.join(FIELDS)}")
        if key.strip() in chosen:
            raise RagError(f"{key.strip()} is named twice")
        chosen[key.strip()] = value.strip()
    choice = replace(DEFAULT, **chosen)
    if problems(choice):
        raise RagError("; ".join(problems(choice)))
    return choice


@beartype
@ensure(lambda result: tuple(result) == FIELDS, "every part, in order")
def as_record(choice: Retrieval) -> dict[str, str]:
    """The choices as a manifest and an eval record write them."""
    return asdict(choice)


@beartype
@ensure(lambda result, choice: choice != DEFAULT or not result, "version 1 needs no word")
@ensure(lambda result: all("=" in word for word in result), "each word is KEY=VALUE")
def words_of(choice: Retrieval) -> list[str]:
    """The KEY=VALUE words that name these choices, only those that differ from version 1."""
    default = as_record(DEFAULT)
    return [f"{k}={v}" for k, v in as_record(choice).items() if v != default[k]]


@beartype
@ensure(lambda result: [row["part"] for row in result] == list(FIELDS), "every part once, in order")
@ensure(lambda result: all(set(r) == {"part", "choices", "default"} for r in result), "3 columns")
def parts() -> list[dict[str, str]]:
    """Every plug-in point: the part, the names it may take and version 1's choice."""
    default = as_record(DEFAULT)
    return [{"part": n, "choices": ", ".join(CHOICES[n]), "default": default[n]} for n in FIELDS]


# Words


def _stem(word: str) -> str:
    # At most one rule, the first that fits and leaves a word of three letters or more; a word
    # ending in ss, us or is keeps its s.
    for suffix, replacement in _SUFFIXES:
        left = len(word) - len(suffix) + len(replacement)
        if word.endswith(suffix) and left >= _SHORTEST_STEM:
            if suffix == "s" and word.endswith(_KEEP_ENDINGS):
                return word
            return word[: -len(suffix)] + replacement
    return word


def _is_word(word: str) -> bool:
    return bool(word) and all("a" <= c <= "z" or "0" <= c <= "9" for c in word)


@beartype
@require(lambda rule: rule in TOKENS, "a tokens block that exists")
@ensure(lambda result: all(_is_word(word) for word in result), "ASCII letters and digits")
@ensure(lambda result, rule: rule != "plain" or not STOPWORDS & set(result), "no stop word")
def tokens(text: str, rule: str) -> list[str]:
    """The words of a text a search matches, by the tokens block named: runs of ASCII letters and
    digits, the 26 capitals lowered and nothing else, so the browser's mirror reads every text
    alike; the stop words left out; and, for stem, each word's light suffix rule applied."""
    kept = [word for word in _WORD.findall(text.translate(_LOWER)) if word not in STOPWORDS]
    return [_stem(word) for word in kept] if rule == "stem" else kept


@beartype
@ensure(lambda result: result == " ".join(result.split()), "one space between words, none at ends")
@ensure(lambda result: not set(result) & set("*`|"), "no emphasis, code or table marks")
def plain_text(markdown: str) -> str:
    """The words a reader sees of some Markdown: a link's label without its address, no image line
    or table rule, no emphasis, code or table marks, one space between words."""
    lines = [
        line
        for line in markdown.splitlines()
        if not _FIGURE_LINE.match(line) and not _TABLE_RULE.match(line)
    ]
    return " ".join(_MARKS.sub("", _LINK.sub(r"\1", "\n".join(lines))).split())


@beartype
@ensure(lambda result: all("a" <= c <= "z" or "0" <= c <= "9" or c == "-" for c in result), "id")
@ensure(lambda result: not result.startswith("-") and not result.endswith("-"), "no hyphen at ends")
def anchor(heading: str) -> str:
    """The id the site gives a heading, by tools/living_docs.py's rule, so a passage links to its
    section; a figure's id gives the figure's own anchor the same way, after "fig-"."""
    return _ANCHOR_GAP.sub("-", heading.lower()).strip("-")


# Passages


def _section_starts(lines: Sequence[str]) -> list[int]:
    # The first line, which holds the chapter's title, then every heading below it.
    return [0] + [i for i, line in enumerate(lines) if i > 0 and _HEADING.match(line)]


def _section(chapter: Chapter, lines: Sequence[str], start: int, end: int) -> _Section:
    head = _HEADING.match(lines[start]) if start > 0 else None
    raw = head.group(1).strip() if head else ""
    body = [line for line in lines[start + 1 : end] if not line.startswith("Label: ")]
    figures = tuple(m.group(1) for m in map(_FIGURE_LINE.match, body) if m)
    heading = plain_text(raw) if head else chapter.title
    return _Section(heading, anchor(raw), start + 1, plain_text("\n".join(body)), figures)


def _sections(chapter: Chapter) -> list[_Section]:
    """A chapter's sections in order: what stands under its title, then one for each heading."""
    lines = chapter.text.splitlines() or [""]
    starts = _section_starts(lines)
    ends = starts[1:] + [len(lines)]
    return [_section(chapter, lines, start, end) for start, end in zip(starts, ends, strict=True)]


def _pieces(words: Sequence[str]) -> list[Sequence[str]]:
    # A section of SECTION_WORDS words or fewer is one passage; a longer one is cut into even
    # pieces of at most that many, each after the first opening with the OVERLAP_WORDS before it.
    count = max(1, -(-len(words) // SECTION_WORDS))
    size = -(-len(words) // count)
    return [words[max(0, i * size - OVERLAP_WORDS) : (i + 1) * size] for i in range(count)]


def _section_chunks(chapter: Chapter) -> list[Chunk]:
    out: list[Chunk] = []
    for s in _sections(chapter):
        for piece in _pieces(s.text.split()) if s.text else []:
            key = f"{chapter.number}-{len(out) + 1}"
            text = " ".join(piece)
            out.append(
                Chunk(
                    key,
                    chapter.file,
                    chapter.number,
                    chapter.title,
                    s.heading,
                    s.anchor,
                    s.line,
                    text,
                    s.figures,
                )
            )
    return out


def _window_chunks(chapter: Chapter) -> list[Chunk]:
    sections = _sections(chapter)
    words = [(word, k) for k, s in enumerate(sections) for word in s.text.split()]
    out: list[Chunk] = []
    for start in range(0, len(words), WINDOW_WORDS):
        span = words[start : start + WINDOW_WORDS]
        first = sections[span[0][1]]
        figures = tuple(f for k in sorted({k for _w, k in span}) for f in sections[k].figures)
        key = f"{chapter.number}-w{len(out) + 1}"
        text = " ".join(word for word, _k in span)
        out.append(
            Chunk(
                key,
                chapter.file,
                chapter.number,
                chapter.title,
                first.heading,
                first.anchor,
                first.line,
                text,
                figures,
            )
        )
    return out


def _figure_chunk(figure: Figure, placed: dict[str, Chunk], chapters: dict[str, Chapter]) -> Chunk:
    # A figure is read where a chapter places it, else in the chapter its record names.
    home = placed.get(figure.id)
    chapter = chapters.get(figure.chapter)
    file = home.file if home else chapter.file if chapter else f"{_FIGURE_RECORDS}/{figure.id}.json"
    title = home.title if home else chapter.title if chapter else ""
    number = home.chapter if home else figure.chapter
    line = home.line if home else 1
    key, where = f"fig-{figure.id}", "fig-" + anchor(figure.id)
    text = plain_text(figure.text)
    return Chunk(key, file, number, title, figure.title, where, line, text, (figure.id,))


def _cut_chapter(chapter: Chapter, rule: str) -> list[Chunk]:
    return _window_chunks(chapter) if rule == "window" else _section_chunks(chapter)


def _figure_chunks(
    chunks: Sequence[Chunk], chapters: Sequence[Chapter], figures: Sequence[Figure]
) -> list[Chunk]:
    placed: dict[str, Chunk] = {}
    for c in chunks:
        for fid in c.figures:
            placed.setdefault(fid, c)
    by_number = {c.number: c for c in chapters}
    return [_figure_chunk(f, placed, by_number) for f in figures if plain_text(f.text)]


def _distinct_numbers(chapters: Sequence[Chapter]) -> bool:
    numbers = [c.number for c in chapters]
    return all(n.isascii() and n.isdigit() for n in numbers) and len(set(numbers)) == len(numbers)


@beartype
@require(lambda rule: rule in CHUNK, "a chunk block that exists")
@require(lambda chapters: _distinct_numbers(chapters), "each chapter has its own number, in digits")
@require(lambda figures: len({f.id for f in figures}) == len(figures), "each figure once")
@ensure(lambda result: len({c.id for c in result}) == len(result), "each passage its own id")
@ensure(lambda result: all(c.text for c in result), "no passage is empty")
@ensure(
    lambda result, rule: rule == "figure" or not any(c.id[:4] == "fig-" for c in result),
    "figures are passages only under chunk=figure",
)
def chunk(chapters: Sequence[Chapter], figures: Sequence[Figure], rule: str) -> tuple[Chunk, ...]:
    """The book cut into passages by the chunk block named, chapter by chapter in the order given,
    then, for figure, each figure with prose in its record after them."""
    cut = [c for chapter in chapters for c in _cut_chapter(chapter, rule)]
    extra = _figure_chunks(cut, chapters, figures) if rule == "figure" else []
    return tuple(cut + extra)


# The index


def _idf(kind: str, passages: int, holding: int) -> float:
    # bm25's idf, which never falls below 0, and tf-idf's smoothed one.
    if kind == "tfidf":
        return math.log(1 + passages / holding)
    return math.log(1 + (passages - holding + 0.5) / (holding + 0.5))


def _norms(counts: Sequence[Counter[str]], idf: dict[str, float]) -> list[float]:
    # Each passage's length as a vector of tf-idf weights, so its weights can be scaled to 1;
    # fsum, whose sum is exact, so every Python release gives the same bits.
    return [
        math.sqrt(math.fsum(((1 + math.log(tf)) * idf[word]) ** 2 for word, tf in count.items()))
        for count in counts
    ]


def _postings(
    kind: str, counts: Sequence[Counter[str]], idf: dict[str, float]
) -> dict[str, list[tuple[int, float]]]:
    # For each word, the passages holding it in their order, with its count there (bm25) or its
    # weight there scaled by the passage's length (tfidf).
    norms = _norms(counts, idf) if kind == "tfidf" else []
    held: dict[str, list[tuple[int, float]]] = {word: [] for word in idf}
    for doc, count in enumerate(counts):
        for word, tf in count.items():
            weight = (1 + math.log(tf)) * idf[word] / norms[doc] if norms else float(tf)
            held[word].append((doc, weight))
    return held


def _well_formed(index: Index) -> bool:
    """An index as build_index makes one: every row in place, every number finite and bounded, and
    every posting naming a passage the index has."""
    passages = len(index.lengths)
    return (
        index.kind in INDEX
        and index.tokens in TOKENS
        and len(index.idf) == len(index.vocabulary) == len(index.postings)
        and all(0.0 <= value <= _BOUND for value in index.idf)
        and all(0 <= length <= _BOUND for length in index.lengths)
        and all(0 <= d < passages and 0.0 < v <= _BOUND for row in index.postings for d, v in row)
    )


@beartype
@require(lambda kind: kind in INDEX, "an index block that exists")
@require(lambda rule: rule in TOKENS, "a tokens block that exists")
@ensure(lambda result, chunks: len(result.lengths) == len(chunks), "a length for every passage")
@ensure(lambda result: list(result.vocabulary) == sorted(set(result.vocabulary)), "sorted, once")
@ensure(lambda result: _well_formed(result), "plain data the scoring reads")
def build_index(chunks: Sequence[Chunk], kind: str, rule: str) -> Index:
    """The index of the passages in the order given: each word of their headings and texts with its
    idf and postings, and each passage's length in words; the data the browser's mirror scores."""
    counts = [Counter(tokens(c.heading + " " + c.text, rule)) for c in chunks]
    df = Counter(word for count in counts for word in count)
    vocabulary = tuple(sorted(df))
    idf = {word: _idf(kind, len(counts), df[word]) for word in vocabulary}
    held = _postings(kind, counts, idf)
    lengths = tuple(sum(count.values()) for count in counts)
    rows = tuple(tuple(held[word]) for word in vocabulary)
    return Index(kind, rule, vocabulary, tuple(idf[w] for w in vocabulary), lengths, rows)


def _average(lengths: Sequence[int]) -> float:
    total = sum(lengths)
    return total / len(lengths) if total > 0 else 1.0


def _row_scores(index: Index, row: int, average: float) -> list[tuple[int, float]]:
    """What one word of the question adds to each passage holding it. The arithmetic is written in
    the browser's mirror in the same order, so the two agree to the bit."""
    if index.kind == "tfidf":
        return list(index.postings[row])
    idf, lengths = index.idf[row], index.lengths
    return [
        (doc, idf * (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * lengths[doc] / average)))
        for doc, tf in index.postings[row]
    ]


def _rank_key(pair: tuple[int, float]) -> tuple[float, int]:
    return (-pair[1], pair[0])


@beartype
@require(lambda index: _well_formed(index), "an index as build_index makes one")
@ensure(lambda result: all(total > 0.0 for _doc, total in result), "only passages that match")
@ensure(lambda result: result == sorted(result, key=_rank_key), "best first, ties in index order")
@ensure(lambda result: len({doc for doc, _t in result}) == len(result), "each passage once")
@ensure(lambda result, index: all(d < len(index.lengths) for d, _t in result), "the index's own")
def score(index: Index, question: str) -> list[tuple[int, float]]:
    """Every passage that shares a word with the question, best first, with its score, passages of
    equal score in the index's order. Each word of the question counts once, in the order it first
    comes, which is the order the browser's mirror adds in."""
    rows = {word: row for row, word in enumerate(index.vocabulary)}
    average = _average(index.lengths)
    totals: dict[int, float] = {}
    for word in dict.fromkeys(tokens(question, index.tokens)):
        for doc, add in _row_scores(index, rows[word], average) if word in rows else []:
            totals[doc] = totals.get(doc, 0.0) + add
    return [(doc, total) for doc, total in sorted(totals.items(), key=_rank_key) if total > 0.0]


def _in_order(kept: Sequence[int], ranked: Sequence[int]) -> bool:
    rest = iter(ranked)
    return all(doc in rest for doc in kept)


def _per_chapter(kept: Sequence[int], chapters: Sequence[str]) -> int:
    return max(Counter(chapters[doc] for doc in kept).values(), default=0)


@beartype
@require(lambda rule: rule in RETRIEVE, "a retrieve block that exists")
@require(lambda k: 0 <= k <= 1000, "a handful of passages")
@require(lambda ranked, chapters: all(0 <= d < len(chapters) for d, _s in ranked), "named places")
@ensure(lambda result, k: len(result) <= k, "no more than k")
@ensure(lambda result, ranked: _in_order(result, [d for d, _s in ranked]), "best first, as ranked")
@ensure(
    lambda result, chapters, rule: (
        rule != "spread" or _per_chapter(result, chapters) <= PER_CHAPTER
    ),
    "spread keeps at most PER_CHAPTER of a chapter",
)
def retrieve(
    ranked: Sequence[tuple[int, float]], chapters: Sequence[str], rule: str, k: int
) -> list[int]:
    """The passages kept of the ranked ones, by the retrieve block named: the k best (top), or the
    best with at most PER_CHAPTER of any one chapter (spread); `chapters` names each passage's."""
    kept: list[int] = []
    taken: Counter[str] = Counter()
    for doc, _score in ranked:
        if len(kept) == k:
            break
        if rule == "spread" and taken[chapters[doc]] >= PER_CHAPTER:
            continue
        kept.append(doc)
        taken[chapters[doc]] += 1
    return kept


# The measures of tools/rag.py eval


@beartype
@require(lambda gold: len(gold) > 0, "a question has a chapter that answers it")
@require(lambda n: n >= 1, "at least the first passage")
@ensure(lambda result: 0.0 <= result <= 1.0, "a share")
def recall_at(found: Sequence[str], gold: Sequence[str], n: int) -> float:
    """The share of the chapters that answer a question that are among the chapters of the first n
    passages found."""
    wanted = set(gold)
    return len(wanted & set(found[:n])) / len(wanted)


@beartype
@ensure(lambda result: 0.0 <= result <= 1.0, "a share")
@ensure(lambda result, found, gold: (result > 0.0) == bool(set(found) & set(gold)), "0 when none")
def reciprocal_rank(found: Sequence[str], gold: Sequence[str]) -> float:
    """One over the place of the first passage found from a chapter that answers, 0 when none is."""
    for place, chapter in enumerate(found, 1):
        if chapter in gold:
            return 1.0 / place
    return 0.0


# What Claude is asked

_RULES = (
    "You answer a reader of the SchwingNet textbook, a confidential book built from a research "
    "programme's records. Answer from the numbered passages of the book and from nothing else; if "
    "the search_textbook tool is offered and they do not answer, search again with other words. "
    "Cite every passage you rely on by its number in square brackets, as [2], after the sentence "
    "it supports, and name in your words the chapter (its number and title) and any figure you "
    "use. Give the book's grades (Measured, Reported, Inferred, Unverified) and its status words "
    "as the passages give them, call a figure the record has not settled a record, not a final "
    "value, and give numbers only as the passages give them, with their n and interval where they "
    "have them. Name people by role, never by name. When the passages do not answer, say so "
    "plainly and name the chapter that comes nearest, rather than guess."
)
_LENGTH = {
    "cite": "Plain prose, no headings, under 250 words.",
    "brief": "Plain prose, no headings, in at most five sentences.",
}


@beartype
@require(lambda answer: answer in ANSWER, "an answer block that exists")
@ensure(lambda result: "[2]" in result and "do not answer" in result, "cites, and says so")
def instructions(answer: str) -> str:
    """What Claude is told before the passages, by the answer block named."""
    return _RULES + " " + _LENGTH[answer]


def _passage(number: int, passage: Chunk) -> str:
    figures = f" (figure {', '.join(passage.figures)})" if passage.figures else ""
    where = f"Chapter {passage.chapter} {passage.title}, {passage.heading}{figures}"
    return f"[{number}] {where}:\n{passage.text}"


@beartype
@require(lambda answer: answer in ANSWER, "an answer block that exists")
@require(lambda question: question != "" and question == question.strip(), "a question, trimmed")
@ensure(lambda result, question: result.endswith("Question: " + question), "the question last")
@ensure(
    lambda result, passages: all(f"[{n}] " in result for n in range(1, len(passages) + 1)),
    "every passage numbered",
)
def prompt(answer: str, question: str, passages: Sequence[Chunk]) -> str:
    """The whole text Claude reads: the answer block's instructions, the passages numbered from 1
    with each one's chapter and heading, then the question."""
    shown = [_passage(n, p) for n, p in enumerate(passages, 1)]
    return "\n\n".join([instructions(answer), "Passages:", *shown, "Question: " + question])


@beartype
@require(lambda index: _well_formed(index), "an index as build_index makes one")
@ensure(lambda result, index: len(result["postings"]) == len(index.vocabulary), "a row a word")
def index_record(index: Index) -> dict[str, object]:
    """The index as plain JSON data for the browser: each word's postings flattened to passage,
    value, passage, value, the counts of bm25 written as whole numbers, with the settings, the stop
    words and the suffix rules the mirror needs to read and score a question as this code does."""
    whole = index.kind == "bm25"
    rows = [[x for d, v in row for x in (d, int(v) if whole else v)] for row in index.postings]
    return {
        "kind": index.kind,
        "tokens": index.tokens,
        "k1": K1,
        "b": B,
        "per_chapter": PER_CHAPTER,
        "stopwords": sorted(STOPWORDS),
        "suffixes": [list(rule) for rule in _SUFFIXES],
        "keep": list(_KEEP_ENDINGS),
        "shortest": _SHORTEST_STEM,
        "vocabulary": list(index.vocabulary),
        "idf": list(index.idf),
        "lengths": list(index.lengths),
        "postings": rows,
    }
