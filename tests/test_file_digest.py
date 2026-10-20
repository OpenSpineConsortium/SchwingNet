"""tools/file_digest.py: each kind of file a drive holds read as a short
text, Word, Excel, CSV, PowerPoint, a notebook, code, a PDF and images;
the kind told from a name or a Google file's type; and a broken or hostile
file said to be unreadable, never an error, and never read past its limit."""

import contextlib
import io
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docx_review  # noqa: E402
import file_digest  # noqa: E402

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def workbook(path):
    """A workbook of one sheet: a header, three rows of a region and an amount, one formula."""
    rows = ['<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>']
    for number, (region, amount) in enumerate((("East", 10), ("West", 20), ("East", 30)), start=2):
        formula = "<f>B2*2</f>" if number == 4 else ""
        rows.append(f'<row r="{number}"><c r="A{number}" t="inlineStr"><is><t>{region}</t></is></c>'
                    f'<c r="B{number}">{formula}<v>{amount}</v></c></row>')
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", f'<workbook xmlns="{MAIN}" xmlns:r="{REL}"><sheets>'
                         '<sheet name="Sales" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{PKG}">'
                         '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/sharedStrings.xml", f'<sst xmlns="{MAIN}"><si><t>Region</t></si>'
                         '<si><t>Amount</t></si></sst>')
        archive.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{MAIN}"><dimension ref="A1:B4"/>'
                         f'<sheetData>{"".join(rows)}</sheetData></worksheet>')


def deck(path):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ppt/presentation.xml", f'<p:presentation xmlns:p="{P}" xmlns:r="{REL}"><p:sldIdLst>'
                         '<p:sldId id="257" r:id="rId3"/><p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
                         '</p:presentation>')
        archive.writestr("ppt/_rels/presentation.xml.rels", f'<Relationships xmlns="{PKG}">'
                         '<Relationship Id="rId2" Target="slides/slide1.xml"/>'
                         '<Relationship Id="rId3" Target="slides/slide2.xml"/></Relationships>')
        for number, words in ((1, "Second in order"), (2, "Launch plan")):
            archive.writestr(f"ppt/slides/slide{number}.xml",
                             f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><a:t>{words}</a:t></p:sld>')


class DigestTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)

    def write(self, name, data):
        path = self.dir / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def test_a_word_document_gives_its_headings_text_and_open_comments(self):
        path = self.dir / "paper.docx"
        docx_review.sample(path)
        text = file_digest.digest(path)["text"]
        self.assertTrue(text.startswith("document, "))
        self.assertIn("3 open comments", text)
        self.assertIn("# ", text)

    def test_a_workbook_gives_each_column_its_numbers_or_its_values(self):
        path = self.dir / "sales.xlsx"
        workbook(path)
        found = file_digest.digest(path)
        self.assertEqual(found["kind"], "spreadsheet")
        self.assertIn("sheet Sales: A1:B4, 1 formulas", found["text"])
        self.assertIn("header: Region | Amount", found["text"])
        self.assertIn("- Amount: 3 numbers, min 10, max 30, mean 20, sum 60", found["text"])
        self.assertIn("- Region: 3 values, 2 distinct: East, West", found["text"])

    def test_a_csv_is_summed_as_a_sheet_is(self):
        path = self.write("ledger.csv", "date;debit;memo\n2026-01-01;1,200.50;rent\n2026-02-01;$300;ads\n")
        text = file_digest.digest(path)["text"]
        self.assertIn("table, ", text)
        self.assertIn("- debit: 2 numbers, min 300, max 1200, mean 750.2, sum 1500", text)

    def test_slides_come_in_the_decks_order(self):
        path = self.dir / "pitch.pptx"
        deck(path)
        text = file_digest.digest(path)["text"]
        self.assertIn("2 slides\n1. Launch plan\n2. Second in order", text)

    def test_code_text_and_a_notebook(self):
        code = file_digest.digest(self.write("model.py", "class A:\n    def f(self):\n        pass\n"))["text"]
        self.assertIn("Python, 3 lines, 2 functions or classes", code)
        note = {"metadata": {"kernelspec": {"language": "python"}},
                "cells": [{"cell_type": "markdown", "source": ["# Churn study"]}, {"cell_type": "code", "source": []}]}
        self.assertIn("python, 1 code cells, 1 markdown cells\n# Churn study",
                      file_digest.digest(self.write("churn.ipynb", json.dumps(note)))["text"])
        self.assertIn("3 lines, 6 words", file_digest.digest(self.write("notes.md", "a b\nc d\ne f\n"))["text"])

    def test_a_pdf_and_images_give_their_size(self):
        pdf = b"%PDF-1.4 /Type /Pages /Title (Annual report) /Type /Page /Type /Page"
        self.assertIn("2 pages, title Annual report", file_digest.digest(self.write("r.pdf", pdf))["text"])
        png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 640, 480) + b"\0" * 8
        self.assertIn("PNG, 640 x 480 pixels", file_digest.digest(self.write("logo.png", png))["text"])
        jpeg = b"\xff\xd8\xff\xc0\x00\x11\x08" + struct.pack(">HH", 300, 400) + b"\0" * 20
        self.assertIn("JPEG, 400 x 300 pixels", file_digest.digest(self.write("p.jpg", jpeg))["text"])
        svg = '<svg viewBox="0 0 120 80"></svg>'
        self.assertIn("SVG, 120 x 80 pixels", file_digest.digest(self.write("art.svg", svg))["text"])

    def test_the_kind_comes_from_the_name_or_a_google_type(self):
        self.assertEqual(file_digest.kind_of("Budget.XLSX"), "spreadsheet")
        self.assertEqual(file_digest.kind_of("cover.psd"), "art")
        self.assertEqual(file_digest.kind_of("Plan", "application/vnd.google-apps.document"), "document")
        self.assertEqual(file_digest.kind_of("README"), "other")

    def test_a_broken_file_is_said_to_be_unreadable(self):
        found = file_digest.digest(self.write("broken.xlsx", b"PK not a zip"))
        self.assertIn("could not be read (BadZipFile)", found["text"])
        self.assertIn("could not be read", file_digest.digest(self.write("bad.ipynb", "{"))["text"])

    def test_a_digest_is_never_longer_than_its_limit(self):
        long = "\n".join("word " * 40 for _ in range(400))
        self.assertLessEqual(len(file_digest.digest(self.write("long.txt", long))["text"]), file_digest.LIMIT)

    def test_a_zip_part_is_read_only_to_its_limit(self):
        path = self.dir / "huge.xlsx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", b"<" + b" " * (file_digest.PART_LIMIT + 10))
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(len(file_digest.part(archive, "xl/workbook.xml")), file_digest.PART_LIMIT)
        self.assertIn("could not be read", file_digest.digest(path)["text"])

    def test_a_code_file_of_blank_lines_is_read_at_once(self):
        import time
        path = self.write("blank.py", "\n" * 400000)
        began = time.monotonic()
        file_digest.digest(path)
        self.assertLess(time.monotonic() - began, 2)

    def test_a_word_part_that_inflates_past_the_limit_is_not_read(self):
        path = self.dir / "bomb.docx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", b" " * (file_digest.PART_LIMIT + 1))
        self.assertIn("could not be read (ValueError)", file_digest.digest(path)["text"])

    def test_the_command_line_prints_each_file(self):
        path = self.write("a.csv", "x\n1\n")
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(file_digest.main([str(path)]), 0)
            self.assertEqual(file_digest.main([str(self.dir / "missing.csv")]), 1)
        self.assertIn("- x: 1 numbers", out.getvalue())


if __name__ == "__main__":
    unittest.main()
