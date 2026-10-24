"""tools/textbook_site.py lays the Artifact Textbook out as pages: one for
every chapter of the plan and every artifact in the record, each chapter
linking the artifacts it reads; a written narrative shown on its chapter's
page and checked there against the concept ledger, a superseded value given
without its disclaimer on its line flagged; what the book does not hold yet
listed, a folder with no record, a record no chapter reads (beside the
chapter that reads its cluster's canonical artifact), a record whose folder is
gone and a chapter file the plan does not name; the owner's account names and
a person named by title kept off the pages; no copy of an artifact
served, each one opening on claude.ai; and each figure a chapter places
shown with its record's grade, status and source panel, Explore and Re-run,
an interactive figure in place of its image, one with no record said to have
none, and every figure listed with how far it is traced."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import textbook_site  # noqa: E402

LONG_LINE = ("In the earliest record the figure was 98.2% exact level on whole lateral frames of the set, read "
             "from the first page as it stood when the first page was made, before the second page revised the "
             "count, recounted every frame it held and gave the figure that the record now keeps for the set, "
             "and the first page was never read again after that revision, so the older figure is given here only "
             "as a record, not a final value.")
NARRATIVE = f"""# 01 One

Label: schwingnet-internal. A test chapter.

The first page gave 98.2% exact level on whole lateral frames of the set.

The second page gives 97.4% exact level on whole lateral frames of the set.

{LONG_LINE}

The figures follow.

![A figure](figures/01/a-figure.png)
*Figure 1.1. A drawn figure. Source: [record](figures/01/a-figure.json).*

![A moving figure](figures/01/a-moving-figure.png)
*Figure 1.2. A figure one can move. Source: [record](figures/01/a-moving-figure.json).*

![An untraced figure](figures/01/untraced.png)
*Figure 1.3. A figure with no record yet.*
"""


def figure_record(fid, where, command=None, made_by=None, data=()):
    return {"id": fid, "title": f"Title of {fid}", "caption": f"Caption of {fid}, drawn for someacct.", "chapter": "01",
            "grade": "Reported", "status": "a record, not a final value",
            "source": {"kind": "artifact", "artifact": "artifacts/second/", "artifact_url": None, "made_by": made_by,
                       "commit": None, "data": list(data), "run": None, "notes": "Traced from the manifest."},
            "explore": [{"label": "The artifact", "href": "artifacts/second/"},
                        {"label": "The method", "href": "docs/method.md"}],
            "rerun": {"where": where, "command": command, "cost": "one GPU job", "needs_owner_word": where == "grid"}}
# No git of the test's runs gc or maintenance on its own, as tests/test_claim_skill.py says why.
QUIET = {"gc.auto": "0", "gc.autoDetach": "false", "maintenance.auto": "false", "maintenance.autoDetach": "false",
         "receive.autogc": "false"}
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_CONFIG_COUNT": str(len(QUIET)),
           **{f"GIT_CONFIG_KEY_{i}": key for i, key in enumerate(QUIET)},
           **{f"GIT_CONFIG_VALUE_{i}": value for i, value in enumerate(QUIET.values())}}


def record(folder, title, date, **fields):
    return {"repo": "SchwingNet", "folder": folder, "title": title, "link": f"https://claude.ai/artifact/{folder}",
            "date": date, "kind": "page", "genre": "report", "confidentiality": "schwingnet-other",
            "question": f"What does {title} answer?", "summary": f"{title} in brief.", "key_claims": [],
            "numbers": [{"value": "98.2", "unit": "%", "n": 148, "interval": None, "context": "exact level"}], **fields}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True,
                          env={**os.environ, **GIT_ENV}).stdout.strip()


def small_book(root):
    """A repository with one chapter reading the canonical artifact, the artifact it superseded
    read by no chapter, a folder the synthesis has not read, two artifacts that share a title, a
    record whose folder is gone and a chapter file no chapter of the plan names, committed, with
    two of its folders stamped as they were when their records were read."""
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
    shared = [{"title": "Shared", "relation": "builds on", "why": "It reads the shared figures."}]
    write(syn / "inventory.json", {"artifacts": [
        record("first", "First", "2026-09-22", account="someacct", summary="Made for Dr. Smith by someacct."),
        record("second", "Second", "2026-10-01", cross_references=["owner-login/some-repo, branch main"]),
        record("fourth", "Fourth", "2026-10-02", related_titles=shared),
        record("fifth", "Shared", "2026-09-01", related_titles=shared),
        record("sixth", "Shared", "2026-09-05"),
        record("seventh", "Seventh", "2026-09-07")], "skipped": []})
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
    for folder in ("first", "second", "third", "fourth", "fifth", "sixth"):
        write(root / "artifacts" / folder / "index.html", f"<p>{folder}</p>")
    write(root / ".github" / "CODEOWNERS", "# Every file asks the owner.\n* @owner-login\n")
    write(root / "docs" / "textbook" / "01-one.md", NARRATIVE)
    figures = root / "docs" / "textbook" / "figures" / "01"
    write(figures / "a-figure.json", figure_record("01/a-figure", "grid", "sbatch slurm/draw.sh", "tools/draw.py"))
    write(figures / "a-figure.png", "not really a png")
    write(figures / "a-moving-figure.json", figure_record("01/a-moving-figure", "none", data=["data/x.json"]))
    write(figures / "a-moving-figure.png", "fallback")
    write(figures / "a-moving-figure.html", "<!doctype html><p>moves</p>")
    write(figures / "untraced.png", "no record")
    write(root / "docs" / "textbook" / "02-unplanned.md", "# 02 Unplanned\n\nA chapter the plan does not name.\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "A small book")
    # The second artifact changed since its record was read; the third was stamped unread by hand.
    write(syn / "work" / "out" / "state.json", {"stamped": "2026-10-24", "artifacts": {
        "SchwingNet/first": git(root, "rev-parse", "HEAD:artifacts/first"),
        "SchwingNet/second": "0" * 40, "SchwingNet/third": "1" * 40}})


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
        self.assertIn("1 agree with the ledger and 2 give one another way", page)
        rows = {row.split("</td>", 1)[0]: row for row in page.split("<tr><td>")[1:]}
        self.assertIn("no disclaimer in the passage", rows["line 5"])

    def test_a_disclaimer_late_in_a_long_line_still_counts(self):
        rows = {row.split("</td>", 1)[0]: row for row in self.read("chapter-01.html").split("<tr><td>")[1:]}
        self.assertIn("gives a superseded value", rows["line 9"])
        self.assertNotIn("no disclaimer in the passage", rows["line 9"])

    def test_what_the_book_does_not_hold_yet_is_listed(self):
        pending = self.read("pending.html")
        self.assertIn("third", pending)
        self.assertIn("artifact-first.html", pending)
        self.assertIn("New, not yet placed by the plan", self.read("chapter-01.html"))

    def test_a_changed_artifact_is_listed_and_a_stamped_folder_with_no_record_breaks_nothing(self):
        changed = self.read("pending.html").split("<h2>Changed since its record was read</h2>", 1)[1].split("<h2>", 1)[0]
        self.assertIn("artifact-second.html", changed)
        self.assertNotIn("first", changed)
        self.assertNotIn("third", changed)

    def test_a_record_whose_folder_is_gone_and_an_unplanned_chapter_file_are_listed(self):
        pending = self.read("pending.html")
        gone = pending.split("<h2>Recorded, but its folder is gone</h2>", 1)[1].split("<h2>", 1)[0]
        self.assertIn("artifact-seventh.html", gone)
        self.assertIn("docs/textbook/02-unplanned.md", pending)
        self.assertNotIn("Its files in the repository", self.read("artifact-seventh.html"))

    def test_a_superseded_artifact_says_so_on_its_page(self):
        page = self.read("artifact-first.html")
        self.assertIn("Superseded by", page)
        self.assertIn("not final values", page)

    def test_an_artifact_opens_on_claude_ai_and_no_copy_is_served(self):
        self.assertFalse((self.out / "files").exists())
        page = self.read("artifact-second.html")
        self.assertIn('href="https://claude.ai/artifact/second"', page)
        self.assertNotIn("<iframe", page)

    def test_account_names_and_a_person_named_by_title_are_kept_off_the_pages(self):
        first, second = self.read("artifact-first.html"), self.read("artifact-second.html")
        self.assertIn("Made for [a colleague] by [the owner&#x27;s account].", first)
        self.assertNotIn("someacct", first)
        self.assertNotIn("Smith", first)
        self.assertIn("[the owner&#x27;s account]/some-repo", second)
        self.assertNotIn("owner-login", second)

    def test_a_title_two_records_share_links_each_of_them(self):
        fourth, fifth = self.read("artifact-fourth.html"), self.read("artifact-fifth.html")
        self.assertIn('href="artifact-fifth.html">2026-09-01</a>', fourth)
        self.assertIn('href="artifact-sixth.html">2026-09-05</a>', fourth)
        self.assertIn('<a href="artifact-sixth.html">Shared</a>', fifth)
        self.assertNotIn('href="artifact-fifth.html"', fifth)

    def test_a_link_in_a_record_page_reaches_the_artifact_page(self):
        self.assertIn('href="artifact-second.html"', self.read("clusters.html"))

    def test_a_folder_it_did_not_build_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "keep.txt").write_text("mine", encoding="utf-8")
            with self.assertRaises(SystemExit):
                textbook_site.prepare(tmp)
            self.assertTrue((Path(tmp) / "keep.txt").exists())


    # the figures (issue #215)

    def figure(self, fid):
        page = self.read("chapter-01.html")
        start = page.index(f'id="fig-{fid}"')
        return page[start:page.index("</figure>", start)]

    def test_a_figure_shows_its_image_caption_grade_and_status(self):
        block = self.figure("01-a-figure")
        self.assertIn('<img src="figures/01/a-figure.png"', block)
        self.assertIn("<strong>Figure 1.1.</strong> Caption of 01/a-figure", block)
        self.assertIn("Reported", block)
        self.assertIn("a record, not a final value", block)
        self.assertIn("traced to the script", block)
        self.assertNotIn("*Figure", self.read("chapter-01.html"))

    def test_its_source_panel_explores_and_reruns(self):
        block = self.figure("01-a-figure")
        self.assertIn('href="artifact-second.html"', block)
        self.assertIn('href="https://github.com/OWNER/NAME/blob/abc1234/docs/method.md"', block)
        self.assertIn("https://github.com/OWNER/NAME/issues/new?labels=figure-rerun", block)
        self.assertIn("figure-rerun-id%3A+01%2Fa-figure", block)
        self.assertIn("owner&#x27;s word for this one run", block)
        self.assertIn("sbatch slurm/draw.sh", block)
        self.assertIn('href="figures/01/a-figure.json"', block)

    def test_an_interactive_figure_shows_in_place_of_its_image(self):
        block = self.figure("01-a-moving-figure")
        self.assertIn('<iframe src="figures/01/a-moving-figure.html"', block)
        self.assertNotIn("<img", block)
        self.assertIn("traced to the data", block)
        self.assertIn("No command is recorded", block)

    def test_a_figure_with_no_record_says_so(self):
        page = self.read("chapter-01.html")
        self.assertIn('<img src="figures/01/untraced.png"', page)
        self.assertIn("This figure has no record yet", page)

    def test_the_figures_are_served_and_listed_with_their_provenance(self):
        self.assertTrue((self.out / "figures" / "01" / "a-figure.png").exists())
        self.assertTrue((self.out / "figures" / "01" / "a-moving-figure.html").exists())
        listing = self.read("figures.html")
        self.assertIn("2 figures", listing)
        self.assertIn("Traced to the script that drew it: 1; to its data or run only: 1; to the artifact alone: 0", listing)
        self.assertIn('href="chapter-01.html#fig-01-a-figure"', listing)
        self.assertIn('href="figures.html"', self.read("index.html"))

    def test_a_record_s_prose_goes_through_the_privacy_pass(self):
        self.assertNotIn("someacct", self.read("chapter-01.html"))


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
