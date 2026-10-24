#!/usr/bin/env python3
"""Ask the book: retrieval over the Artifact Textbook, each part of it a block chosen by name.

The owner's ask of 2026-10-24: "A RAG trained on the textbook should help. Use a similar plug and
play method package". The parts and their names are src/schwingnet/rag.py's, chosen with --block
KEY=VALUE as tools/train.py chooses the training blocks; this tool reads the book under
docs/textbook/ (the chapters and the figure records), hands their text to the package's pure
functions and prints or writes what they give. It needs the standard library alone, since
scripts/check.sh and the docs workflow run it with plain python3: the package is loaded from its
file with its two outside imports, beartype and beethoven_qa's contracts, standing in as no-ops
while it loads (the gate proves the contracts; tests/schwingnet checks them at run time).

    python3 tools/rag.py parts
    python3 tools/rag.py ask "How is a level counted from the sacrum?" [--k 8] [--block K=V ...] [--prompt]
    python3 tools/rag.py build --out DIR [--block KEY=VALUE ...]
    python3 tools/rag.py eval [--block KEY=VALUE ...] [--vary KEY=VALUE ...] [--grid] [--write]
    python3 tools/rag.py check
    python3 tools/rag.py fixture

ask builds the index in memory, in seconds, and prints the passages a question finds, each with its
chapter, heading, file, line and place in the site, for a session to read before it reads a chapter
whole; --prompt prints the whole text the book's Ask the book box gives Claude. build writes
index.json, chunks.json (each passage's id, chapter file, heading, anchor and text) and
manifest.json (the blocks, the passage count, the commit, the sha256 of every file read and the
build time). eval scores block sets by docs/textbook/rag/questions.json: the recall at 5 of the
chapters that answer each question, the mean reciprocal rank of the first passage from one of them,
the share of questions with a figure whose figure is held by the first five passages, and the
misses. --block names the set (version 1 when none), each --vary a set that differs from it in one
part, and --grid every set of the parts that change what is found; --write keeps the result as
docs/textbook/rag/eval.json. check holds version 1 to the floor the questions file writes, and runs
in scripts/check.sh. fixture rewrites the outputs of tests/fixtures/rag-scoring.json from its
inputs, the outputs the package's tests and the browser's mirror are both held to.

The index is not committed, since every edit of a chapter changes it. tools/textbook_site.py builds
it into the site with write_site (rag/index.json and rag/chunks.json, with the mirror rag/search.js
and the box's rag/box.js and rag/box.css), where the Ask the book box scores a question in the
reader's browser. In the claude.ai edition, where the artifact runtime gives the page sample, the
box also has Claude answer from the passages, with the search as its tool, on the viewer's own
account: no server and no key.
"""

import argparse
import functools
import hashlib
import html
import importlib.util
import itertools
import json
import math
import re
import subprocess
import sys
import types
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = Path("src/schwingnet/rag.py")
BOOK = Path("docs/textbook")
FIGURES = BOOK / "figures"
QUESTIONS = BOOK / "rag" / "questions.json"
RECORD = BOOK / "rag" / "eval.json"
FIXTURE = Path("tests/fixtures/rag-scoring.json")
CHAPTER_NAME = re.compile(r"\d\d-[a-z0-9-]+\.md")
TITLE_LINE = re.compile(r"# \d\d (.+)")
MODULE = "_schwingnet_rag_for_tools"
# The parts --grid varies: those that change which passages a question finds.
SEARCH_PARTS = ("chunk", "tokens", "index", "retrieve")
# Passages kept for a scored question (recall reads the first 5, the reciprocal rank all of them),
# printed by ask, and given to Claude by the site's box.
EVAL_K, ASK_K, SITE_K = 10, 8, 8
MIN_QUESTIONS = 30


# The package, loaded by path


def _decorator_factory(*_args, **_kwargs):
    return lambda function: function


def _stand_ins():
    beartype = types.ModuleType("beartype")
    beartype.beartype = lambda function: function
    contracts = types.ModuleType("beethoven_qa.contracts")
    contracts.require = contracts.ensure = _decorator_factory
    qa = types.ModuleType("beethoven_qa")
    qa.contracts = contracts
    return {"beartype": beartype, "beethoven_qa": qa, "beethoven_qa.contracts": contracts}


@functools.cache
def package():
    """src/schwingnet/rag.py, loaded once from its file under a name of its own. The stand-ins sit
    in sys.modules only while it loads, so a real beartype or beethoven_qa already imported, as in
    the gate's environment, is left as it was."""
    spec = importlib.util.spec_from_file_location(MODULE, ROOT / PACKAGE)
    module = importlib.util.module_from_spec(spec)
    stand_ins = _stand_ins()
    saved = {name: sys.modules.get(name) for name in stand_ins}
    sys.modules.update(stand_ins)
    sys.modules[MODULE] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module


# Reading the book


def chapter_files(root, only=None):
    """The chapters under docs/textbook/ by name, the first of any number two files share; `only`,
    when given, keeps the files whose repository paths it holds."""
    kept = {}
    for path in sorted((root / BOOK).glob("[0-9][0-9]-*.md")):
        wanted = only is None or path.relative_to(root).as_posix() in only
        if CHAPTER_NAME.fullmatch(path.name) and wanted and path.name[:2] not in kept:
            kept[path.name[:2]] = path
    return list(kept.values())


def read_chapters(root, only=None):
    rag = package()
    out = []
    for path in chapter_files(root, only):
        text = path.read_text(encoding="utf-8")
        found = TITLE_LINE.fullmatch(text.split("\n", 1)[0].strip())
        title = found.group(1).strip() if found else path.stem[3:].replace("-", " ")
        out.append(rag.Chapter(path.relative_to(root).as_posix(), path.name[:2], title, text))
    return out


def is_figure(path):
    """A JSON under figures/ is a figure's record when an image or a page of its name stands beside
    it, the rule tools/textbook_site.py reads them by; any other JSON there is a figure's data."""
    return any(path.with_suffix(ext).exists() for ext in (".svg", ".png", ".html"))


def record_files(root):
    base = root / FIGURES
    return [p for p in sorted(base.glob("*/*.json")) if is_figure(p)] if base.is_dir() else []


def read_records(root):
    """Every figure record of the book, as its file holds it, each with its id."""
    out = []
    for path in record_files(root):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict):
            record.setdefault("id", path.relative_to(root / FIGURES).with_suffix("").as_posix())
            out.append(record)
    return out


def _words(value, template):
    return template.format(value) if isinstance(value, str) and value.strip() else ""


def figure_text(record):
    """The prose of a figure's record as one passage: its caption, what it is about, its grade and
    status, and its source's notes."""
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    graded = " ".join(w for w in (_words(record.get("grade"), "Grade: {}."),
                                  _words(record.get("status"), "Status: {}.")) if w)
    parts = (_words(record.get("caption"), "{}"), _words(record.get("about"), "{}"), graded,
             _words(source.get("notes"), "{}"))
    return "\n\n".join(p for p in parts if p)


def figures_of(records):
    """The package's Figure for each record with an id, the first of any id two records share."""
    rag = package()
    seen, out = set(), []
    for r in records:
        fid = r.get("id")
        if isinstance(fid, str) and fid and fid not in seen:
            seen.add(fid)
            title = r.get("title") if isinstance(r.get("title"), str) else fid
            out.append(rag.Figure(fid, str(r.get("chapter") or ""), title, figure_text(r)))
    return out


def build(root, choice, records=None, only=None):
    """The passages and the index of the book under root by the blocks chosen: the chapters, and,
    under chunk=figure, the figure records given, or the book's own when none are."""
    rag = package()
    chapters = read_chapters(root, only)
    figures = []
    if choice.chunk == "figure":
        figures = figures_of(read_records(root) if records is None else records)
    chunks = rag.chunk(chapters, figures, choice.chunk)
    return chunks, rag.build_index(chunks, choice.index, choice.tokens)


def search(chunks, index, choice, question, k):
    """The passages kept for a question, best first."""
    rag = package()
    ranked = rag.score(index, question)
    return [chunks[d] for d in rag.retrieve(ranked, [c.chapter for c in chunks], choice.retrieve, k)]


# What is written


def chunk_record(c):
    return {"id": c.id, "file": c.file, "chapter": c.chapter, "title": c.title, "heading": c.heading,
            "anchor": c.anchor, "line": c.line, "text": c.text, "figures": list(c.figures)}


def link_of(c):
    """Where a passage is read in the site: its chapter's page at its section."""
    if not c.chapter:
        return "figures.html"
    return f"chapter-{c.chapter}.html" + (f"#{c.anchor}" if c.anchor else "")


def site_index(index, choice):
    """The index as the box reads it: the package's record of it, with the blocks it was built by,
    the instructions their answer block gives Claude and how many passages a question shows."""
    rag = package()
    return {"version": 1, "blocks": rag.as_record(choice), "instructions": rag.instructions(choice.answer),
            "k": SITE_K, **rag.index_record(index)}


def commit_of(root):
    try:
        done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "not recorded"
    return done.stdout.strip() or "not recorded"


def sources(root, choice, only=None):
    """The sha256 of every file the build read, by its repository path."""
    paths = chapter_files(root, only) + (record_files(root) if choice.chunk == "figure" else [])
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def manifest(root, choice, chunks, index):
    rag = package()
    return {"blocks": rag.as_record(choice), "words": rag.words_of(choice), "passages": len(chunks),
            "vocabulary": len(index.vocabulary), "commit": commit_of(root), "sources": sources(root, choice),
            "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def dump(path, data, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, separators=(",", ":")) if compact else json.dumps(data, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


# The measures


def load_questions(root):
    return json.loads((root / QUESTIONS).read_text(encoding="utf-8"))


def score_question(chunks, index, choice, question):
    rag = package()
    found = search(chunks, index, choice, question["question"], EVAL_K)
    files, figure = [c.file for c in found], question.get("figure")
    return {"id": question["id"], "recall": rag.recall_at(files, question["chapters"], 5),
            "rr": rag.reciprocal_rank(files, question["chapters"]),
            "figure": any(figure in c.figures for c in found[:5]) if figure else None,
            "top": [c.chapter for c in found[:3]]}


def mean(values):
    values = list(values)
    return round(math.fsum(values) / len(values), 3) if values else None


def evaluate(chunks, index, choice, questions):
    """One block set's measures over the questions, with the questions it missed at 5."""
    rows = [score_question(chunks, index, choice, q) for q in questions]
    rag = package()
    return {"set": " ".join(rag.words_of(choice)) or "version 1", "blocks": rag.as_record(choice),
            "passages": len(chunks), "recall_at_5": mean(r["recall"] for r in rows),
            "mrr": mean(r["rr"] for r in rows),
            "figure_at_5": mean(float(r["figure"]) for r in rows if r["figure"] is not None),
            "misses": [r["id"] for r in rows if r["recall"] == 0.0], "_rows": rows}


def block_sets(base, vary, grid):
    """The sets eval scores: the base, one set for each --vary word, or every set of the search's
    parts, the base's answer and embed kept."""
    rag = package()
    if grid:
        names = [rag.CHOICES[part] for part in SEARCH_PARTS]
        return [replace(base, **dict(zip(SEARCH_PARTS, values, strict=True)))
                for values in itertools.product(*names)]
    sets = [base] + [replace(base, **vars(rag.parse([word]))) for word in vary]
    return [s for n, s in enumerate(sets) if s not in sets[:n]]


def evaluate_sets(root, sets, questions):
    built = {}
    results = []
    for choice in sets:
        key = (choice.chunk, choice.tokens, choice.index)
        if key not in built:
            built[key] = build(root, choice)
        results.append(evaluate(*built[key], choice, questions))
    return results


# Checking the questions


def question_problems(root, question, figures):
    name = question.get("id") or "a question with no id"
    out = []
    if not isinstance(question.get("question"), str) or not question["question"].strip():
        out.append(f"{name}: no question")
    files = question.get("chapters")
    if not isinstance(files, list) or not files:
        out.append(f"{name}: no chapter that answers it")
        files = []
    for f in files:
        if not (isinstance(f, str) and CHAPTER_NAME.fullmatch(Path(f).name) and (root / f).is_file()):
            out.append(f"{name}: {f} is not a chapter of the book")
    if question.get("figure") and question["figure"] not in figures:
        out.append(f"{name}: figure {question['figure']} has no record")
    return out


def questions_problems(root, data):
    """What is wrong with the questions file, in words; empty when it holds."""
    questions = data.get("questions") if isinstance(data.get("questions"), list) else []
    out = [f"{len(questions)} questions; at least {MIN_QUESTIONS} are needed"] if len(questions) < MIN_QUESTIONS else []
    ids = [q.get("id") for q in questions]
    out += [f"question id {i!r} is used twice" for i in sorted({str(i) for i in ids if ids.count(i) > 1})]
    figures = {r.get("id") for r in read_records(root)}
    for q in questions:
        out += question_problems(root, q, figures)
    floor = data.get("floor") if isinstance(data.get("floor"), dict) else {}
    for measure in ("recall_at_5", "mrr"):
        value = floor.get(measure)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            out.append(f"the floor's {measure} is not a share from 0 to 1")
    return out


def below_floor(result, floor):
    return [f"{m} {result[m]} is below the floor {floor[m]}" for m in ("recall_at_5", "mrr") if result[m] < floor[m]]


# Printing


def where(c):
    figures = f" (figure {', '.join(c.figures)})" if c.figures else ""
    return f"Chapter {c.chapter} {c.title}: {c.heading}{figures}"


def print_passages(found):
    for n, c in enumerate(found, 1):
        print(f"[{n}] {where(c)}")
        print(f"    {c.file}, line {c.line}; in the site {link_of(c)}")
        print(f"    {c.text}\n")


def print_results(results, questions):
    print(f"{'set':42} {'passages':>8} {'recall@5':>8} {'MRR':>6} {'fig@5':>6} misses")
    for r in results:
        fig = "-" if r["figure_at_5"] is None else f"{r['figure_at_5']:.3f}"
        print(f"{r['set'][:42]:42} {r['passages']:>8} {r['recall_at_5']:>8.3f} {r['mrr']:>6.3f} {fig:>6} "
              f"{len(r['misses'])}")
    by_id = {q["id"]: q for q in questions}
    for r in results:
        rows = {row["id"]: row for row in r["_rows"]}
        for qid in r["misses"]:
            gold = ", ".join(Path(f).name[:2] for f in by_id[qid]["chapters"])
            found = ", ".join(rows[qid]["top"]) or "nothing"
            print(f"miss ({r['set']}): {qid}: wanted chapter {gold}, found {found}: {by_id[qid]['question']}")


# The site's box


def esc(text):
    return html.escape(str(text))


def box_html(repo, subject, record, button):
    """The Ask the book box for a page of the site, the page's Ask Claude button (`button`, as the
    site writes it) in its row. It sits in a buttons row, which the claude.ai edition's own Ask
    Claude leaves out of the page text it reads; repo, subject and record are what the button's
    issue names, and the box's script adds the question and the passages found to it."""
    return (f'<div class="buttons asks"><div class="ask-book" id="ask-book" data-repo="{esc(repo)}" '
            f'data-subject="{esc(subject)}" data-record="{esc(record)}">'
            '<link rel="stylesheet" href="rag/box.css">'
            '<label class="ab-label" for="ab-q">Ask the book</label>'
            '<form class="ab-row" role="search"><input id="ab-q" class="ab-q" type="search" '
            'placeholder="A question, in your own words" autocomplete="off" enterkeyhint="search">'
            '<button type="submit" class="ab-go">Search</button>'
            '<button type="button" class="ab-stop" hidden>Stop</button>' + button + '</form>'
            '<p class="ab-hint">Searches the whole book here in your browser and links each passage to its '
            'section. Ask Claude opens the question, with the passages found, as an issue in the '
            'repository.</p><p class="ab-status" role="status"></p>'
            '<div class="ab-answer" hidden><div class="ab-said"></div><p class="ab-note"></p>'
            '<p class="ab-sources-title">Sources</p><ol class="ab-sources"></ol></div>'
            '<ol class="ab-results"></ol></div>'
            '<script src="rag/search.js" defer></script><script src="rag/box.js" defer></script></div>')


def write_site(out, root, only=None, records=None):
    """The box's files in a built site, under out (the site's rag/): version 1's index and passages,
    which carry no clock and no commit, so one commit builds the same bytes twice, with the
    browser's mirror, the box's script and its style; the number of passages."""
    rag = package()
    chunks, index = build(Path(root), rag.DEFAULT, records, only)
    out = Path(out)
    dump(out / "index.json", site_index(index, rag.DEFAULT), compact=True)
    dump(out / "chunks.json", [chunk_record(c) for c in chunks], compact=True)
    for name, text in (("search.js", SEARCH_JS), ("box.js", BOX_JS), ("box.css", BOX_CSS)):
        (out / name).write_text(text, encoding="utf-8")
    return len(chunks)


# The browser's mirror of the package's tokens, score, retrieve and prompt: the same arithmetic in
# the same order, held to tests/fixtures/rag-scoring.json with the package (tests/test_rag_tool.py).
# The stop words, the suffix rules and the BM25 settings come from the index, so a change to them
# in the package reaches the browser with the next build.
SEARCH_JS = r"""// The book's search in the reader's browser (tools/rag.py): a mirror of src/schwingnet/rag.py's
// tokens, score, retrieve and prompt, held to the same outputs by tests/fixtures/rag-scoring.json.
var SchwingRag = (function () {
  "use strict";
  function words(text) {
    var lowered = String(text).replace(/[A-Z]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) + 32); });
    return lowered.match(/[a-z0-9]+/g) || [];
  }
  function stem(word, index) {
    for (var i = 0; i < index.suffixes.length; i++) {
      var suffix = index.suffixes[i][0], replacement = index.suffixes[i][1];
      var left = word.length - suffix.length + replacement.length;
      if (word.endsWith(suffix) && left >= index.shortest) {
        var kept = suffix === "s" && index.keep.some(function (end) { return word.endsWith(end); });
        return kept ? word : word.slice(0, word.length - suffix.length) + replacement;
      }
    }
    return word;
  }
  function tokens(text, p) {
    return words(text).filter(function (w) { return !p.stop.has(w); }).map(function (w) {
      return p.index.tokens === "stem" ? stem(w, p.index) : w;
    });
  }
  // The index ready to score, with each passage's chapter for retrieve.
  function prepare(index, chunks) {
    var rows = new Map(), total = 0;
    index.vocabulary.forEach(function (w, i) { rows.set(w, i); });
    index.lengths.forEach(function (n) { total += n; });
    return {index: index, rows: rows, stop: new Set(index.stopwords),
            average: total > 0 ? total / index.lengths.length : 1,
            chapters: (chunks || []).map(function (c) { return c.chapter; }),
            retrieve: (index.blocks && index.blocks.retrieve) || "top"};
  }
  function add(p, row, totals) {
    var index = p.index, post = index.postings[row], idf = index.idf[row];
    for (var i = 0; i < post.length; i += 2) {
      var doc = post[i], value = post[i + 1];
      var part = index.kind === "tfidf" ? value
        : idf * (value * (index.k1 + 1)) / (value + index.k1 * (1 - index.b + index.b * index.lengths[doc] / p.average));
      totals.set(doc, (totals.has(doc) ? totals.get(doc) : 0) + part);
    }
  }
  function score(p, question) {
    var totals = new Map(), seen = new Set(), ranked = [];
    tokens(question, p).forEach(function (w) {
      if (seen.has(w) || !p.rows.has(w)) return;
      seen.add(w);
      add(p, p.rows.get(w), totals);
    });
    totals.forEach(function (total, doc) { if (total > 0) ranked.push([doc, total]); });
    return ranked.sort(function (x, y) { return y[1] - x[1] || x[0] - y[0]; });
  }
  function retrieve(ranked, chapters, rule, k, perChapter) {
    var kept = [], taken = new Map();
    for (var i = 0; i < ranked.length && kept.length < k; i++) {
      var doc = ranked[i][0], chapter = chapters[doc], n = taken.get(chapter) || 0;
      if (rule === "spread" && n >= perChapter) continue;
      kept.push(doc);
      taken.set(chapter, n + 1);
    }
    return kept;
  }
  function search(p, question, k) {
    return retrieve(score(p, question), p.chapters, p.retrieve, k, p.index.per_chapter);
  }
  function passage(n, c) {
    var figures = c.figures && c.figures.length ? " (figure " + c.figures.join(", ") + ")" : "";
    return "[" + n + "] Chapter " + c.chapter + " " + c.title + ", " + c.heading + figures + ":\n" + c.text;
  }
  function prompt(instructions, question, passages) {
    var shown = passages.map(function (c, i) { return passage(i + 1, c); });
    return [instructions, "Passages:"].concat(shown, ["Question: " + question]).join("\n\n");
  }
  return {words: words, stem: stem, tokens: tokens, prepare: prepare, score: score, retrieve: retrieve,
          search: search, passage: passage, prompt: prompt};
})();
if (typeof module === "object" && module.exports) module.exports = SchwingRag;
"""

# The box: the search on every page, and the answer where the artifact runtime gives the page sample.
BOX_JS = r"""// Ask the book (tools/rag.py): the search box of the textbook's pages. The book's index is fetched
// once and a question is scored here, in the reader's browser, by rag/search.js; the box lists the
// best passages, each linked to its section, and gives the page's Ask Claude button the question
// with the passages found. Inside the claude.ai viewer, where the artifact runtime gives the page
// sample, the box also answers: Claude reads the passages, may search the book again through the
// search_textbook tool, and cites what it used. Nothing calls Claude before the reader asks, since
// a call spends the reader's own usage and the first one asks the reader's consent.
(function () {
  "use strict";
  var box = document.getElementById("ask-book");
  if (!box || typeof SchwingRag === "undefined") return;
  function part(name) { return box.querySelector("." + name); }
  var form = part("ab-row"), input = part("ab-q"), go = part("ab-go"), stop = part("ab-stop");
  var hint = part("ab-hint"), status = part("ab-status"), list = part("ab-results");
  var answer = part("ab-answer"), said = part("ab-said"), note = part("ab-note"), sources = part("ab-sources");
  var ask = box.querySelector("a.button.ask");
  var repo = box.getAttribute("data-repo") || "", subject = box.getAttribute("data-subject") || "";
  var record = box.getAttribute("data-record") || "";
  var book = null, loading = null, sample = null, withTools = false, controller = null, turn = 0;
  var GONE = ["not_granted", "sampling_disabled", "not_declared", "capability_disabled", "capability_removed"];
  var CLIP = 2400; // characters of a passage the search tool returns, so eight stay under its 32 KB

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c];
    });
  }
  function load() {
    if (book) return Promise.resolve(book);
    if (!loading) {
      loading = Promise.all([fetch("rag/index.json"), fetch("rag/chunks.json")]).then(function (r) {
        if (!r[0].ok || !r[1].ok) throw new Error("the book's index is not here");
        return Promise.all([r[0].json(), r[1].json()]);
      }).then(function (got) {
        book = {index: got[0], chunks: got[1], p: SchwingRag.prepare(got[0], got[1])};
        return book;
      }).catch(function (e) { loading = null; throw e; });
    }
    return loading;
  }
  function find(question, k) {
    return SchwingRag.search(book.p, question, k).map(function (doc) { return book.chunks[doc]; });
  }
  function where(c) { return (c.chapter ? "Chapter " + c.chapter + " " + c.title + ": " : "") + c.heading; }
  function href(c) {
    return c.chapter ? "chapter-" + c.chapter + ".html" + (c.anchor ? "#" + c.anchor : "") : "figures.html";
  }
  function excerpt(text, wanted) {
    // About sixty words from just before the first word the question shares, the shared words marked.
    var all = text.split(/\s+/), first = 0;
    function hit(w) { return SchwingRag.tokens(w, book.p).some(function (t) { return wanted.has(t); }); }
    while (first < all.length && !hit(all[first])) first++;
    var from = first < all.length ? Math.max(0, first - 15) : 0, to = Math.min(all.length, from + 60);
    var shown = all.slice(from, to).map(function (w) { return hit(w) ? "<mark>" + esc(w) + "</mark>" : esc(w); });
    return (from > 0 ? "... " : "") + shown.join(" ") + (to < all.length ? " ..." : "");
  }
  function showPassages(found, question) {
    var wanted = new Set(SchwingRag.tokens(question, book.p));
    list.innerHTML = found.map(function (c) {
      return '<li><a class="ab-where" href="' + esc(href(c)) + '">' + esc(where(c)) + '</a><span class="ab-text">' +
        excerpt(c.text, wanted) + "</span></li>";
    }).join("");
  }
  function issueHref(question, found) {
    var lines = ["@claude", "", "About: " + subject, "Its record: " + record, "", "My question: " + question, ""];
    if (found.length) {
      lines.push("The book's search found these passages for it (python3 tools/rag.py ask gives the same):");
      found.forEach(function (c) { lines.push("- " + where(c) + " (" + c.file + ", line " + c.line + ")"); });
      lines.push("");
    }
    var query = new URLSearchParams({title: "Ask Claude: " + question.slice(0, 80), body: lines.join("\n")});
    return "https://github.com/" + repo + "/issues/new?" + query.toString();
  }

  function cite(text, given) {
    // [2] and [2, 5] become links to the passages Claude was given under those numbers.
    return esc(text).replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, function (all, numbers) {
      return "[" + numbers.split(/\s*,\s*/).map(function (n) {
        var c = given[Number(n) - 1];
        return c ? '<a href="' + esc(href(c)) + '" title="' + esc(where(c)) + '">' + n + "</a>" : n;
      }).join(", ") + "]";
    });
  }
  function showSources(given) {
    sources.innerHTML = given.map(function (c) {
      return '<li><a href="' + esc(href(c)) + '">' + esc(where(c)) + "</a></li>";
    }).join("");
  }
  function searchTool(given) {
    return {
      name: "search_textbook",
      description: "Searches the SchwingNet textbook for the passages that best match a query and returns them, " +
        "numbered as they may be cited, each with its chapter and heading. Use it when the passages given do not answer.",
      inputSchema: {type: "object", required: ["query"], properties: {
        query: {type: "string", description: "The words to search for"},
        k: {type: "integer", description: "How many passages, 1 to 8; 5 when left out"}}},
      execute: function (args) {
        var query = String((args && args.query) || "").trim();
        if (!query) throw new Error("the query is empty");
        var k = Math.max(1, Math.min(8, Math.floor(Number(args.k)) || 5));
        status.textContent = 'Claude searched the book for "' + query + '".';
        var found = find(query, k);
        if (!found.length) return "No passage of the book shares a word with that query; try other words.";
        return found.map(function (c) {
          var n = given.indexOf(c);
          if (n < 0) { given.push(c); n = given.length - 1; showSources(given); }
          var clipped = c.text.length > CLIP ? Object.assign({}, c, {text: c.text.slice(0, CLIP) + " ..."}) : c;
          return SchwingRag.passage(n + 1, clipped);
        }).join("\n\n");
      }
    };
  }
  function copyFor(code) {
    if (code === "rate_limited") return "Claude is busy, or your usage limit is reached: wait a minute and ask again.";
    if (code === "cancelled") return "Stopped.";
    if (code === "refused") return "Claude would not answer that as asked; the passages are listed above.";
    return "Claude could not answer this time (" + code + "); the passages it was given are listed above.";
  }
  function noClaude(words) {
    sample = null; withTools = false;
    box.classList.remove("can-answer");
    go.textContent = "Search";
    answer.hidden = true; list.hidden = false;
    if (words) hint.textContent = words;
  }
  function answerWith(question, found, mine) {
    var given = found.slice();
    var options = {onText: function (u) { if (mine === turn) said.innerHTML = cite(u.text, given); }};
    if (withTools) options.tools = [searchTool(given)];
    controller = new AbortController();
    options.signal = controller.signal;
    answer.hidden = false; list.hidden = true; stop.hidden = false;
    said.textContent = "Thinking..."; note.textContent = "";
    showSources(given);
    sample(SchwingRag.prompt(book.index.instructions, question, found), options).then(function (r) {
      if (mine !== turn) return;
      said.innerHTML = cite(r.text, given);
      note.textContent = r.truncated ? "The answer was cut short; ask for less at a time." : "";
    }, function (e) {
      if (mine !== turn) return;
      var code = (e && e.code) || "upstream_error", kept = code === "refused" ? "" : (e && e.text) || "";
      if (GONE.indexOf(code) >= 0) { noClaude("Claude may not answer on this page, so the box searches the book only."); return; }
      if (code === "tools_unavailable") withTools = false;
      said.innerHTML = cite(kept, given);
      note.textContent = copyFor(code);
      list.hidden = !!kept;
    }).then(function () { if (mine === turn) { stop.hidden = true; controller = null; } });
  }

  function run(event) {
    if (event) event.preventDefault();
    var question = input.value.replace(/\s+/g, " ").trim();
    if (!question) { input.focus(); return; }
    var mine = ++turn;
    if (controller) { controller.abort(); controller = null; }
    status.textContent = "Searching the book...";
    load().then(function () {
      if (mine !== turn) return;
      var found = find(question, book.index.k || 8);
      showPassages(found, question);
      if (ask && repo) ask.href = issueHref(question, found);
      answer.hidden = true; list.hidden = false; stop.hidden = true;
      status.textContent = found.length ? "The " + found.length + " passages that match best, best first."
        : "No passage shares a word with the question; try other words.";
      if (sample && (found.length || withTools)) answerWith(question, found, mine);
    }, function () {
      if (mine === turn) status.textContent = "The book's index could not be read here, so the search is off on this copy.";
    });
  }
  form.addEventListener("submit", run);
  stop.addEventListener("click", function () { if (controller) controller.abort(); });

  function useClaude(fn) {
    sample = fn;
    box.classList.add("can-answer");
    go.textContent = "Ask";
    hint.textContent = "Claude answers from the passages the search finds, citing each by its number, on your own " +
      "Claude account; your first question asks your consent. Ask Claude opens the question in the repository instead.";
    if (typeof fn.limits === "function") {
      fn.limits().then(function (l) { withTools = !!(l && l.tools && l.tools.maxCount > 0); }, function () {});
    }
  }
  (function wait(tries) {
    // Inside the viewer window.claude is there before any page script runs; elsewhere it never comes.
    if (window.claude && typeof window.claude.use === "function") {
      window.claude.use("sample").then(function (fn) { if (fn) useClaude(fn); }, function () {});
    } else if (tries < 40) {
      setTimeout(function () { wait(tries + 1); }, 100);
    }
  })(0);
})();
"""

BOX_CSS = """/* Ask the book (tools/rag.py): the search box, in the site's own colours, light and dark. */
.ask-book { flex:1 1 100%; min-width:0; border:1px solid var(--line, #ddd); border-radius:10px; padding:10px 14px 12px;
            background:var(--soft, var(--panel, #f6f3ec)); }
.ask-book .ab-label { display:block; font-weight:600; font-size:15px; margin:0 0 6px; }
.ask-book .ab-row { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:0; }
.ask-book .ab-q { flex:1 1 240px; min-width:0; padding:7px 10px; border:1px solid var(--line, #ccc); border-radius:8px;
                  background:var(--bg, #fff); color:var(--fg, #222); font:inherit; font-size:15px; }
.ask-book .ab-row button { border:1px solid var(--accent, #2a5db0); border-radius:6px; padding:4px 14px; font:inherit;
                           font-size:13.5px; cursor:pointer; background:var(--accent, #2a5db0); color:var(--bg, #fff); }
.ask-book .ab-row button.ab-stop { background:transparent; color:var(--accent, #2a5db0); }
.ask-book .ab-row .button.ask { padding:4px 12px; }
.ask-book .ab-hint, .ask-book .ab-status, .ask-book .ab-note { color:var(--muted, #666); font-size:13px; margin:6px 0 0; }
.ask-book .ab-status:empty, .ask-book .ab-note:empty { display:none; }
.ask-book .ab-results, .ask-book .ab-sources { margin:8px 0 0; padding-left:24px; }
.ask-book .ab-results li { margin:8px 0; font-size:14.5px; line-height:1.45; }
.ask-book .ab-where { font-weight:600; }
.ask-book .ab-text { display:block; margin-top:2px; overflow-wrap:anywhere; }
.ask-book mark { background:rgba(224,168,90,.38); color:inherit; border-radius:2px; padding:0 1px; }
.ask-book .ab-answer { margin:10px 0 0; padding:10px 12px; border-left:3px solid var(--ok, #3f7a3a);
                       background:var(--panel, #fff); border-radius:6px; }
.ask-book .ab-said { white-space:pre-wrap; font-size:15px; line-height:1.5; }
.ask-book .ab-sources-title { font-weight:600; font-size:13.5px; margin:10px 0 0; }
.ask-book .ab-sources li { font-size:13.5px; margin:3px 0; }
"""


# The commands


def cmd_parts(_args):
    rows = package().parts()
    print(f"{'part':10} {'names':28} version 1")
    for row in rows:
        print(f"{row['part']:10} {row['choices']:28} {row['default']}")
    return 0


def cmd_ask(args):
    rag = package()
    choice = rag.parse(args.block)
    chunks, index = build(Path(args.root), choice)
    question = " ".join(args.question.split())
    found = search(chunks, index, choice, question, args.k)
    if args.prompt:
        print(rag.prompt(choice.answer, question, found))
        return 0
    words = " ".join(rag.words_of(choice)) or "version 1"
    print(f"Ask the book ({words}, {len(chunks)} passages): {question}\n")
    print_passages(found)
    if not found:
        print("No passage shares a word with the question; try other words.")
    return 0


def cmd_build(args):
    rag = package()
    choice = rag.parse(args.block)
    root = Path(args.root)
    chunks, index = build(root, choice)
    out = Path(args.out)
    dump(out / "index.json", site_index(index, choice), compact=True)
    dump(out / "chunks.json", [chunk_record(c) for c in chunks], compact=True)
    dump(out / "manifest.json", manifest(root, choice, chunks, index))
    print(f"rag build: {len(chunks)} passages, {len(index.vocabulary)} words, written to {out}")
    return 0


def cmd_eval(args):
    rag, root = package(), Path(args.root)
    data = load_questions(root)
    results = evaluate_sets(root, block_sets(rag.parse(args.block), args.vary, args.grid), data["questions"])
    print_results(results, data["questions"])
    if args.write:
        record = {"about": "The measures of tools/rag.py eval over docs/textbook/rag/questions.json, "
                           "one row for each block set tried; written by tools/rag.py eval --write.",
                  "commit": commit_of(root), "questions": len(data["questions"]),
                  "sets": [{k: v for k, v in r.items() if k != "_rows"} for r in results]}
        dump(root / RECORD, record)
        print(f"written to {RECORD}")
    return 0


def cmd_check(args):
    """The questions file holds, and version 1 reaches its floor."""
    rag, root = package(), Path(args.root)
    data = load_questions(root)
    problems = questions_problems(root, data)
    if not problems:
        result = evaluate(*build(root, rag.DEFAULT), rag.DEFAULT, data["questions"])
        problems = below_floor(result, data["floor"])
        print(f"rag check: version 1 over {len(data['questions'])} questions: recall at 5 "
              f"{result['recall_at_5']:.3f} (floor {data['floor']['recall_at_5']}), MRR {result['mrr']:.3f} "
              f"(floor {data['floor']['mrr']})")
    for p in problems:
        print(f"rag check: {p}")
    return 1 if problems else 0


def fill_fixture(data):
    """The fixture with its outputs computed from its inputs by the package: the words of each text
    under each tokens block, each build's index record, each query's ranking with its scores and the
    passages kept, and the prompt."""
    rag = package()
    for t in data["texts"]:
        t.update(plain=rag.tokens(t["text"], "plain"), stem=rag.tokens(t["text"], "stem"))
    chunks = [rag.Chunk(**{**c, "figures": tuple(c["figures"])}) for c in data["chunks"]]
    chapters = [c.chapter for c in chunks]
    for b in data["builds"]:
        index = rag.build_index(chunks, b["index"], b["tokens"])
        b["record"] = rag.index_record(index)
        for q in b["queries"]:
            ranked = rag.score(index, q["question"])
            q["ranked"] = [[chunks[d].id, s] for d, s in ranked]
            q["kept"] = [chunks[d].id for d in rag.retrieve(ranked, chapters, b["retrieve"], b["k"])]
    p = data["prompt"]
    by_id = {c.id: c for c in chunks}
    p["instructions"] = rag.instructions(p["answer"])
    p["text"] = rag.prompt(p["answer"], p["question"], [by_id[i] for i in p["passages"]])
    return data


def cmd_fixture(_args):
    path = ROOT / FIXTURE
    dump(path, fill_fixture(json.loads(path.read_text(encoding="utf-8"))))
    print(f"rewritten {FIXTURE}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parts", help="every block with its names").set_defaults(run=cmd_parts)
    ask = sub.add_parser("ask", help="the passages a question finds")
    ask.add_argument("question")
    ask.add_argument("--k", type=int, default=ASK_K, help=f"how many passages ({ASK_K} by default)")
    ask.add_argument("--prompt", action="store_true", help="print the whole text Claude is given")
    out = sub.add_parser("build", help="write index.json, chunks.json and manifest.json")
    out.add_argument("--out", required=True, help="the folder to write into")
    scored = sub.add_parser("eval", help="score block sets by the questions file")
    scored.add_argument("--vary", action="append", default=[], metavar="KEY=VALUE",
                        help="a set that differs from --block's in this one part; may be repeated")
    scored.add_argument("--grid", action="store_true", help="every set of the parts that change the search")
    scored.add_argument("--write", action="store_true", help=f"keep the result as {RECORD}")
    for command in (ask, out, scored):
        command.add_argument("--block", action="append", default=[], metavar="KEY=VALUE",
                             help="choose a block by name (python3 tools/rag.py parts lists them)")
    floor = sub.add_parser("check", help="version 1 reaches the questions file's floor")
    for command in (ask, out, scored, floor):
        command.add_argument("--root", default=str(ROOT), help="the repository whose book is read (this one)")
    ask.set_defaults(run=cmd_ask)
    out.set_defaults(run=cmd_build)
    scored.set_defaults(run=cmd_eval)
    floor.set_defaults(run=cmd_check)
    sub.add_parser("fixture", help=f"rewrite the outputs of {FIXTURE}").set_defaults(run=cmd_fixture)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except package().RagError as fault:
        print(f"rag: {fault}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
