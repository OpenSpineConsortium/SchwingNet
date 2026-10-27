"""The door's loader, tools/front_door_loader.html, the page published at the door's link, driven in
a browser against the stand-in of tests/door_stand_in.py: it reads tools/front_door.html from main
through the viewer's GitHub connector and runs it, so the door the viewer sees is main's, its deep
link and its theme kept, and a door merged later is the one the next open runs; where the door cannot
be read, the viewer is told why. The browser is Playwright's Chromium; where it is not installed, as
on CI, the tests skip.
"""

import shutil
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import door_stand_in as stand_in  # noqa: E402

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # the browser is optional; CI has none
    sync_playwright = None

WAIT = 10000
CONFIGS = {"loader": {"mode": "normal", "page": "loader"}, "absent": {"mode": "absent", "page": "loader"},
           "notConnected": {"mode": "notConnected", "page": "loader"}, "denied": {"mode": "denied", "page": "loader"},
           "rate": {"mode": "normal", "page": "loader", "rateLimited": 2}}
COMMITS = [{"sha": "abc1234" + "0" * 33, "html_url": "https://github.com/x/y/commit/abc1234", "author": None,
            "commit": {"message": "Open the door", "author": {"name": "Someone", "date": "2026-10-27T11:00:00Z"},
                       "committer": {"name": "Someone", "date": "2026-10-27T11:00:00Z"}}}]
FILES = {"README.md": "# The small repository\n\nSee [one](docs/one.md).\n",
         "docs/one.md": "# One\n\nA document.\n"}
MARK = "<title>SchwingNet Front Door</title>"


def door_as_main_holds_it(edition):
    """The repository's own door, with its title naming the edition, so a test sees which copy ran."""
    door = stand_in.DOOR.read_text(encoding="utf-8")
    assert door.startswith(MARK)
    return door.replace(MARK, f"<title>SchwingNet Front Door, {edition}</title>", 1)


@unittest.skipIf(sync_playwright is None, "Playwright is not installed here")
class LoaderInABrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.temp = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.main = cls.temp / "main"
        for rel, text in FILES.items():
            (cls.main / rel).parent.mkdir(parents=True, exist_ok=True)
            (cls.main / rel).write_text(text, encoding="utf-8")
        cls.set_door("first")
        board = cls.temp / "board"
        board.mkdir()
        (board / "STATE.md").write_text("# Board\n", encoding="utf-8")
        cls.repository = stand_in.Repository({"main": cls.main, "board": board}, COMMITS)
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

    @classmethod
    def set_door(cls, edition):
        (cls.main / "tools").mkdir(exist_ok=True)
        (cls.main / "tools" / "front_door.html").write_text(door_as_main_holds_it(edition), encoding="utf-8")

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1000, "height": 700})
        self.addCleanup(self.context.close)
        self.addCleanup(self.set_door, "first")
        self.errors = []

    def open(self, config="loader", hash_=""):
        page = self.context.new_page()
        page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.goto(stand_in.viewer_url(self.port, config, hash_))
        return page

    def frame(self, page):
        return page.frame_locator("#artifact")

    def artifact(self, page):
        return next(f for f in page.frames if "artifact.html" in f.url)

    def test_the_loader_runs_the_door_main_holds_and_the_door_reads_the_repository(self):
        page = self.open()
        frame = self.frame(page)
        expect(frame.locator("#content .doc h1")).to_have_text("The small repository", timeout=WAIT)
        expect(frame.locator("#head")).to_contain_text("main abc1234")
        self.assertEqual(self.artifact(page).title(), "SchwingNet Front Door, first")
        # The loader's own words and style are gone; the door's style is in force.
        self.assertEqual(frame.locator("#loader").count(), 0)
        self.assertEqual(frame.locator("#loader-style").count(), 0)
        self.assertEqual(frame.locator(".bar").evaluate("e => getComputedStyle(e).display"), "flex")
        calls = [c for c in self.artifact(page).evaluate("window.standInCalls") if c[0] == "callTool"]
        self.assertEqual(calls[0][1:], ["GitHub", "get_file_contents",
                                        {"owner": "OpenSpineConsortium", "repo": "SchwingNet",
                                         "path": "tools/front_door.html", "ref": "refs/heads/main"}])
        self.assertEqual(self.errors, [])

    def test_a_door_merged_later_is_the_one_the_next_open_runs(self):
        page = self.open()
        expect(self.frame(page).locator("#content .doc h1")).to_have_text("The small repository", timeout=WAIT)
        self.set_door("second")
        later = self.open()
        expect(self.frame(later).locator("#content .doc h1")).to_have_text("The small repository", timeout=WAIT)
        self.assertEqual(self.artifact(later).title(), "SchwingNet Front Door, second")

    def test_a_deep_link_and_the_theme_reach_the_door(self):
        page = self.open(hash_="docs~one.md")
        frame = self.frame(page)
        expect(frame.locator("#content .doc h1")).to_have_text("One", timeout=WAIT)
        frame.locator("#content .doc").wait_for()
        self.artifact(page).evaluate("document.documentElement.setAttribute('data-theme', 'dark')")
        bg = frame.locator("body").evaluate("e => getComputedStyle(e).backgroundColor")
        self.assertEqual(bg, "rgb(21, 24, 29)")

    def test_calls_refused_for_the_rate_are_made_again(self):
        page = self.open("rate")
        expect(self.frame(page).locator("#content .doc h1")).to_have_text("The small repository", timeout=WAIT)
        doors = [c for c in self.artifact(page).evaluate("window.standInCalls")
                 if c[0] == "callTool" and c[3].get("path") == "tools/front_door.html"]
        self.assertEqual(len(doors), 3, "refused twice for the rate, read the third time")

    def test_a_viewer_the_loader_cannot_serve_is_told_why(self):
        said = {"absent": "This view cannot reach your connectors.",
                "notConnected": "GitHub is not connected to your claude.ai account, so the door cannot be read.",
                "denied": "The door may not use your GitHub connector, so it cannot be read."}
        for config, words in said.items():
            with self.subTest(config=config):
                page = self.open(config)
                expect(self.frame(page).locator("#loader-text")).to_have_text(words, timeout=WAIT)
        page = self.open("notConnected")
        expect(self.frame(page).locator("#loader-more")).to_contain_text("https://api.githubcopilot.com/mcp/", timeout=WAIT)
        expect(self.frame(page).locator("#loader-again")).to_be_visible()

    def test_a_door_main_lacks_is_said_and_tried_again(self):
        door = self.main / "tools" / "front_door.html"
        aside = self.temp / "door-aside.html"
        shutil.move(door, aside)
        self.addCleanup(lambda: aside.exists() and shutil.move(aside, door))
        page = self.open()
        frame = self.frame(page)
        expect(frame.locator("#loader-text")).to_have_text("The door could not be read from the repository (tool_error).", timeout=WAIT)
        expect(frame.locator("#loader-more")).to_contain_text("404")
        shutil.move(aside, door)
        frame.locator("#loader-again").click()
        expect(frame.locator("#content .doc h1")).to_have_text("The small repository", timeout=WAIT)


if __name__ == "__main__":
    unittest.main()
