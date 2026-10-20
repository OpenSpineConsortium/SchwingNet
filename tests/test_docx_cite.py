"""tools/docx_cite.py: citations written into a copy of a Word document as
tracked insertions, as Word's own CITATION fields with the references in the
document's source list, or as Zotero fields naming each item's library URI.
Every name here is made up."""

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docx_cite  # noqa: E402
import docx_review as dr  # noqa: E402

REFS = [
    {"key": "smith2020", "title": "A Fast Matching", "authors": ["Smith, Ann", "Lee, Bo"], "year": "2020",
     "doi": "10.1000/abc", "venue": "J. Graphs", "url": "https://example.test/smith",
     "uri": "http://zotero.org/users/42/items/ABCD1234"},
    {"key": "jones2019", "title": "Readers Agree", "authors": ["Jones, C", "Kim, D", "Roe, E"], "year": "2019",
     "doi": "", "venue": "", "url": "", "uri": ""},
]


class Cite(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.paper = self.folder / "paper.docx"
        dr.sample(self.paper)
        self.out = self.folder / "cited.docx"

    def document(self):
        with zipfile.ZipFile(self.out) as archive:
            return {name: archive.read(name) for name in archive.namelist()}

    def test_word_citations_are_tracked_fields_with_sources(self):
        report = docx_cite.cite(self.paper, REFS, [
            {"paragraph": 1, "after": "most of the time", "refs": ["smith2020", "jones2019"]},
            {"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}], self.out, "word")
        self.assertEqual((report["citations"], report["references"]), (2, 2))
        parts = self.document()
        root = ET.fromstring(parts[dr.DOCUMENT])
        paragraph = dr.paragraphs(root)[1]
        self.assertEqual(dr.paragraph_text(paragraph, "rejected"), dr.paragraph_text(
            dr.paragraphs(ET.fromstring(zipfile.ZipFile(self.paper).read(dr.DOCUMENT)))[1]))
        self.assertIn("most of the time (Smith and Lee, 2020; Jones et al., 2019).",
                      dr.paragraph_text(paragraph))
        codes = [e.text for e in root.iter(dr.W + "instrText")]
        self.assertEqual(codes[0], " CITATION smith2020 \\l 1033 \\m jones2019 ")
        inserted = root.findall(f".//{dr.W}ins")
        self.assertEqual({e.get(dr.W + "author") for e in inserted}, {"Claude"})
        sources = ET.fromstring(parts["customXml/item1.xml"])
        tags = [e.text for e in sources.iter(docx_cite.B + "Tag")]
        self.assertEqual(tags, ["smith2020", "jones2019"])
        self.assertEqual([e.text for e in sources.iter(docx_cite.B + "DOI")], ["10.1000/abc"])
        self.assertIn(b"customXml/item1.xml", parts[docx_cite.DOCUMENT_RELS])
        self.assertIn(b"itemProps1.xml", parts[docx_cite.CONTENT_TYPES])

    def test_a_second_pass_adds_to_the_same_source_list(self):
        docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}],
                       self.out, "word")
        again = self.folder / "again.docx"
        docx_cite.cite(self.out, REFS, [{"paragraph": 2, "after": "next section", "refs": ["smith2020", "jones2019"]}],
                       again, "word")
        with zipfile.ZipFile(again) as archive:
            names = archive.namelist()
            sources = ET.fromstring(archive.read("customXml/item1.xml"))
        self.assertNotIn("customXml/item2.xml", names)
        self.assertEqual([e.text for e in sources.iter(docx_cite.B + "Tag")], ["smith2020", "jones2019"])

    def test_zotero_fields_name_the_library_item(self):
        docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}],
                       self.out, "zotero")
        root = ET.fromstring(self.document()[dr.DOCUMENT])
        [code] = [e.text for e in root.iter(dr.W + "instrText")]
        self.assertTrue(code.startswith(" ADDIN ZOTERO_ITEM CSL_CITATION {"))
        data = json.loads(code.split("CSL_CITATION", 1)[1])
        self.assertEqual(data["citationItems"][0]["uris"], ["http://zotero.org/users/42/items/ABCD1234"])
        self.assertEqual(data["citationItems"][0]["itemData"]["DOI"], "10.1000/abc")

    def test_zotero_needs_a_uri(self):
        with self.assertRaises(docx_cite.Refused):
            docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["jones2019"]}],
                           self.out, "zotero")

    def test_refusals(self):
        for citation in ({"paragraph": 9, "after": "x", "refs": ["smith2020"]},
                         {"paragraph": 1, "after": "absent words", "refs": ["smith2020"]},
                         {"paragraph": 1, "after": "most of the time", "refs": ["nobody"]},
                         {"paragraph": 1, "after": "the", "refs": ["smith2020"]}):
            with self.assertRaises(docx_cite.Refused):
                docx_cite.cite(self.paper, REFS, [citation], self.out, "word")
        with self.assertRaises(docx_cite.Refused):
            docx_cite.cite(self.paper, REFS, [], self.paper, "word")

    def test_a_cited_paragraph_is_not_cited_again_blindly(self):
        docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}],
                       self.out, "word")
        with self.assertRaises(docx_cite.Refused):
            docx_cite.cite(self.out, REFS, [{"paragraph": 3, "after": "Results", "refs": ["smith2020"]}],
                           self.folder / "x.docx", "word")

    def test_two_citations_in_one_paragraph_in_one_pass(self):
        docx_cite.cite(self.paper, REFS, [
            {"paragraph": 2, "after": "next section", "refs": ["smith2020"]},
            {"paragraph": 2, "after": "very novel", "refs": ["jones2019"]}], self.out, "word")
        paragraph = dr.paragraphs(ET.fromstring(self.document()[dr.DOCUMENT]))[2]
        self.assertEqual(dr.paragraph_text(paragraph), "The method is described in the next section "
                         "(Smith and Lee, 2020), and it is very novel (Jones et al., 2019).")
        with self.assertRaises(docx_cite.Refused):
            docx_cite.cite(self.paper, REFS, [{"paragraph": 2, "after": "next section", "refs": ["smith2020"]},
                                              {"paragraph": 2, "after": "the next section", "refs": ["smith2020"]}],
                           self.folder / "x.docx", "word")

    def test_the_space_is_outside_the_field(self):
        docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}],
                       self.out, "word")
        root = ET.fromstring(self.document()[dr.DOCUMENT])
        runs = list(root.iter(dr.W + "ins"))[0]
        texts = [e.text for e in runs.iter(dr.W + "t")]
        self.assertEqual(texts, [" ", "(Smith and Lee, 2020)"])

    def test_zotero_citation_ids_differ_between_passes(self):
        docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}],
                       self.out, "zotero")
        again = self.folder / "again.docx"
        docx_cite.cite(self.out, REFS, [{"paragraph": 2, "after": "next section", "refs": ["smith2020"]}],
                       again, "zotero")
        with zipfile.ZipFile(again) as archive:
            root = ET.fromstring(archive.read(dr.DOCUMENT))
        ids = [json.loads(e.text.split("CSL_CITATION", 1)[1])["citationID"] for e in root.iter(dr.W + "instrText")]
        self.assertEqual(len(set(ids)), 2)

    def test_names_written_first_name_first(self):
        reference = dict(REFS[0], authors=["Ann Smith", "Bo Lee"])
        self.assertEqual(docx_cite.label(reference), "Smith and Lee, 2020")
        self.assertEqual(docx_cite.person("Ann Smith"), {"family": "Smith", "given": "Ann"})

    def test_a_different_work_under_a_taken_tag_is_refused(self):
        docx_cite.cite(self.paper, REFS, [{"paragraph": 3, "after": "Table 1", "refs": ["smith2020"]}],
                       self.out, "word")
        other = [dict(REFS[0], title="Another Work")]
        with self.assertRaises(docx_cite.Refused):
            docx_cite.cite(self.out, other, [{"paragraph": 2, "after": "next section", "refs": ["smith2020"]}],
                           self.folder / "x.docx", "word")


class Splitting(unittest.TestCase):
    def paragraph(self, inner):
        return ET.fromstring(f'<w:p xmlns:w="{dr.W_URI}">{inner}</w:p>')

    def test_a_run_ending_in_a_tab_keeps_the_tab_before_the_citation_only_when_cited_after_it(self):
        p = self.paragraph('<w:r><w:t>Results</w:t><w:tab/></w:r><w:r><w:t>next</w:t></w:r>')
        position, _ = docx_cite.split_at(p, len("Results"))
        p.insert(position, ET.Element(dr.W + "r"))
        self.assertEqual([len(r) for r in p], [1, 0, 1, 1])
        q = self.paragraph('<w:r><w:t>Results</w:t><w:tab/></w:r><w:r><w:t>next</w:t></w:r>')
        position, _ = docx_cite.split_at(q, len("Results\t"))
        self.assertEqual(position, 1)


if __name__ == "__main__":
    unittest.main()
