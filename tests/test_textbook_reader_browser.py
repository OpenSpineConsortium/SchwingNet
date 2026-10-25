"""The textbook's reader, tools/textbook_reader.html (issue #294), driven in a browser against the
stand-in of tests/reader_stand_in.py, over a small book packed and placed by tools/textbook_reader.py
as a thread of the project places the real one: the front page found in the project's files and
shown with its edition, Ask Claude reaching the runtime's sample through the reader, a chapter by
its link and Back, its stylesheet in place and its fetch of the book's search index answered from
the pack, its images filled as they come near the view, a figure and an exported artifact shown
sealed, with their files inline and their links opening pages of the book, a deep link, the
viewer's theme, a page the book lacks, and what the reader says to a viewer it cannot serve: no
files capability, access declined, no access, no copy, a copy of another format, a copy removed
while it was read; calls refused for the rate made again, paths spelled with slashes passed back as
given, and a copy found below another root. The browser is Playwright's Chromium; where it is not
installed, as on CI, the tests skip.
"""

import json
import re
import struct
import sys
import tempfile
import time
import unittest
import zlib
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reader_stand_in as stand_in  # noqa: E402
import textbook_reader as tr  # noqa: E402

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # the browser is optional; CI has none
    sync_playwright = None

SHA = "abcdef1234567890abcdef1234567890abcdef12"
BUILT = "2026-10-25T04:19:10+00:00"
WAIT = 10000
BLOB, PNG_INLINE = re.compile(r"^blob:"), re.compile(r"^data:image/png;base64,")
CONFIGS = {"normal": {"mode": "normal"}, "absent": {"mode": "absent"}, "denied": {"mode": "denied"},
           "outsider": {"mode": "outsider"}, "rate": {"mode": "normal", "rateLimited": 3}}


def png():
    """A PNG of one pixel."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


ASK = """(function () {
  var root = document.documentElement, out = document.getElementById("answer");
  out.setAttribute("data-page", root.getAttribute("data-page") || "");
  out.setAttribute("data-hash", root.getAttribute("data-hash") || "");
  if (!window.claude || typeof window.claude.use !== "function") { out.textContent = "no runtime"; return; }
  window.claude.use("sample").then(function (fn) { return fn ? fn("What is on this page?") : {text: "no sample"}; })
    .then(function (r) { out.textContent = r.text; });
})();
"""

SEARCH = """fetch("rag/index.json").then(function (r) { return r.json(); }).then(function (j) {
  document.getElementById("found").textContent = "found " + j.words.join(" ");
}, function () { document.getElementById("found").textContent = "fetch failed"; });
"""

PAGES = {
    # The front page as the edition writes it: the tool's page proper, with no document skeleton.
    "index.html": """<title>The SchwingNet textbook</title>
<style>body{font:16px serif}.dot{width:4px;height:4px;background:url(figures/01/dot.png)}</style>
<script>document.documentElement.setAttribute("data-repo", "OpenSpineConsortium/SchwingNet");</script>
<h1 id="front">The SchwingNet textbook</h1>
<ul><li><a id="to-one" href="chapter-01.html">01 One</a></li><li><a id="to-thing" href="artifact-thing.html#part">Thing</a></li>
<li><a id="to-missing" href="chapter-99.html">Missing</a></li><li><a id="away" href="https://example.com/">Away</a></li></ul>
<p id="answer"></p><div class="dot" id="dot"></div>
<script src="ask.js" defer></script>
""",
    "chapter-01.html": """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>01 One - The SchwingNet textbook</title><link rel="stylesheet" href="rag/box.css"></head><body><main>
<h1 id="top">01 One</h1><p><a id="home-link" href="index.html">Front page</a> <a id="down" href="#far">Down</a></p>
<p id="found"></p><p id="answer"></p>
<img id="pic" src="figures/01/dot.png" alt="a dot" width="40" height="40">
<div style="height:1600px"></div>
<iframe id="fig" src="figures/01/plot.html" sandbox="allow-scripts" title="plot" style="width:300px;height:120px"></iframe>
<div style="height:4000px"></div>
<img id="late" src="figures/01/late.png" alt="late" width="40" height="40">
<p id="far">Far</p><div style="height:900px"></div>
</main><script src="ask.js" defer></script><script src="rag/search.js" defer></script></body></html>
""",
    "artifact-thing.html": """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Thing - The SchwingNet textbook</title></head><body><main>
<h1 id="thing">Thing</h1><p id="answer"></p><div style="height:1600px"></div><p id="part">Part</p>
<a id="own" href="artifacts/thing/index.html">Its own page</a>
<iframe id="embed" src="artifacts/thing/index.html" sandbox="allow-scripts allow-popups" title="thing"
 style="width:400px;height:200px"></iframe><div style="height:900px"></div>
</main><script src="ask.js" defer></script></body></html>
""",
    "ask.js": ASK,
    "rag/box.css": "#found { color: rgb(1, 2, 3); }\n",
    "rag/index.json": json.dumps({"words": ["spine", "level"]}),
    "rag/search.js": SEARCH,
    "figures/01/plot.html": """<!doctype html><html><head><link rel="stylesheet" href="plot.css"></head><body>
<p id="drawn">not drawn</p><img id="fdot" src="dot.png" alt="dot" width="10" height="10">
<a id="go" href="../../chapter-01.html#far">Far in the chapter</a><script src="plot.js"></script></body></html>
""",
    "figures/01/plot.css": "#drawn { color: rgb(7, 8, 9); }\n",
    "figures/01/plot.js": """var reach;
try { reach = String(window.parent.document.title); } catch (e) { reach = "sealed"; }
document.getElementById("drawn").textContent = "drawn " + reach;
""",
    "artifacts/thing/index.html": """<!doctype html><html><head><title>The thing itself</title>
<link rel="stylesheet" href="style.css"></head><body><p id="t">not run</p>
<a id="back-to-one" href="../../chapter-01.html">Chapter one</a><script src="app.js" defer></script></body></html>
""",
    "artifacts/thing/style.css": "#t { color: rgb(4, 5, 6); }\n",
    "artifacts/thing/app.js": 'document.getElementById("t").textContent = "thing ran";\n',
    "batches.json": "{}",
}
IMAGES = {"figures/01/dot.png": png(), "figures/01/late.png": png()}


def small_book(folder):
    for rel, text in PAGES.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8")
    for rel, data in IMAGES.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(data)
    return folder


def placed(project, pack_dir, below=""):
    """The packed small book placed in a project's files as the stage command places a book."""
    index = json.loads((pack_dir / "book.json").read_text(encoding="utf-8"))
    folder = project / below / tr.FOLDER if below else project / tr.FOLDER
    tr.place(folder, pack_dir, index, "2026-10-25T05:00:00Z", wait=0)
    return folder


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here")
class ReaderInABrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.temp = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.pack = cls.temp / "pack"
        tr.pack(small_book(cls.temp / "edition"), cls.pack, tr.REPO_NAME, SHA, BUILT)
        cls.project = cls.temp / "project"
        (cls.project / "uploads").mkdir(parents=True)
        placed(cls.project, cls.pack)
        cls.playwright = cls.stack.enter_context(sync_playwright())
        cls.browser = stand_in.chromium(cls.playwright)
        if cls.browser is None:
            cls.stack.close()
            raise unittest.SkipTest("no Chromium Playwright can launch here")
        cls.stack.callback(cls.browser.close)
        cls.port = cls.stack.enter_context(stand_in.serving(stand_in.Project(cls.project), CONFIGS))

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1000, "height": 700})
        self.addCleanup(self.context.close)
        self.errors = []

    def open(self, config="normal", hash_="", port=None):
        page = self.context.new_page()
        page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(stand_in.viewer_url(port or self.port, config, hash_))
        return page

    def reader(self, page):
        return page.frame_locator("#artifact")

    def shown(self, page):
        return self.reader(page).frame_locator("#view iframe").last

    def note(self, page):
        return self.reader(page).locator("#note-text")

    def calls(self, page):
        frame = next(f for f in page.frames if "artifact.html" in f.url)
        return frame.evaluate("window.standInCalls")

    def front(self, config="normal", port=None):
        return self.opened("#front", config, port=port)

    def opened(self, selector, config="normal", hash_="", port=None):
        """The viewer opened, once the page it opens on shows the element named."""
        page = self.open(config, hash_, port)
        expect(self.shown(page).locator(selector)).to_be_attached(timeout=WAIT)
        return page

    def test_the_front_page_opens_from_the_projects_files_with_its_edition(self):
        page = self.front()
        reader = self.reader(page)
        expect(reader.locator("#edition")).to_have_text("Edition abcdef1, 2026-10-25 04:19 UTC")
        expect(reader.locator("#note")).to_be_hidden()
        expect(reader.locator("#back")).to_be_disabled()
        expect(reader.locator("#where")).to_have_text("The SchwingNet textbook")
        reads = [c for c in self.calls(page) if c[0] == "read"]
        self.assertEqual([c[1] for c in reads[:2]], ["textbook/CURRENT.json", f"textbook/book-{SHA[:12]}.json"])
        self.assertLessEqual(len(reads), 5, "a page and what it needs come in few reads")
        self.assertEqual(self.errors, [])

    def test_ask_claude_reaches_sample_through_the_reader(self):
        page = self.front()
        answer = self.shown(page).locator("#answer")
        expect(answer).to_have_text("A stand-in answer.", timeout=WAIT)
        expect(answer).to_have_attribute("data-page", "index.html")
        self.assertIn("sample", [c[0] for c in self.calls(page)])

    def test_a_chapter_opens_by_its_link_and_back_returns(self):
        page = self.front()
        self.shown(page).locator("#to-one").click()
        chapter = self.shown(page)
        expect(chapter.locator("#top")).to_be_visible(timeout=WAIT)
        expect(self.reader(page).locator("#where")).to_have_text("01 One")
        expect(chapter.locator("#found")).to_have_text("found spine level", timeout=WAIT)
        expect(chapter.locator("#found")).to_have_css("color", "rgb(1, 2, 3)")
        expect(chapter.locator("#answer")).to_have_attribute("data-page", "chapter-01.html")
        expect(self.reader(page).locator("#back")).to_be_enabled()
        self.reader(page).locator("#back").click()
        expect(self.shown(page).locator("#front")).to_be_visible(timeout=WAIT)
        expect(self.reader(page).locator("#back")).to_be_disabled()
        self.assertEqual(self.errors, [])

    def test_images_fill_near_the_view_and_a_figure_is_sealed(self):
        page = self.opened("#top", hash_="chapter-01")
        chapter = self.shown(page)
        pic = chapter.locator("#pic")
        expect(pic).to_have_attribute("src", BLOB, timeout=WAIT)
        self.assertEqual(pic.evaluate("i => i.complete && i.naturalWidth"), 1)
        expect(chapter.locator("#late")).to_have_attribute("data-reader-src", "figures/01/late.png")
        figure = chapter.frame_locator("#fig")
        expect(figure.locator("#drawn")).to_have_text("drawn sealed", timeout=WAIT)
        expect(figure.locator("#drawn")).to_have_css("color", "rgb(7, 8, 9)")
        expect(figure.locator("#fdot")).to_have_attribute("src", PNG_INLINE)
        expect(chapter.locator("#fig")).to_have_attribute("sandbox", "allow-scripts")
        chapter.locator("#down").click()
        expect(chapter.locator("#late")).to_have_attribute("src", BLOB, timeout=WAIT)
        self.assertEqual(self.errors, [])

    def test_a_link_in_a_figure_opens_its_place_in_the_book(self):
        page = self.opened("#top", hash_="chapter-01")
        chapter = self.shown(page)
        figure = chapter.frame_locator("#fig")
        expect(figure.locator("#drawn")).to_have_text("drawn sealed", timeout=WAIT)
        figure.locator("#go").click()
        self.wait_for(lambda: chapter.locator("body").evaluate("() => scrollY") > 4000, "the chapter scrolled to #far")

    def test_an_exported_artifact_runs_sealed_and_its_links_open_pages(self):
        page = self.front()
        self.shown(page).locator("#to-thing").click()
        thing = self.shown(page)
        expect(thing.locator("#thing")).to_be_attached(timeout=WAIT)
        expect(thing.locator("#answer")).to_have_attribute("data-hash", "part")
        self.wait_for(lambda: thing.locator("body").evaluate("() => scrollY") > 1000, "the page scrolled to #part")
        embed = thing.frame_locator("#embed")
        expect(embed.locator("#t")).to_have_text("thing ran", timeout=WAIT)
        expect(embed.locator("#t")).to_have_css("color", "rgb(4, 5, 6)")
        embed.locator("#back-to-one").click()
        expect(self.shown(page).locator("#top")).to_be_visible(timeout=WAIT)
        self.assertEqual(self.errors, [])

    def test_an_artifacts_own_page_opens_sealed_and_its_links_too(self):
        page = self.opened("#thing", hash_="artifact-thing")
        self.shown(page).locator("#own").click()
        reader = self.reader(page)
        expect(reader.locator("#where")).to_have_text("The thing itself", timeout=WAIT)
        expect(reader.locator("#view iframe").last).to_have_attribute("sandbox", "allow-scripts allow-popups")
        own = self.shown(page)
        expect(own.locator("#t")).to_have_text("thing ran", timeout=WAIT)
        own.locator("#back-to-one").click()
        expect(self.shown(page).locator("#top")).to_be_visible(timeout=WAIT)
        self.assertEqual(self.errors, [])

    def test_the_viewers_theme_reaches_the_page(self):
        page = self.front()
        root = next(f for f in page.frames if "artifact.html" in f.url)
        root.evaluate("() => document.documentElement.setAttribute('data-theme', 'dark')")
        expect(self.shown(page).locator("html")).to_have_attribute("data-theme", "dark", timeout=WAIT)
        root.evaluate("() => document.documentElement.removeAttribute('data-theme')")
        expect(self.shown(page).locator("html")).not_to_have_attribute("data-theme", "dark", timeout=WAIT)

    def test_a_page_the_book_lacks_says_so_and_closes(self):
        page = self.front()
        self.shown(page).locator("#to-missing").click()
        expect(self.note(page)).to_have_text("That page is not in this copy of the book.", timeout=WAIT)
        self.reader(page).get_by_role("button", name="Close").click()
        expect(self.reader(page).locator("#note")).to_be_hidden()
        expect(self.shown(page).locator("#front")).to_be_visible()

    def test_what_a_viewer_the_reader_cannot_serve_is_told(self):
        said = {"absent": "This view cannot read the project's files.",
                "denied": "The reader may not read the project's files, so it cannot show the book.",
                "outsider": "No copy of the book was found in the project's files."}
        for config, words in said.items():
            with self.subTest(config=config):
                page = self.open(config)
                expect(self.note(page)).to_have_text(words, timeout=WAIT)
        reader = self.reader(page)
        expect(reader.locator("#note-code")).to_have_text("python3 tools/textbook_reader.py stage")
        page = self.open("denied")
        expect(self.note(page)).to_have_text(said["denied"], timeout=WAIT)
        self.reader(page).get_by_role("button", name="Open permissions").click()
        self.wait_for(lambda: ["manage"] in self.calls(page), "the permissions panel was asked for")

    def test_calls_refused_for_the_rate_are_made_again(self):
        page = self.front("rate")
        refused = self.calls(page)[:3]
        self.assertEqual([c[0] for c in refused], ["list", "list", "list"])

    def test_a_copy_removed_while_it_is_read_says_the_book_changed(self):
        page = self.front()
        data = self.project / tr.FOLDER / f"book-{SHA[:12]}.bin"
        aside = data.with_suffix(".aside")
        data.rename(aside)
        self.addCleanup(aside.rename, data)
        self.shown(page).locator("#to-one").click()
        expect(self.note(page)).to_have_text("The copy of the book changed while you were reading.", timeout=WAIT)

    def test_copies_the_reader_cannot_find_or_read_are_named(self):
        empty, other = self.temp / "empty", self.temp / "other"
        (empty / "notes").mkdir(parents=True)
        folder = placed(other, self.pack)
        pointer = json.loads((folder / tr.POINTER).read_text(encoding="utf-8"))
        (folder / tr.POINTER).write_text(json.dumps(dict(pointer, format="textbook-reader/0")), encoding="utf-8")
        cases = [(stand_in.Project(empty), "No copy of the book was found in the project's files."),
                 (stand_in.Project(other), "The copy of the book in the project's files is not one this reader reads.")]
        for project, words in cases:
            with self.subTest(words=words), stand_in.serving(project, CONFIGS) as port:
                page = self.open(port=port)
                expect(self.note(page)).to_have_text(words, timeout=WAIT)

    def test_paths_with_slashes_and_a_book_below_another_root_are_read(self):
        nested = self.temp / "nested"
        placed(nested, self.pack, below="project-files")
        for project in (stand_in.Project(self.project, slashes=True), stand_in.Project(nested, page_size=2)):
            with self.subTest(slashes=project.slashes), stand_in.serving(project, CONFIGS) as port:
                page = self.front(port=port)
                self.shown(page).locator("#to-one").click()
                expect(self.shown(page).locator("#found")).to_have_text("found spine level", timeout=WAIT)

    def wait_for(self, check, what, seconds=10):
        end = time.time() + seconds
        while time.time() < end:
            if check():
                return
            time.sleep(0.1)
        self.fail(f"timed out waiting until {what}")


if __name__ == "__main__":
    unittest.main()
