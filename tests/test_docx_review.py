"""tools/docx_review.py: a Word document's comments read into a review sheet
and a task, and a worker's revisions written back as tracked changes that
accept to the new text and reject to the old, formatting kept, with a
refusal where a revision would land on the wrong paragraph or lose what a
paragraph holds."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docx_review  # noqa: E402

FIRST = ("We measured lumbar levels in forty radiographs and found the detector "
         "agrees with readers most of the time.")
FIRST_NEW = ("We measured lumbar levels in forty radiographs and found the detector "
             "agrees with readers (kappa 0.81).")


def add_comment(path, author, text):
    """A comment of a reviewer's on the first paragraph, as Word would add it."""
    parts = docx_review.read_parts(path)
    comments = parts[docx_review.COMMENTS].decode("utf-8")
    comments = comments.replace("</w:comments>", f'<w:comment w:id="9" w:author="{author}" '
                                f'w:date="2026-10-19T00:00:00Z"><w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
                                "</w:comment></w:comments>")
    parts[docx_review.COMMENTS] = comments.encode("utf-8")
    document = parts[docx_review.DOCUMENT].decode("utf-8")
    document = document.replace("</w:p>", '<w:r><w:commentReference w:id="9"/></w:r></w:p>', 1)
    parts[docx_review.DOCUMENT] = document.encode("utf-8")
    docx_review.write_parts(path, parts, path)


def texts(path, view):
    parts = docx_review.read_parts(path)
    root = docx_review.parse(parts[docx_review.DOCUMENT])
    return [docx_review.paragraph_text(p, view) for p in docx_review.paragraphs(root)]


class DocxReviewTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.paper = self.folder / "papers" / "paper.docx"
        self.paper.parent.mkdir()
        docx_review.sample(self.paper)

    def test_extract_reads_comments_and_their_anchors(self):
        review = docx_review.extract(self.paper)
        self.assertEqual(review["paragraphs"][1]["text"], FIRST)
        first = review["comments"][0]
        self.assertEqual((first["author"], first["paragraphs"]), ("Reviewer 1", [1]))
        self.assertEqual(first["anchor"], "agrees with readers most of the time")
        self.assertEqual(len(docx_review.open_comments(review)), 3)

    def test_sheet_numbers_paragraphs_and_lists_comments_under_them(self):
        [written] = docx_review.write_sheets([self.paper])
        sheet = Path(written).read_text(encoding="utf-8")
        self.assertIn("[1] " + FIRST, sheet)
        self.assertIn("> Comment 0 by Reviewer 1, on paragraphs 1:", sheet)
        self.assertTrue(sheet.isascii())

    def test_one_task_per_document_in_the_task_forms_shape(self):
        [task] = docx_review.tasks(self.folder)
        self.assertEqual(task["title"], f"Task: revise {self.paper.as_posix()}")
        for heading in ("### Goal", "### Acceptance", "### Files likely touched"):
            self.assertIn(heading, task["body"])
        self.assertIn(self.paper.with_suffix(".revisions.json").as_posix(), task["body"])

    def fake_github(self, issues, calls):
        def run(*args):
            calls.append(args)
            if args[0] == "api":
                return "\n".join(json.dumps(i) for i in issues)
            if args[:2] == ("issue", "create"):
                issues.append({"number": 7, "state": "OPEN", "body": args[args.index("--body") + 1],
                               "labels": ["todo"], "author": "github-actions[bot]", "association": "NONE"})
            if args[:2] == ("issue", "edit") and "--body" in args:
                next(i for i in issues if i["number"] == int(args[2]))["body"] = args[args.index("--body") + 1]
            return ""
        return run

    def test_watch_opens_a_task_then_tells_it_only_of_new_comments(self):
        issues, calls = [], []
        run = self.fake_github(issues, calls)
        self.assertEqual(docx_review.watch([self.paper], run), [str(self.paper)])
        self.assertEqual(docx_review.watch([self.paper], run), [])
        issues[0]["state"], issues[0]["labels"] = "CLOSED", ["in-review", "worker:papers"]
        add_comment(self.paper, "Reviewer 3", "Cite the reader study.")
        docx_review.apply(self.paper, [{"paragraph": 1, "old": FIRST, "text": FIRST, "why": "Noted."}])
        calls.clear()
        self.assertEqual(docx_review.watch([self.paper], run), [str(self.paper)])
        told = [c for c in calls if c[:2] == ("issue", "comment")]
        self.assertEqual(len(told), 1)
        self.assertIn("Reviewer 3: Cite the reader study.", told[0][-1])
        self.assertNotIn("Noted.", told[0][-1])
        for call in (("issue", "reopen", "7"), ("issue", "edit", "7", "--remove-label", "in-review"),
                     ("issue", "edit", "7", "--remove-label", "worker:papers"),
                     ("issue", "edit", "7", "--add-label", "todo")):
            self.assertIn(call, calls)
        self.assertEqual(docx_review.watch([self.paper], run), [])

    def test_watch_takes_no_issue_from_someone_who_may_not_write(self):
        mark = docx_review.DOCUMENT_MARK.format(self.paper.as_posix())
        issues = [{"number": 99, "state": "OPEN", "body": mark + "\n<!-- symphony-comments:  -->",
                   "labels": [], "author": "stranger", "association": "NONE"}]
        calls = []
        docx_review.watch([self.paper], self.fake_github(issues, calls))
        self.assertFalse([c for c in calls if "99" in c])
        self.assertTrue([c for c in calls if c[:2] == ("issue", "create")])

    def test_watch_appends_the_comments_mark_a_person_removed(self):
        issues, calls = [], []
        run = self.fake_github(issues, calls)
        docx_review.watch([self.paper], run)
        issues[0]["body"] = docx_review.COMMENTS_MARK.sub("", issues[0]["body"])
        docx_review.watch([self.paper], run)
        self.assertEqual(docx_review.watch([self.paper], run), [])

    def test_watch_goes_on_past_a_document_it_cannot_read(self):
        broken = self.folder / "papers" / "broken.docx"
        broken.write_bytes(b"not a zip")
        issues, calls = [], []
        self.assertEqual(docx_review.watch([broken, self.paper], self.fake_github(issues, calls)), [str(self.paper)])

    def test_a_comment_keeps_its_key_when_word_renumbers_it(self):
        before = set(docx_review.awaiting(self.paper))
        parts = docx_review.read_parts(self.paper)
        for name in (docx_review.DOCUMENT, docx_review.COMMENTS):
            parts[name] = parts[name].replace(b'w:id="0"', b'w:id="40"')
        docx_review.write_parts(self.paper, parts, self.paper)
        self.assertEqual(set(docx_review.awaiting(self.paper)), before)

    def test_apply_writes_tracked_changes_that_accept_and_reject(self):
        revisions = [
            {"paragraph": 1, "old": FIRST, "text": FIRST_NEW, "comment": "0", "why": "Gave the kappa."},
            {"paragraph": 3, "old": "Results are shown in Table 1.",
             "text": "Results are shown in Table 1.", "comment": "2", "why": "Needs the author's data."},
        ]
        before = texts(self.paper, "accepted")
        docx_review.apply(self.paper, revisions)
        accepted, rejected = texts(self.paper, "accepted"), texts(self.paper, "rejected")
        self.assertEqual(accepted[1], FIRST_NEW)
        self.assertEqual(rejected, before)
        self.assertEqual(accepted[3], before[3])
        document = zipfile.ZipFile(self.paper).read(docx_review.DOCUMENT).decode("utf-8")
        self.assertIn('w:author="Claude"', document)
        self.assertIn("<w:b /></w:rPr><w:t xml:space=\"preserve\">forty", document)
        claude = [c for c in docx_review.extract(self.paper)["comments"] if c["author"] == "Claude"]
        self.assertEqual([c["text"] for c in claude],
                         ["On comment 0: Gave the kappa.", "On comment 2: Needs the author's data."])

    def test_a_changed_phrase_is_one_deletion_and_one_insertion(self):
        docx_review.apply(self.paper, [{"paragraph": 1, "old": FIRST, "text": FIRST_NEW}])
        document = zipfile.ZipFile(self.paper).read(docx_review.DOCUMENT).decode("utf-8")
        self.assertIn(">most of the time</w:delText>", document)

    def test_apply_refuses_a_paragraph_that_moved(self):
        with self.assertRaises(docx_review.Refused):
            docx_review.apply(self.paper, [{"paragraph": 2, "old": FIRST, "text": FIRST_NEW}])

    def test_apply_refuses_a_paragraph_with_a_tracked_change_already(self):
        docx_review.apply(self.paper, [{"paragraph": 1, "old": FIRST, "text": FIRST_NEW}])
        with self.assertRaises(docx_review.Refused) as refusal:
            docx_review.apply(self.paper, [{"paragraph": 1, "old": FIRST_NEW, "text": FIRST}])
        self.assertIn("revise it by hand", str(refusal.exception))

    def test_the_command_line_runs_the_loop(self):
        revisions = self.folder / "paper.revisions.json"
        revisions.write_text(json.dumps([{"paragraph": 1, "old": FIRST, "text": FIRST_NEW}]))
        out = self.folder / "out.docx"
        tool = [sys.executable, str(ROOT / "tools" / "docx_review.py")]
        subprocess.run(tool + ["apply", str(self.paper), str(revisions), "--out", str(out)], check=True,
                       capture_output=True)
        self.assertEqual(texts(out, "accepted")[1], FIRST_NEW)
        self.assertEqual(texts(self.paper, "accepted")[1], FIRST)


def document_with(body):
    """A sample .docx whose body is replaced, to put Word's own shapes in it."""
    folder = Path(tempfile.mkdtemp())
    path = folder / "word.docx"
    docx_review.sample(path)
    parts = docx_review.read_parts(path)
    parts[docx_review.DOCUMENT] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{docx_review.W_URI}" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" mc:Ignorable="w14">'
        f"<w:body>{body}</w:body></w:document>").encode("utf-8")
    docx_review.write_parts(path, parts, path)
    return folder, path


PICTURE = ('<w:p><w:r><w:drawing><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
           '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"/>'
           '</a:graphic></w:drawing></w:r></w:p>')
TAB_STOPS = ('<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="720"/></w:tabs></w:pPr>'
             '<w:r><w:t>Name</w:t></w:r><w:r><w:tab/><w:t>Page</w:t></w:r></w:p>')
TEXT_BOX = ('<w:p><w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><w:txbxContent>'
            '<w:p><w:r><w:t>box</w:t></w:r></w:p></w:txbxContent></w:drawing></mc:Choice><mc:Fallback>'
            '<w:pict><w:txbxContent><w:p><w:r><w:t>box</w:t></w:r></w:p></w:txbxContent></w:pict>'
            '</mc:Fallback></mc:AlternateContent></w:r></w:p>')


class PanelTest(unittest.TestCase):
    """Several reviewers, each a lens with its own author name, on one paper."""

    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder)
        self.paper = self.folder / "paper.docx"
        docx_review.sample(self.paper)

    def authors(self, tag):
        document = zipfile.ZipFile(self.paper).read(docx_review.DOCUMENT).decode("utf-8")
        import re
        return set(re.findall(rf'<w:{tag} w:id="\d+" w:author="([^"]+)"', document))

    def test_each_lens_writes_under_its_own_name(self):
        methods = [{"paragraph": 1, "old": FIRST, "text": FIRST_NEW, "why": "Report the agreement."}]
        plain = [{"paragraph": 3, "old": "Results are shown in Table 1.",
                  "text": "Table 1 shows the results.", "why": "Active voice."}]
        report = docx_review.panel(self.paper, [("Methods reviewer", methods), ("Plain language", plain)])
        self.assertEqual([(r["author"], r["revised"], r["suggested"]) for r in report],
                         [("Methods reviewer", 1, 0), ("Plain language", 1, 0)])
        self.assertEqual(self.authors("ins"), {"Methods reviewer", "Plain language"})
        accepted = texts(self.paper, "accepted")
        self.assertEqual((accepted[1], accepted[3]), (FIRST_NEW, "Table 1 shows the results."))
        mine = {c["author"] for c in docx_review.extract(self.paper)["comments"]}
        self.assertTrue({"Methods reviewer", "Plain language"} <= mine)

    def test_a_later_lens_on_a_changed_paragraph_suggests_in_a_comment(self):
        first = [{"paragraph": 1, "old": FIRST, "text": FIRST_NEW}]
        second = [{"paragraph": 1, "old": FIRST, "text": FIRST.replace("forty", "40"), "why": "Numerals."}]
        report = docx_review.panel(self.paper, [("Editor", first), ("Style", second)])
        self.assertEqual((report[1]["revised"], report[1]["suggested"]), (0, 1))
        self.assertEqual(self.authors("ins"), {"Editor"})
        style = [c["text"] for c in docx_review.extract(self.paper)["comments"] if c["author"] == "Style"]
        self.assertEqual(len(style), 1)
        self.assertTrue(style[0].startswith("Suggests: We measured lumbar levels in 40 radiographs"))
        self.assertIn("Why: Numerals.", style[0])

    def test_a_later_lens_comments_on_a_changed_paragraph_without_a_revert(self):
        first = [{"paragraph": 1, "old": FIRST, "text": FIRST_NEW}]
        note = [{"paragraph": 1, "old": FIRST, "text": FIRST, "why": "Cite the readers."}]
        same = [{"paragraph": 1, "old": FIRST, "text": FIRST_NEW, "why": "Agree."}]
        report = docx_review.panel(self.paper, [("Editor", first), ("Methods", note), ("Domain", same)])
        self.assertEqual([(r["revised"], r["suggested"], r["commented"]) for r in report],
                         [(1, 0, 0), (0, 0, 1), (0, 0, 1)])
        comments = {c["author"]: c["text"] for c in docx_review.extract(self.paper)["comments"]}
        self.assertEqual((comments["Methods"], comments["Domain"]), ("Cite the readers.", "Agree."))
        self.assertEqual(texts(self.paper, "accepted")[1], FIRST_NEW)

    def test_a_bad_entry_is_skipped_and_the_rest_goes_on(self):
        lens = [{"paragraph": 99, "old": "", "text": "x"},
                {"paragraph": 1, "old": FIRST, "text": "two\nlines"},
                {"paragraph": 1, "old": FIRST, "text": FIRST_NEW}]
        report = docx_review.panel(self.paper, [("Editor", lens)])
        self.assertEqual((report[0]["revised"], len(report[0]["skipped"])), (1, 2))

    def test_an_author_name_must_be_one_plain_line(self):
        for name in ("", "a\nb", "x" * 61, '<w:t>'):
            with self.assertRaises(docx_review.Refused):
                docx_review.panel(self.paper, [(name, [])])

    def test_the_command_line_takes_one_lens_a_flag(self):
        revisions = self.folder / "m.json"
        revisions.write_text(json.dumps([{"paragraph": 1, "old": FIRST, "text": FIRST_NEW}]))
        out = self.folder / "out.docx"
        done = subprocess.run([sys.executable, str(ROOT / "tools/docx_review.py"), "panel", str(self.paper),
                               "--lens", f"Methods={revisions}", "--out", str(out)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout)[0]["revised"], 1)
        self.assertEqual(texts(out, "accepted")[1], FIRST_NEW)
        self.assertEqual(texts(self.paper, "accepted")[1], FIRST)


class WordShapesTest(unittest.TestCase):
    def shaped(self, body):
        folder, path = document_with(body)
        self.addCleanup(shutil.rmtree, folder)
        return path

    def test_a_picture_elsewhere_keeps_its_prefixes_declared(self):
        path = self.shaped("<w:p><w:r><w:t>Hello world</w:t></w:r></w:p>" + PICTURE)
        docx_review.apply(path, [{"paragraph": 0, "old": "Hello world", "text": "Hello there"}])
        document = zipfile.ZipFile(path).read(docx_review.DOCUMENT)
        docx_review.ET.fromstring(document)
        self.assertIn(b'mc:Ignorable="w14"', document)
        self.assertEqual(texts(path, "accepted")[0], "Hello there")

    def test_tab_stops_are_no_text(self):
        path = self.shaped(TAB_STOPS)
        self.assertEqual(texts(path, "accepted"), ["Name\tPage"])
        docx_review.apply(path, [{"paragraph": 0, "old": "Name\tPage", "text": "Name\tFolio"}])
        self.assertEqual(texts(path, "accepted"), ["Name\tFolio"])

    def test_a_text_box_is_listed_once(self):
        path = self.shaped(TEXT_BOX)
        listed = [p["text"] for p in docx_review.extract(path)["paragraphs"]]
        self.assertEqual(listed.count("box"), 1)

    def test_a_line_break_in_new_text_is_refused(self):
        path = self.shaped("<w:p><w:r><w:t>Hello</w:t></w:r></w:p>")
        with self.assertRaises(docx_review.Refused):
            docx_review.apply(path, [{"paragraph": 0, "old": "Hello", "text": "Hello\nworld"}])


if __name__ == "__main__":
    unittest.main()
