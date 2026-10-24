"""tools/textbook_artifact.py turns the site tools/textbook_site.py wrote into the files of one
claude.ai artifact (issue #236): the front page as the Artifact tool's page proper, with no
document skeleton and its title and style first; every other page whole; no figure record among
the files, "The record" pointing at GitHub at the built commit, the data a figure is drawn from
kept; the edition line dated by the commit and not the clock, so one commit builds the same
bytes twice; the theme overrides, the Ask Claude box and its script on every page and a button
on every figure beside the site's own; the exported artifact pages copied with their trees; and
the files grouped under the tool's limits with the page in no batch."""

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import textbook_artifact  # noqa: E402
import textbook_site  # noqa: E402
from test_textbook_site import small_book, write  # noqa: E402

REPO = "OWNER/NAME"
SHA = "abc1234def5678"
BUILT = "2026-10-24T14:42:00-04:00"


def hashes(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(folder).rglob("*")) if p.is_file()}


class AnEdition(unittest.TestCase):
    """The small book of tests/test_textbook_site.py, built as a site and then as an edition; a
    data file is put beside one of its figures, as chapter 35's corpora are."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name) / "repo"
        small_book(root)
        write(root / "docs" / "textbook" / "figures" / "01" / "corpora.json", '{"rows": []}')
        cls.site = Path(cls.tmp.name) / "site"
        textbook_site.main([str(cls.site), "--root", str(root), "--repo", REPO, "--sha", SHA])
        cls.out = Path(cls.tmp.name) / "out"
        cls.summary = textbook_artifact.build(cls.site, cls.out, REPO, SHA, BUILT)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_the_front_page_is_the_tools_page_proper(self):
        page = self.read("index.html")
        self.assertTrue(page.startswith("<title>SchwingNet Textbook</title>\n<style>"), page[:80])
        for tag in ("<!doctype", "<html", "<head>", "</head>", "<body>", "</body>", "</html>"):
            self.assertNotIn(tag, page.lower(), tag)
        self.assertIn('<script>document.documentElement.setAttribute("data-repo", "OWNER/NAME");</script>', page)
        self.assertIn('href="chapter-01.html"', page)
        self.assertIn('<aside id="ask" hidden', page)
        self.assertIn('<script src="ask.js" defer></script>', page)

    def test_the_edition_line_is_dated_by_the_commit_on_the_front_page_alone(self):
        page = self.read("index.html")
        self.assertIn('<h1>The SchwingNet textbook</h1><p class="edition">This edition was built from '
                      '<a href="https://github.com/OWNER/NAME/commit/abc1234def5678">abc1234</a> on 2026-10-24 18:42 UTC;',
                      page)
        self.assertEqual(page.count('class="edition"'), 1)
        self.assertNotIn('class="edition"', self.read("chapter-01.html"))

    def test_every_other_page_keeps_its_whole_document_with_the_box_and_the_theme(self):
        for name in ("chapter-01.html", "artifact-second.html", "figures.html", "pending.html"):
            page = self.read(name)
            self.assertTrue(page.lower().startswith("<!doctype html>"), name)
            self.assertIn('<html lang="en" data-repo="OWNER/NAME">', page, name)
            self.assertIn('<aside id="ask" hidden aria-label="Ask Claude about this page">', page, name)
            self.assertTrue(page.rstrip().endswith('<script src="ask.js" defer></script></body></html>'), name)
            self.assertIn(':root[data-theme="dark"]', page, name)
            self.assertIn(':root[data-theme="light"]', page, name)
            self.assertEqual(page.count("</body>"), 1, name)
        script = self.read("ask.js")
        self.assertIn('window.claude.use("sample")', script)
        self.assertIn("ask-fig", script)

    def test_the_box_turns_an_experiment_line_in_an_answer_into_a_request(self):
        # The Claude prompt path: the rules ask for one experiment: line when a run is asked for, the box reads
        # it into the panel's request lines, offers the prefilled issue always and Run as me only through the
        # page's dispatcher where the viewer's connector resolves (tools/textbook_site.py MESSAGE_JS).
        script = self.read("ask.js")
        for word in ("experiment: recipe=<name> epochs=<n> seed=<n> hours=<h> KEY=VALUE", "write no such line otherwise",
                     '/^experiment:[ \\t]*(.+?)[ \\t]*$/m', "<!-- schwingnet-experiment -->", 'labels: "experiment"',
                     "Request this run", "Run as me", "window.schwingnetConnector", "window.schwingnetDispatch",
                     'workflow: "experiment.yml", ref: "main"', "blocks: r.blocks.join(\" \")", "offerRun(null)"):
            self.assertIn(word, script, word)
        self.assertNotIn("callTool", script, "the box dispatches through the page's dispatcher alone")
        self.assertNotIn('use("mcp")', script)

    def test_no_record_is_among_the_files_and_the_record_points_at_github(self):
        files = hashes(self.out)
        self.assertNotIn("figures/01/a-figure.json", files)
        self.assertNotIn("figures/01/a-moving-figure.json", files)
        self.assertIn("figures/01/corpora.json", files, "the data a figure is drawn from stays")
        self.assertIn("figures/01/a-figure.png", files)
        self.assertIn("figures/01/a-moving-figure.html", files)
        self.assertNotIn(".textbook", files)
        page = self.read("chapter-01.html")
        self.assertIn('href="https://github.com/OWNER/NAME/blob/abc1234def5678/docs/textbook/figures/01/a-figure.json"',
                      page)
        self.assertNotIn('href="figures/01/a-figure.json"', page)

    def test_every_figure_gets_an_ask_button_beside_the_sites_own(self):
        page = self.read("chapter-01.html")
        blocks = page.count('<figure class="fig"')
        self.assertEqual(blocks, 3)
        self.assertEqual(page.count('class="button ask-fig"'), blocks)
        self.assertIn('data-subject="Figure 1.1: Caption of 01/a-figure, drawn for [the owner&#x27;s account]."', page)
        self.assertNotIn("&amp;#x27;", page)
        self.assertIn("Open the artifact&#x27;s page", page)
        self.assertIn("Re-run", page)
        button = page.index('class="button ask-fig"')
        self.assertLess(page.rindex("The record", 0, button), button, "the button comes after the site's own")

    def test_the_exported_pages_are_copied_with_their_trees_and_left_as_they_are(self):
        self.assertEqual(self.read("artifacts/second/index.html"), "<p>second</p>")
        self.assertTrue((self.out / "artifacts" / "second" / "data" / "table.js").exists())
        self.assertFalse((self.out / "artifacts" / "second" / "README.md").exists())
        self.assertFalse((self.out / "artifacts" / "eighth").exists())

    def test_the_batches_stay_under_the_limits_and_leave_the_page_out(self):
        summary = json.loads(self.read("batches.json"))
        listed = [f for batch in summary["batches"] for f in batch]
        self.assertNotIn("index.html", listed)
        files = hashes(self.out)
        self.assertEqual(sorted(listed), sorted(f for f in files if f not in ("index.html", "batches.json")))
        self.assertEqual(summary["files"], len(files) - 1)
        self.assertEqual(summary["bytes"], sum((self.out / f).stat().st_size for f in files if f != "batches.json"))
        self.assertEqual((summary["repo"], summary["sha"], summary["built"]), (REPO, SHA, "2026-10-24 18:42 UTC"))
        self.assertEqual(summary["skipped"], [])
        for batch in summary["batches"]:
            self.assertLessEqual(len(batch), textbook_artifact.PER_PUBLISH_FILES)
            self.assertLessEqual(sum((self.out / f).stat().st_size for f in batch), textbook_artifact.PER_PUBLISH_BYTES)

    def test_small_limits_make_several_batches_that_together_hold_every_file(self):
        paths = sorted(p for p in self.out.rglob("*") if p.is_file() and p.name not in ("index.html", "batches.json"))
        with mock.patch.object(textbook_artifact, "PER_PUBLISH_FILES", 3):
            groups = textbook_artifact.batches(paths, self.out)
        self.assertGreater(len(groups), 1)
        self.assertTrue(all(len(g) <= 3 for g in groups))
        self.assertEqual([f for g in groups for f in g], [p.relative_to(self.out).as_posix() for p in paths])
        with mock.patch.object(textbook_artifact, "PER_PUBLISH_BYTES", 40):
            groups = textbook_artifact.batches(paths, self.out)
        for group in groups:
            size = sum((self.out / f).stat().st_size for f in group)
            self.assertTrue(size <= 40 or len(group) == 1, group)

    def test_one_commit_builds_the_same_bytes_twice(self):
        again = Path(self.tmp.name) / "again"
        textbook_artifact.build(self.site, again, REPO, SHA, BUILT)
        self.assertEqual(hashes(again), hashes(self.out))

    def test_the_command_prints_a_summary(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = textbook_artifact.main([str(self.site), str(Path(self.tmp.name) / "cmd"), "--repo", REPO,
                                           "--sha", SHA, "--built", BUILT])
        self.assertEqual(code, 0)
        self.assertIn("publish batches; 6 artifact pages; 0 files over the size limit left out", out.getvalue())


class Pieces(unittest.TestCase):
    def test_the_built_date_is_the_commits_in_utc(self):
        self.assertEqual(textbook_artifact.built_words("2026-10-24T14:42:00-04:00"), "2026-10-24 18:42 UTC")
        self.assertEqual(textbook_artifact.built_words("2026-10-24T18:42:00Z"), "2026-10-24 18:42 UTC")
        self.assertEqual(textbook_artifact.built_words("2026-10-24 18:42:00"), "2026-10-24 18:42 UTC")
        with self.assertRaises(SystemExit):
            textbook_artifact.built_words("yesterday")

    def test_the_page_proper_keeps_the_heads_script_after_the_body(self):
        document = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>T</title><style>a{}</style>'
                    '<script>var x=1;</script></head><body><h1>Hi</h1></body></html>')
        proper = textbook_artifact.page_proper(document, REPO)
        self.assertTrue(proper.startswith("<title>SchwingNet Textbook</title>\n<style>a{}</style>\n"))
        self.assertLess(proper.index("<h1>Hi</h1>"), proper.index("<script>var x=1;</script>"))
        self.assertNotIn("<head>", proper)

    def test_a_figure_without_a_number_is_named_by_its_id(self):
        block = ('<figure class="fig" id="fig-01-x"><figcaption>No number</figcaption>'
                 '<div class="buttons"><a class="button" href="#">Re-run</a></div></figure>')
        self.assertIn('data-subject="figure fig-01-x"', textbook_artifact.figure_buttons(block))
        self.assertEqual(textbook_artifact.figure_buttons("<p>no figure</p>"), "<p>no figure</p>")

    def test_a_folder_that_is_no_site_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(SystemExit):
                textbook_artifact.build(folder, Path(folder) / "out", REPO, SHA, BUILT)


if __name__ == "__main__":
    unittest.main()
