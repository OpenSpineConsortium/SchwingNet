"""The front door, tools/front_door.html, driven in a browser against the stand-in of
tests/door_stand_in.py over a small repository: the top folder with its README rendered and the
head of main named, a document opened by a relative link with its picture, code, emphasis, lists
and table, an SVG and a heading with an id of its own, an anchor in the same document, Back, a deep
link, an exported artifact run sealed with its stylesheet, script, image and fetch of a file beside
it, its reads by message answered at its own branch alone, its link outside the repository shown and
not opened, and its link opening a document at its anchor, the board branch, the newest commits, a search, Ask reaching sample with a tool that reads
through the connector, a picture and a binary file, a path the repository lacks, the viewer with no
connector, no GitHub, or a declined grant told what to do, calls refused for the rate made again,
and the folder pane on a phone. The browser is Playwright's Chromium; where it is not installed, as
on CI, the tests skip.
"""

import re
import struct
import sys
import tempfile
import time
import unittest
import zlib
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import door_stand_in as stand_in  # noqa: E402

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # the browser is optional; CI has none
    sync_playwright = None

WAIT = 10000
BLOB, PNG_INLINE = re.compile(r"^blob:"), re.compile(r"^data:image/png;base64,")
CONFIGS = {"normal": {"mode": "normal"}, "absent": {"mode": "absent"}, "notConnected": {"mode": "notConnected"},
           "denied": {"mode": "denied"}, "rate": {"mode": "normal", "rateLimited": 3}}
GITHUB = f"https://github.com/{stand_in.OWNER}/{stand_in.REPO}"
COMMITS = [
    {"sha": "abc1234" + "0" * 33, "html_url": f"{GITHUB}/commit/abc1234", "author": {"login": "someone"},
     "commit": {"message": "Open the door\n\nThe rest of the message.", "author": {"name": "Someone", "date": "2026-10-26T00:50:00Z"},
                "committer": {"name": "Someone", "date": "2026-10-26T00:50:00Z"}}},
    {"sha": "def5678" + "0" * 33, "html_url": f"{GITHUB}/commit/def5678", "author": None,
     "commit": {"message": "Stage the book", "author": {"name": "Else", "date": "2026-10-25T23:39:00Z"},
                "committer": {"name": "Else", "date": "2026-10-25T23:39:00Z"}}},
]


def png():
    """A PNG of one pixel."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00")) + chunk(b"IEND", b""))


LONG = "\n\n".join(f"Paragraph {n} of the long chapter." for n in range(120))
FILES = {
    "README.md": ("# The small repository\n\nSee [one](docs/one.md), the [thing](artifacts/thing/index.html), the "
                  "[picture](docs/figures/dot.png), the [blob](data/blob.bin), [away](https://example.com/), "
                  "[missing](docs/none.md) and a [script](javascript:alert(1)) link.\n\n"
                  "| Column | Value |\n|---|---:|\n| rows | 2 |\n"),
    "docs/one.md": ("# One\n\nA paragraph with `code`, **bold** and a [back link](../README.md); [down](#far), "
                    f"an [odd]({GITHUB}/blob/main/%E0%A4%A) address.\n\n"
                    "![a dot](figures/dot.png)\n\n![mark](figures/mark.svg)\n\n![see https://example.com/alt](figures/dot.png)\n\n"
                    "## Files\n\n- first\n- second\n  - nested\n\n```python\nprint(1)\n```\n\n"
                    + LONG + "\n\n## Far\n\nFar text.\n"),
    "docs/figures/mark.svg": '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>\n',
    "artifacts/thing/index.html": ("<!doctype html><html><head><title>The thing itself</title>"
                                   "<link rel=\"stylesheet\" href=\"style.css\"></head><body><p id=\"t\">not run</p>"
                                   "<img id=\"pic\" src=\"fig.png\" alt=\"fig\" width=\"10\" height=\"10\">"
                                   "<a id=\"to-one\" href=\"../../docs/one.md#far\">One, far</a>"
                                   "<a id=\"out\" href=\"https://example.com/out\">out</a>"
                                   "<p id=\"r1\"></p><p id=\"r2\"></p>"
                                   "<script src=\"app.js\" defer></script></body></html>\n"),
    "artifacts/thing/style.css": "#t { color: rgb(4, 5, 6); }\n",
    "artifacts/thing/app.js": ('fetch("data.json").then(function (r) { return r.json(); }).then(function (j) {\n'
                               '  document.getElementById("t").textContent = "thing ran " + j.n;\n'
                               '}, function () { document.getElementById("t").textContent = "fetch failed"; });\n'
                               'addEventListener("message", function (e) {\n'
                               '  var d = e.data;\n'
                               '  if (d && d.type === "schwingnet.read.result")\n'
                               '    document.getElementById(d.id).textContent = d.ok ? "read " + d.text.trim() : "refused " + d.error;\n'
                               '});\n'
                               f'var repo = "{stand_in.OWNER}/{stand_in.REPO}";\n'
                               'parent.postMessage({type: "schwingnet.read", id: "r1", repo: repo, ref: "main", path: "artifacts/thing/data.json"}, "*");\n'
                               'parent.postMessage({type: "schwingnet.read", id: "r2", repo: repo, ref: "refs/heads/board", path: "STATE.md"}, "*");\n'),
    "artifacts/thing/data.json": '{"n": 7}\n',
}
BYTES = {"docs/figures/dot.png": png(), "artifacts/thing/fig.png": png(), "data/blob.bin": bytes(range(12))}
BOARD = {"STATE.md": "# Board\n\nThe board says hello.\n"}


def small_repository(folder, files, data=None):
    for rel, text in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_text(text, encoding="utf-8")
    for rel, blob in (data or {}).items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(blob)
    return folder


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here")
class DoorInABrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.temp = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        main = small_repository(cls.temp / "main", FILES, BYTES)
        board = small_repository(cls.temp / "board", BOARD)
        cls.repository = stand_in.Repository({"main": main, "board": board}, COMMITS)
        cls.playwright = cls.stack.enter_context(sync_playwright())
        cls.browser = stand_in.chromium(cls.playwright)
        if cls.browser is None:
            cls.stack.close()
            raise unittest.SkipTest("no Chromium Playwright can launch here")
        cls.stack.callback(cls.browser.close)
        cls.port = cls.stack.enter_context(stand_in.serving(cls.repository, CONFIGS))

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1000, "height": 700})
        self.addCleanup(self.context.close)
        self.errors = []

    def open(self, config="normal", hash_=""):
        page = self.context.new_page()
        page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(stand_in.viewer_url(self.port, config, hash_))
        return page

    def door(self, page):
        return page.frame_locator("#artifact")

    def sealed(self, page):
        return self.door(page).frame_locator("#view iframe")

    def note(self, page):
        return self.door(page).locator("#note-text")

    def heading(self, page):
        return self.door(page).locator("#content .doc h1")

    def calls(self, page):
        frame = next(f for f in page.frames if "artifact.html" in f.url)
        return frame.evaluate("window.standInCalls")

    def front(self, config="normal"):
        page = self.open(config)
        expect(self.heading(page)).to_have_text("The small repository", timeout=WAIT)
        return page

    def test_the_top_folder_opens_with_its_readme_and_the_head_of_main(self):
        page = self.front()
        door = self.door(page)
        expect(door.locator("#head")).to_contain_text("main abc1234, 2026-10-26 00:50 UTC: Open the door")
        expect(door.locator("#note")).to_be_hidden()
        expect(door.locator("#back")).to_be_disabled()
        names = door.locator("#content ul.entries li button").all_text_contents()
        self.assertEqual(names, ["artifacts", "data", "docs", "README.md"], "folders first, then files, by name")
        expect(door.locator("#content .doc table td").first).to_have_text("rows")
        # A link of a scheme the page would run itself is shown as its words, not as a link.
        self.assertEqual(door.locator("#content .doc a[href^='javascript']").count(), 0)
        expect(door.locator("#content .doc p").first).to_contain_text("and a script link")
        expect(door.locator("#content .doc a", has_text="away")).to_have_attribute("target", "_blank")
        expect(door.locator("#side h2").first).to_have_text("Doors")
        expect(door.locator("#side button", has_text="Board")).to_be_visible()
        reads = [c for c in self.calls(page) if c[0] == "callTool"]
        self.assertEqual(sorted(c[2] for c in reads[:3]), ["get_file_contents", "get_file_contents", "list_commits"],
                         "the head of main, the top folder and its README, read together")
        self.assertEqual(self.errors, [])

    def test_a_document_opens_by_its_link_with_its_picture_and_back_returns(self):
        page = self.front()
        door = self.door(page)
        door.locator(".doc a", has_text="one").click()
        expect(self.heading(page)).to_have_text("One", timeout=WAIT)
        expect(door.locator("#where")).to_contain_text("docs / one.md")
        doc = door.locator("#content .doc")
        dot = doc.locator("img[alt='a dot']")
        expect(dot).to_have_attribute("src", BLOB, timeout=WAIT)
        self.assertEqual(dot.evaluate("i => i.complete && i.naturalWidth"), 1)
        # An SVG is shown from a data address, since a blob of it would run its scripts on this origin.
        expect(doc.locator("img[alt='mark']")).to_have_attribute("src", re.compile(r"^data:image/svg\+xml"), timeout=WAIT)
        # An address inside an image's words is words, not the image's link.
        expect(doc.locator("img[alt='see https://example.com/alt']")).to_have_attribute("src", BLOB, timeout=WAIT)
        # A heading carries an id of its own, prefixed doc-, so Files never stands in for the page's button.
        expect(doc.locator("h2#doc-files")).to_have_text("Files")
        self.assertEqual(door.locator("#files").evaluate("e => e.tagName"), "BUTTON")
        # A GitHub address that is no valid encoding still renders as a link.
        expect(doc.locator("a", has_text="odd")).to_be_visible()
        expect(doc.locator("p code").first).to_have_text("code")
        expect(doc.locator("strong")).to_have_text("bold")
        expect(doc.locator("ul > li > ul > li")).to_have_text("nested")
        expect(doc.locator("pre code")).to_have_text("print(1)")
        expect(door.locator("#back")).to_be_enabled()
        door.locator("#back").click()
        expect(self.heading(page)).to_have_text("The small repository", timeout=WAIT)
        expect(door.locator("#back")).to_be_disabled()
        self.assertEqual(self.errors, [])

    def test_a_deep_link_opens_a_document_and_an_anchor_scrolls_within_it(self):
        page = self.open(hash_="docs~one.md")
        expect(self.heading(page)).to_have_text("One", timeout=WAIT)
        door = self.door(page)
        door.locator(".doc a", has_text="down").click()
        self.wait_for(lambda: door.locator("#view").evaluate("v => v.scrollTop") > 1000, "the document scrolled to #far")
        door.locator(".doc a", has_text="back link").click()
        expect(self.heading(page)).to_have_text("The small repository", timeout=WAIT)

    def test_an_exported_artifact_runs_sealed_with_its_files_and_its_link_opens_a_document(self):
        page = self.front()
        door = self.door(page)
        door.locator(".doc a", has_text="thing").click()
        expect(door.locator("#view iframe")).to_have_attribute("sandbox", "allow-scripts", timeout=WAIT)
        expect(door.locator("#where")).to_contain_text("artifacts / thing / index.html")
        thing = self.sealed(page)
        expect(thing.locator("#t")).to_have_text("thing ran 7", timeout=WAIT)
        expect(thing.locator("#t")).to_have_css("color", "rgb(4, 5, 6)")
        expect(thing.locator("#pic")).to_have_attribute("src", PNG_INLINE)
        # A read the page asks for by message is answered at its own branch and refused at another.
        expect(thing.locator("#r1")).to_have_text('read {"n": 7}', timeout=WAIT)
        expect(thing.locator("#r2")).to_have_text("refused ref not allowed", timeout=WAIT)
        # A link outside the repository opens no page: the door shows it for the viewer to open.
        thing.locator("#out").click()
        expect(self.note(page)).to_have_text("The page asks to open a link outside the repository.", timeout=WAIT)
        expect(door.locator("#note-more a")).to_have_attribute("href", "https://example.com/out")
        self.assertEqual(len(self.context.pages), 1, "the sealed frame opened nothing itself")
        door.get_by_role("button", name="Close").click()
        expect(door.locator("#note")).to_be_hidden()
        thing.locator("#to-one").click()
        expect(self.heading(page)).to_have_text("One", timeout=WAIT)
        self.wait_for(lambda: door.locator("#view").evaluate("v => v.scrollTop") > 1000, "the document opened at #far")
        self.assertEqual(self.errors, [])

    def test_the_board_door_opens_the_board_branch(self):
        page = self.front()
        door = self.door(page)
        door.locator("#side button", has_text="Board").click()
        expect(self.heading(page)).to_have_text("Board", timeout=WAIT)
        expect(door.locator("#where")).to_contain_text("board")
        refs = [c[3].get("ref") for c in self.calls(page) if c[0] == "callTool" and c[2] == "get_file_contents"]
        self.assertIn("refs/heads/board", refs)

    def test_changes_search_and_ask_read_through_the_connector(self):
        page = self.front()
        door = self.door(page)
        door.locator("#changes").click()
        expect(door.locator("ul.commits li")).to_have_count(2, timeout=WAIT)
        expect(door.locator("ul.commits li").first).to_contain_text("abc1234")
        expect(door.locator("ul.commits li").first).to_contain_text("Open the door")
        expect(door.locator("ul.commits li").first).to_contain_text("someone")
        door.locator("#q").fill("nested")
        door.locator("#find button").click()
        expect(door.locator("ul.hits li")).to_have_count(1, timeout=WAIT)
        door.locator("ul.hits li button").click()
        expect(self.heading(page)).to_have_text("One", timeout=WAIT)
        door.locator("#ask-open").click()
        door.locator("#question").fill("What is here?")
        door.locator("#ask-go").click()
        expect(door.locator("#answer")).to_have_text(
            'A stand-in answer. The tool said ["artifacts/","data/","docs/","README.md"].', timeout=WAIT)
        self.assertIn("sample", [c[0] for c in self.calls(page)])
        self.assertEqual(self.errors, [])

    def test_a_picture_shows_and_a_binary_file_is_named_with_its_link(self):
        page = self.front()
        door = self.door(page)
        door.locator(".doc a", has_text="picture").click()
        expect(door.locator("#content img.picture")).to_have_attribute("src", BLOB, timeout=WAIT)
        door.locator("#back").click()
        expect(self.heading(page)).to_have_text("The small repository", timeout=WAIT)
        door.locator(".doc a", has_text="blob").click()
        expect(door.locator("#content p").first).to_have_text("blob.bin is a binary file of 12 B.", timeout=WAIT)
        expect(door.locator("#content a", has_text="Open it on GitHub")).to_have_attribute("href", f"{GITHUB}/blob/main/data/blob.bin")

    def test_a_path_the_repository_lacks_says_so_and_closes(self):
        page = self.front()
        door = self.door(page)
        door.locator(".doc a", has_text="missing").click()
        expect(self.note(page)).to_have_text("That is not in the repository.", timeout=WAIT)
        door.get_by_role("button", name="Close").click()
        expect(door.locator("#note")).to_be_hidden()
        expect(self.heading(page)).to_have_text("The small repository")

    def test_what_a_viewer_the_door_cannot_serve_is_told(self):
        said = {"absent": "This view cannot reach your connectors.",
                "notConnected": "GitHub is not connected to your claude.ai account, so the door has nothing to show.",
                "denied": "The door may not use your GitHub connector, so it cannot read the repository."}
        for config, words in said.items():
            with self.subTest(config=config):
                page = self.open(config)
                expect(self.note(page)).to_have_text(words, timeout=WAIT)
        page = self.open("notConnected")
        expect(self.note(page)).to_have_text(said["notConnected"], timeout=WAIT)
        more = self.door(page).locator("#note-more")
        expect(more).to_contain_text("Add custom connector")
        expect(more).to_contain_text("https://api.githubcopilot.com/mcp/")
        expect(more).to_contain_text("https://claude.ai/api/mcp/auth_callback")
        page = self.open("denied")
        expect(self.note(page)).to_have_text(said["denied"], timeout=WAIT)
        self.door(page).get_by_role("button", name="Open permissions").click()
        self.wait_for(lambda: ["manage"] in self.calls(page), "the permissions panel was asked for")

    def test_calls_refused_for_the_rate_are_made_again(self):
        page = self.front("rate")
        tools = [c[2] for c in self.calls(page) if c[0] == "callTool"]
        # The stand-in refuses the first three calls for the rate, whichever tools they are; each is
        # made again after the wait it names, so every tool asked at the start is asked at least twice
        # and the repository still opens.
        self.assertGreaterEqual(tools.count("list_commits"), 2, "the head of main was asked again")
        tops = [c for c in self.calls(page) if c[0] == "callTool" and c[2] == "get_file_contents" and c[3].get("path") in ("", "/")]
        self.assertGreaterEqual(len(tops), 2, "the top folder was asked again")
        self.assertEqual(self.errors, [])

    def test_the_folder_pane_opens_over_the_view_on_a_phone(self):
        self.context.close()
        self.context = self.browser.new_context(viewport={"width": 400, "height": 700})
        page = self.front()
        door = self.door(page)
        expect(door.locator("#files")).to_be_visible()
        door.locator("#files").click()
        expect(door.locator("#side")).to_have_class(re.compile(r"\bopen\b"))
        door.locator("#side button", has_text="docs").click()
        expect(door.locator("#where")).to_contain_text("docs", timeout=WAIT)
        expect(door.locator("#side")).not_to_have_class(re.compile(r"\bopen\b"))
        self.assertLessEqual(page.evaluate("() => document.documentElement.scrollWidth"), 400)

    def wait_for(self, check, what, seconds=10):
        end = time.time() + seconds
        while time.time() < end:
            if check():
                return
            time.sleep(0.1)
        self.fail(f"timed out waiting until {what}")


if __name__ == "__main__":
    unittest.main()
