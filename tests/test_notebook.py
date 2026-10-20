"""tools/notebook.py: notebooks of a drive's files checked against the
catalog, summed into a card's counts, written out as a notebook repository's
starting files, and a citation manager's export read into references.
Every name here is made up."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import notebook  # noqa: E402

CATALOG = {"files": [
    {"path": "OneDrive/paper.docx", "name": "paper.docx", "kind": "document", "size": 900,
     "modified": "2026-01-02T03:04:05Z", "web": "https://example.test/paper.docx", "drive": "b!d", "id": "01A"},
    {"path": "OneDrive/Data/table.csv", "name": "table.csv", "kind": "table", "size": 100,
     "modified": "", "web": "", "drive": "b!d", "id": "01B"},
    {"path": "OneDrive/taxes.pdf", "name": "taxes.pdf", "kind": "pdf", "size": 5, "drive": "b!d", "id": "01C"},
]}


def proposal(**changes):
    one = {"slug": "paper", "title": "The paper", "summary": "A paper and its data.",
           "repository": "paper-notebook", "files": ["OneDrive/paper.docx", "OneDrive/Data/table.csv"]}
    one.update(changes)
    return {"notebooks": [one], "left_out": ["OneDrive/taxes.pdf"]}


class Proposal(unittest.TestCase):
    def test_a_sound_proposal_has_no_problems(self):
        self.assertEqual(notebook.problems_of(proposal(), CATALOG), [])

    def test_a_file_the_catalog_does_not_list_is_named(self):
        problems = notebook.problems_of(proposal(files=["OneDrive/nowhere.docx"]), CATALOG)
        self.assertIn("nowhere.docx", problems[0])

    def test_a_bad_slug_or_repository_is_refused(self):
        self.assertTrue(notebook.problems_of(proposal(slug="Paper One"), CATALOG))
        self.assertTrue(notebook.problems_of(proposal(repository="no spaces"), CATALOG))

    def test_one_file_may_sit_in_two_notebooks(self):
        both = proposal()
        both["notebooks"].append(dict(both["notebooks"][0], slug="data", files=["OneDrive/Data/table.csv"]))
        self.assertEqual(notebook.problems_of(both, CATALOG), [])

    def test_a_slug_named_twice_is_refused(self):
        twice = proposal()
        twice["notebooks"].append(dict(twice["notebooks"][0]))
        self.assertIn("named twice", " ".join(notebook.problems_of(twice, CATALOG)))

    def test_a_card_gives_counts_and_no_names(self):
        known = notebook.files_by_path(CATALOG)
        card = notebook.summary_of(proposal()["notebooks"][0], known)
        self.assertEqual((card["files"], card["bytes"], card["latest"]), (2, 1000, "2026-01-02T03:04:05Z"))
        self.assertNotIn("paper.docx", json.dumps(card))


class Make(unittest.TestCase):
    def test_make_writes_the_repositorys_files(self):
        with tempfile.TemporaryDirectory() as out:
            record = notebook.make(proposal(), CATALOG, "paper", out)
            self.assertEqual([item["id"] for item in record["items"]], ["01A", "01B"])
            page = (Path(out) / "NOTEBOOK.md").read_text()
            self.assertIn("[paper.docx](https://example.test/paper.docx)", page)
            self.assertIn("| table.csv | table |", page)
            self.assertTrue((Path(out) / "research" / "README.md").exists())
            self.assertEqual(json.loads((Path(out) / "notebook.json").read_text())["slug"], "paper")

    def test_a_name_cannot_write_markdown(self):
        self.assertEqual(notebook.plain("a|b [x](y)"), "a\\|b \\[x\\]\\(y\\)")
        self.assertEqual(notebook.plain("- x"), "\\- x")

    def test_a_link_keeps_its_brackets_and_only_https_is_linked(self):
        self.assertEqual(notebook.link("https://a/notes).docx"), "https://a/notes%29.docx")
        self.assertIsNone(notebook.link("javascript:alert(1)"))

    def test_make_will_not_write_names_into_the_template(self):
        with self.assertRaises(notebook.NotebookError):
            notebook.make(proposal(), CATALOG, "paper", ROOT)

    def test_a_malformed_proposal_is_a_problem_not_a_crash(self):
        for bad in ([], {"notebooks": [dict(proposal()["notebooks"][0], files=[["p"]])]},
                    dict(proposal(), left_out=None), dict(proposal(), left_out="abc")):
            self.assertTrue(notebook.problems_of(bad, CATALOG))
        with self.assertRaises(notebook.NotebookError):
            notebook.problems_of(proposal(), {"files": None})

    def test_an_unknown_slug_stops(self):
        with tempfile.TemporaryDirectory() as out, self.assertRaises(notebook.NotebookError):
            notebook.make(proposal(), CATALOG, "other", out)


BIB = """@article{smith2020,
  title = {A {Fast} Matching},
  author = {Smith, Ann and Lee, Bo},
  journal = {J. Graphs},
  year = 2020,
  doi = {10.1000/ABC}
}
@comment{ignored}
"""

RIS = """TY  - JOUR
AU  - Smith, Ann
AU  - Lee, Bo
TI  - A Fast Matching
PY  - 2020///
DO  - 10.1000/abc
ER  -
TY  - BOOK
T1  - Untitled Book
ER  -
"""


class References(unittest.TestCase):
    def read(self, text, suffix):
        with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as handle:
            handle.write(text)
        try:
            return notebook.read_references(handle.name)
        finally:
            Path(handle.name).unlink()

    def test_bibtex(self):
        [entry] = self.read(BIB, ".bib")
        self.assertEqual(entry, {"key": "smith2020", "title": "A Fast Matching", "authors": ["Smith, Ann", "Lee, Bo"],
                                 "year": "2020", "doi": "10.1000/abc", "venue": "J. Graphs",
                                 "url": "", "uri": ""})

    def test_zotero_items_carry_their_library_uri(self):
        items = [{"key": "ABCD1234", "data": {"key": "ABCD1234", "itemType": "journalArticle", "title": "T",
                  "creators": [{"lastName": "Smith", "firstName": "Ann"}, {"name": "A Consortium"}],
                  "date": "March 2021", "DOI": "10.1/X", "url": "https://example.test/t"}},
                 {"key": "NOTE0001", "data": {"key": "NOTE0001", "itemType": "note"}},
                 {"key": "ANNO0001", "data": {"key": "ANNO0001", "itemType": "annotation"}}]
        [entry] = notebook.zotero(items, "users/42")
        self.assertEqual((entry["authors"], entry["year"], entry["uri"], entry["url"]),
                         (["Smith, Ann", "A Consortium"], "2021", "http://zotero.org/users/42/items/ABCD1234",
                          "https://example.test/t"))
        with self.assertRaises(notebook.NotebookError):
            notebook.zotero(items, "users/../x")

    def test_zotero_leaves_editors_out_and_finds_a_doi_in_extra(self):
        items = [{"data": {"key": "K1", "itemType": "conferencePaper", "title": "P", "proceedingsTitle": "Proc",
                  "creators": [{"creatorType": "author", "lastName": "A"}, {"creatorType": "editor", "lastName": "E"}],
                  "extra": "Note\nDOI: 10.5/Y"}}]
        [entry] = notebook.zotero(items, "groups/7")
        self.assertEqual((entry["authors"], entry["doi"], entry["venue"]), (["A"], "10.5/y", "Proc"))

    def test_an_entry_closed_on_its_own_line_keeps_its_own_fields(self):
        text = "@article{a,\n  title={A}}\n@article{b,\n  title={B},\n  doi={10.1/b}\n  }\n@book(c, title = \"C\")\n"
        found = self.read(text, ".bib")
        self.assertEqual([(each["key"], each["title"], each["doi"]) for each in found],
                         [("a", "A", ""), ("b", "B", "10.1/b"), ("c", "C", "")])

    def test_deep_braces_and_accents(self):
        [entry] = self.read('@article{m,\r\n title = {{A {Fast} Matching}},\r\n author = {M{\\"{u}}ller, Hans and Lee, Bo}\r\n}', ".bib")
        self.assertEqual((entry["title"], entry["authors"]), ("A Fast Matching", ["Muller, Hans", "Lee, Bo"]))

    def test_ris_after_header_lines_and_an_empty_result_stops(self):
        [entry] = self.read("Provider: X\nContent: text/plain\n\nTY  - JOUR\nTI  - T\nER  - \n", ".ris")
        self.assertEqual(entry["title"], "T")
        with self.assertRaises(notebook.NotebookError):
            self.read("nothing here", ".bib")

    def test_ris_reads_the_same_and_keys_what_has_no_id(self):
        first, second = self.read(RIS, ".ris")
        self.assertEqual((first["title"], first["year"], first["doi"]), ("A Fast Matching", "2020", "10.1000/abc"))
        self.assertEqual((second["key"], second["title"]), ("ref2", "Untitled Book"))

    def test_the_command_line_reports_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            export, out = Path(folder) / "lib.bib", Path(folder) / "references.json"
            export.write_text(BIB)
            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                self.assertEqual(notebook.main(["refs", "--export", str(export), "--out", str(out)]), 0)
            self.assertEqual(json.loads(printed.getvalue()), {"references": 1, "with_doi": 1})


if __name__ == "__main__":
    unittest.main()
