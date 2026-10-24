"""tools/textbook_site.py lays the Artifact Textbook out as pages: one for
every chapter of the plan and every artifact in the record, each chapter
linking the artifacts it reads; a written narrative shown on its chapter's
page and checked there against the concept ledger, a superseded value given
without its disclaimer flagged; and what the book does not hold yet listed,
a folder with no record and a record no chapter reads, the latter beside the
chapter that reads its cluster's canonical artifact."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import textbook_site  # noqa: E402

NARRATIVE = """# 01 One

Label: schwingnet-internal. A test chapter.

The first page gave 98.2% exact level on whole lateral frames of the set.

The second page gives 97.4% exact level on whole lateral frames of the set.
"""


def record(folder, title, date):
    return {"repo": "SchwingNet", "folder": folder, "title": title, "link": f"https://claude.ai/artifact/{folder}",
            "date": date, "kind": "page", "genre": "report", "confidentiality": "schwingnet-other",
            "question": f"What does {title} answer?", "summary": f"{title} in brief.", "key_claims": [],
            "numbers": [{"value": "98.2", "unit": "%", "n": 148, "interval": None, "context": "exact level"}]}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def small_book(root):
    """A repository with one chapter reading the canonical artifact, the artifact it
    superseded read by no chapter, and a folder the synthesis has not read."""
    syn = root / "artifacts" / "_synthesis"
    for name in ("clusters.md", "concepts.md", "contradictions.md", "table-of-contents.md"):
        write(syn / name, f"# {name}\n\nSee [the second](../second/).\n")
    write(syn / "contradictions" / "one.md", "# Contradictions: One\n\nRows.\n")
    chapter = {"number": "01", "file": "docs/textbook/01-one.md", "title": "One", "purpose": "Settles one thing.",
               "questions_answered": ["Why one?"], "artifacts_primary": ["SchwingNet/second"],
               "artifacts_secondary": [], "repository_sources": [], "research_needed": "Nothing.",
               "confidentiality": "schwingnet-internal"}
    write(syn / "work" / "out" / "toc-hand.json",
          {"preface": "The plan.", "parts": [{"label": "Part I", "title": "Orientation", "chapters": [chapter]}]})
    write(syn / "inventory.json", {"artifacts": [record("first", "First", "2026-09-22"),
                                                 record("second", "Second", "2026-10-01")], "skipped": []})
    write(syn / "work" / "out" / "clustering.json", {"judged": {"clusters": [{
        "name": "One", "part": "schwingnet", "members": ["SchwingNet/first", "SchwingNet/second"],
        "canonical": ["SchwingNet/second"], "secondary_members": [], "duplicates": [],
        "superseded": [{"id": "SchwingNet/first", "by": "SchwingNet/second", "why": "Revised the next week."}]}]}})
    write(syn / "work" / "out" / "concepts.json", {"datasets": [], "checks": [], "figures": [{
        "id": "figure:0", "row": 0, "quantity": "exact level on whole lateral frames", "verdict": "updated-later",
        "artifacts": ["SchwingNet/first", "SchwingNet/second"],
        "quotes": ["98.2% exact level on whole lateral frames", "97.4% exact level on whole lateral frames"],
        "anchors": ["exact", "level", "whole", "lateral", "frames"], "unused": None,
        "values": [{"figure": "98.2", "percent": True, "status": "superseded", "side": "a"},
                   {"figure": "97.4", "percent": True, "status": "current", "side": "b"}]}]})
    write(syn / "work" / "out" / "state.json", {"stamped": "2026-10-24", "artifacts": {}})
    for folder in ("first", "second", "third"):
        write(root / "artifacts" / folder / "index.html", f"<p>{folder}</p>")
    write(root / "docs" / "textbook" / "01-one.md", NARRATIVE)


class ASmallBook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name) / "repo"
        small_book(root)
        cls.out = Path(cls.tmp.name) / "site"
        textbook_site.main([str(cls.out), "--root", str(root), "--repo", "OWNER/NAME", "--sha", "abc1234"])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def read(self, name):
        return (self.out / name).read_text(encoding="utf-8")

    def test_the_chapter_shows_its_narrative_and_links_what_it_reads(self):
        page = self.read("chapter-01.html")
        self.assertIn("The second page gives 97.4%", page)
        self.assertIn("artifact-second.html", page)
        self.assertNotIn("not written yet", page)

    def test_a_superseded_value_without_its_disclaimer_is_flagged(self):
        page = self.read("chapter-01.html")
        self.assertIn("gives a superseded value", page)
        self.assertIn("no disclaimer in the passage", page)
        self.assertIn("1 agree with the ledger and 1 give one another way", page)

    def test_what_the_book_does_not_hold_yet_is_listed(self):
        pending = self.read("pending.html")
        self.assertIn("third", pending)
        self.assertIn("artifact-first.html", pending)
        self.assertIn("New, not yet placed by the plan", self.read("chapter-01.html"))

    def test_a_superseded_artifact_says_so_on_its_page(self):
        page = self.read("artifact-first.html")
        self.assertIn("Superseded by", page)
        self.assertIn("not final values", page)

    def test_the_artifact_itself_is_served_beside_its_page(self):
        self.assertTrue((self.out / "files" / "second" / "index.html").exists())
        self.assertIn('src="files/second/index.html"', self.read("artifact-second.html"))

    def test_a_link_in_a_record_page_reaches_the_artifact_page(self):
        self.assertIn('href="artifact-second.html"', self.read("clusters.html"))

    def test_a_folder_it_did_not_build_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "keep.txt").write_text("mine", encoding="utf-8")
            with self.assertRaises(SystemExit):
                textbook_site.prepare(tmp)
            self.assertTrue((Path(tmp) / "keep.txt").exists())


class TheRepositorysOwnBook(unittest.TestCase):
    def test_every_chapter_and_every_artifact_has_a_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "site"
            self.assertEqual(textbook_site.main([str(out), "--repo", "OWNER/NAME", "--sha", "abc1234"]), 0)
            book = textbook_site.Book(ROOT)
            for _part, chapter in book.chapters:
                page = (out / textbook_site.chapter_page(chapter["number"])).read_text(encoding="utf-8")
                for aid in textbook_site.chapter_ids(chapter):
                    self.assertIn(textbook_site.artifact_page(aid), page, chapter["number"])
            for aid in book.records:
                self.assertTrue((out / textbook_site.artifact_page(aid)).exists(), aid)


if __name__ == "__main__":
    unittest.main()
