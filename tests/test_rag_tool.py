"""tools/rag.py, the book's search as a command and as the site's Ask the book box: build writes
its three files, ask prints the passages, eval and check score the questions file and hold its
floor, the site carries the index and the box, and the browser's mirror scores the shared fixture
exactly as the package does (node, as on the runners)."""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import rag  # noqa: E402

ONE = """# 01 One

Label: schwingnet-internal

The sacrum is the anchor the surgeon trusts, and the count runs up the sweep from it.

## Counting from the anchor

Each frame overlaps the last by two bodies, so the count carries from the anchor to the target.

![Figure 1.1](figures/01/a-figure.png)

## The decline rule

A frame that does not link to the one before it is declined, never named.
"""

TWO = """# 02 Two

## The latency budget

The budget is 97 ms a frame on the device in the operating room.
"""

# The mirror's own check: argv[2] is rag/search.js, argv[3] the fixture; every output must be the
# fixture's, scores compared to the bit by their shortest round-trip spelling.
MIRROR_CHECK = r"""
var R = require(process.argv[2]);
var data = JSON.parse(require("fs").readFileSync(process.argv[3], "utf8"));
var faults = [];
function same(what, got, want) {
  if (JSON.stringify(got) !== JSON.stringify(want)) faults.push(what + ": " + JSON.stringify(got) + " != " + JSON.stringify(want));
}
var rules = {};
data.builds.forEach(function (b) { rules[b.tokens] = rules[b.tokens] || R.prepare(b.record, data.chunks); });
data.texts.forEach(function (t, i) {
  same("text " + i + " plain", R.tokens(t.text, rules.plain), t.plain);
  same("text " + i + " stem", R.tokens(t.text, rules.stem), t.stem);
});
data.builds.forEach(function (b, n) {
  var p = R.prepare(b.record, data.chunks);
  b.queries.forEach(function (q) {
    var ranked = R.score(p, q.question);
    same("build " + n + " ranked " + q.question, ranked.map(function (r) { return [data.chunks[r[0]].id, r[1]]; }), q.ranked);
    var kept = R.retrieve(ranked, p.chapters, b.retrieve, b.k, b.record.per_chapter);
    same("build " + n + " kept " + q.question, kept.map(function (d) { return data.chunks[d].id; }), q.kept);
  });
});
var byId = {};
data.chunks.forEach(function (c) { byId[c.id] = c; });
var p = data.prompt;
same("prompt", R.prompt(p.instructions, p.question, p.passages.map(function (i) { return byId[i]; })), p.text);
if (faults.length) { console.log(faults.join("\n")); process.exit(1); }
console.log("ok");
"""


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def questions(floor, count=30, **extra):
    files = ["docs/textbook/01-one.md", "docs/textbook/02-two.md"]
    asked = [("Where does the count start, at the sacrum?", files[0]), ("What is the latency budget in ms?", files[1])]
    rows = [{"id": f"q{n}", "question": asked[n % 2][0], "chapters": [asked[n % 2][1]]} for n in range(count)]
    rows[0]["figure"] = "01/a-figure"
    return {"floor": floor, "questions": rows, **extra}


def small_book(root):
    write(root / "docs/textbook/01-one.md", ONE)
    write(root / "docs/textbook/02-two.md", TWO)
    write(root / "docs/textbook/figures/01/a-figure.json", json.dumps(
        {"id": "01/a-figure", "chapter": "01", "title": "The count from the anchor", "caption": "Frames linked from the sacrum.",
         "grade": "Measured", "status": "current", "source": {"notes": "Drawn from the sweep records."}}))
    write(root / "docs/textbook/figures/01/a-figure.png", "not an image")
    write(root / "docs/textbook/figures/01/data.json", json.dumps({"rows": [1, 2]}))
    write(root / rag.QUESTIONS, json.dumps(questions({"recall_at_5": 0.5, "mrr": 0.5})))


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = rag.main(list(argv))
    return code, out.getvalue()


class TheTool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        small_book(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parts_lists_every_block_with_its_names_and_version_1(self):
        code, out = run("parts")
        self.assertEqual(code, 0)
        for line in ("chunk      section, window, figure      section", "index      bm25, tfidf                  bm25",
                     "embed      none                         none"):
            self.assertIn(line, out)

    def test_build_writes_the_index_the_passages_and_the_manifest(self):
        out = Path(self.tmp.name) / "built"
        code, said = run("build", "--root", str(self.root), "--out", str(out))
        self.assertEqual(code, 0, said)
        index = json.loads((out / "index.json").read_text())
        chunks = json.loads((out / "chunks.json").read_text())
        made = json.loads((out / "manifest.json").read_text())
        self.assertEqual(index["blocks"], rag.package().as_record(rag.package().DEFAULT))
        self.assertEqual((index["kind"], index["tokens"], index["k"]), ("bm25", "plain", rag.SITE_K))
        self.assertIn("do not answer", index["instructions"])
        self.assertEqual(len(index["lengths"]), len(chunks), 5)
        self.assertEqual([c["id"] for c in chunks], ["01-1", "01-2", "01-3", "02-1", "02-2"][:len(chunks)])
        second = chunks[1]
        self.assertEqual((second["file"], second["heading"], second["anchor"], second["figures"]),
                         ("docs/textbook/01-one.md", "Counting from the anchor", "counting-from-the-anchor", ["01/a-figure"]))
        self.assertEqual(made["passages"], len(chunks))
        self.assertEqual(made["words"], [])
        self.assertEqual(made["commit"], "not recorded")
        self.assertEqual(sorted(made["sources"]), ["docs/textbook/01-one.md", "docs/textbook/02-two.md"])
        self.assertEqual(len(made["sources"]["docs/textbook/01-one.md"]), 64)
        self.assertRegex(made["built"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_chunk_figure_reads_the_records_and_hashes_them(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "--allow-empty", "-m", "start"], check=True)
        out = Path(self.tmp.name) / "built"
        run("build", "--root", str(self.root), "--out", str(out), "--block", "chunk=figure")
        chunks = json.loads((out / "chunks.json").read_text())
        made = json.loads((out / "manifest.json").read_text())
        figure = [c for c in chunks if c["id"] == "fig-01/a-figure"][0]
        self.assertEqual((figure["heading"], figure["anchor"]), ("The count from the anchor", "fig-01-a-figure"))
        self.assertIn("Grade: Measured. Status: current.", figure["text"])
        self.assertIn("docs/textbook/figures/01/a-figure.json", made["sources"])
        self.assertNotIn("docs/textbook/figures/01/data.json", made["sources"])
        self.assertEqual(made["words"], ["chunk=figure"])
        self.assertRegex(made["commit"], r"^[0-9a-f]{40}$")

    def test_ask_prints_the_passages_with_their_chapter_file_and_place(self):
        code, out = run("ask", "--root", str(self.root), "What is the latency budget?", "--k", "2")
        self.assertEqual(code, 0)
        self.assertIn("[1] Chapter 02 Two: The latency budget", out)
        self.assertIn("docs/textbook/02-two.md, line 3; in the site chapter-02.html#the-latency-budget", out)
        self.assertIn("The budget is 97 ms", out)
        self.assertNotIn("[3]", out)
        code, out = run("ask", "--root", str(self.root), "zzz qqq")
        self.assertIn("No passage shares a word", out)

    def test_ask_prompt_prints_what_claude_is_given(self):
        code, out = run("ask", "--root", str(self.root), "  When is a frame declined? ", "--prompt", "--block", "answer=brief")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith(rag.package().instructions("brief")))
        self.assertIn("[1] Chapter 01 One, The decline rule:", out)
        self.assertTrue(out.rstrip().endswith("Question: When is a frame declined?"))

    def test_a_bad_block_is_refused_in_words(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code, _out = run("ask", "--root", str(self.root), "q", "--block", "index=dense")
        self.assertEqual(code, 2)
        self.assertIn("index='dense' is not one of bm25, tfidf", err.getvalue())

    def test_eval_scores_each_set_and_names_the_misses(self):
        code, out = run("eval", "--root", str(self.root), "--vary", "index=tfidf", "--vary", "chunk=window", "--write")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("set"))
        self.assertTrue(lines[1].startswith("version 1"))
        self.assertTrue(lines[2].startswith("index=tfidf"))
        self.assertTrue(lines[3].startswith("chunk=window"))
        record = json.loads((self.root / rag.RECORD).read_text())
        self.assertEqual([s["set"] for s in record["sets"]], ["version 1", "index=tfidf", "chunk=window"])
        self.assertEqual(record["questions"], 30)
        self.assertEqual(record["sets"][0]["recall_at_5"], 1.0)
        self.assertEqual(record["sets"][0]["figure_at_5"], 1.0)
        self.assertNotIn("_rows", record["sets"][0])

    def test_grid_tries_every_set_of_the_search_parts(self):
        package = rag.package()
        sets = rag.block_sets(package.DEFAULT, [], True)
        self.assertEqual(len(sets), 3 * 2 * 2 * 2)
        self.assertEqual(sets[0], package.DEFAULT)
        self.assertEqual(rag.block_sets(package.DEFAULT, ["index=bm25"], False), [package.DEFAULT])

    def test_check_passes_at_its_floor_and_fails_below_it(self):
        code, out = run("check", "--root", str(self.root))
        self.assertEqual(code, 0, out)
        self.assertIn("recall at 5 1.000 (floor 0.5)", out)
        data = questions({"recall_at_5": 0.5, "mrr": 1.0})
        data["questions"][1]["chapters"] = ["docs/textbook/01-one.md"]
        write(self.root / rag.QUESTIONS, json.dumps(data))
        code, out = run("check", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("mrr", out)
        self.assertIn("is below the floor 1.0", out)

    def test_check_refuses_a_questions_file_that_does_not_hold(self):
        data = questions({"recall_at_5": 2, "mrr": 0.5}, count=29)
        data["questions"][1].update(id="q0", chapters=["docs/textbook/09-gone.md"], figure="09/none")
        data["questions"][2]["question"] = " "
        write(self.root / rag.QUESTIONS, json.dumps(data))
        code, out = run("check", "--root", str(self.root))
        self.assertEqual(code, 1)
        for said in ("29 questions; at least 30", "question id 'q0' is used twice", "docs/textbook/09-gone.md is not a chapter",
                     "figure 09/none has no record", "q2: no question", "the floor's recall_at_5 is not a share"):
            self.assertIn(said, out)

    def test_the_package_loads_without_its_outside_imports_and_leaves_sys_modules_alone(self):
        self.assertTrue(callable(rag.package().score))
        for name in ("beartype", "beethoven_qa", "beethoven_qa.contracts"):
            module = sys.modules.get(name)
            self.assertFalse(module is not None and getattr(module, "__file__", None) is None,
                             f"{name} was left as a stand-in")

    def test_the_repositorys_questions_hold(self):
        data = rag.load_questions(ROOT)
        self.assertEqual(rag.questions_problems(ROOT, data), [])
        self.assertGreaterEqual(len(data["questions"]), rag.MIN_QUESTIONS)


class TheSite(unittest.TestCase):
    def test_write_site_writes_the_same_bytes_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            small_book(root)
            first, second = Path(tmp) / "a", Path(tmp) / "b"
            self.assertEqual(rag.write_site(first, root), rag.write_site(second, root))
            names = sorted(p.name for p in first.iterdir())
            self.assertEqual(names, ["box.css", "box.js", "chunks.json", "index.json", "search.js"])
            for name in names:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)
            only = rag.write_site(Path(tmp) / "c", root, {"docs/textbook/02-two.md"})
            self.assertEqual(only, 1)

    def test_the_box_keeps_the_pages_ask_claude_button_in_its_row(self):
        box = rag.box_html("OWNER/NAME", 'chapter 01 "One"', "docs/textbook/01-one.md", '<a class="button ask" href="x">Ask Claude</a>')
        self.assertTrue(box.startswith('<div class="buttons asks"><div class="ask-book" id="ask-book" data-repo="OWNER/NAME"'))
        self.assertIn('data-subject="chapter 01 &quot;One&quot;"', box)
        self.assertIn('<a class="button ask" href="x">Ask Claude</a></form>', box)
        self.assertIn('<script src="rag/search.js" defer></script><script src="rag/box.js" defer></script>', box)

    def test_the_site_build_carries_the_index_and_a_box_on_the_front_page_and_each_chapter(self):
        import test_textbook_site
        import textbook_site
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            test_textbook_site.small_book(root)
            out = Path(tmp) / "site"
            with contextlib.redirect_stdout(io.StringIO()):
                textbook_site.main([str(out), "--root", str(root), "--repo", "OWNER/NAME", "--sha", "abc1234"])
            chapter = (out / "chapter-01.html").read_text(encoding="utf-8")
            self.assertIn('id="ask-book" data-repo="OWNER/NAME" data-subject="chapter 01 One"', chapter)
            self.assertIn('class="button ask" href="https://github.com/OWNER/NAME/issues/new?title=Ask+Claude', chapter)
            self.assertIn('id="ask-book"', (out / "index.html").read_text(encoding="utf-8"))
            chunks = json.loads((out / "rag" / "chunks.json").read_text())
            self.assertEqual({c["file"] for c in chunks}, {"docs/textbook/01-one.md"})
            for name in ("index.json", "search.js", "box.js", "box.css"):
                self.assertTrue((out / "rag" / name).is_file(), name)


class TheMirror(unittest.TestCase):
    def test_the_browsers_mirror_scores_the_fixture_as_the_package_does(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed here; the runners have it")
        data = json.loads((ROOT / rag.FIXTURE).read_text(encoding="utf-8"))
        self.assertEqual(rag.fill_fixture(json.loads(json.dumps(data))), data, "run python3 tools/rag.py fixture")
        with tempfile.TemporaryDirectory() as tmp:
            mirror, check = Path(tmp) / "search.js", Path(tmp) / "check.js"
            mirror.write_text(rag.SEARCH_JS, encoding="utf-8")
            check.write_text(MIRROR_CHECK, encoding="utf-8")
            done = subprocess.run([node, str(check), str(mirror), str(ROOT / rag.FIXTURE)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stdout.strip(), "ok")


if __name__ == "__main__":
    unittest.main()
