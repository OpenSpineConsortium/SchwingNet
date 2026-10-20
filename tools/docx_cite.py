"""Citations written into a Word document as tracked changes, in the forms
Word and Zotero read, each naming where its reference came from.

Claude cites from a notebook's references.json (tools/notebook.py refs):
each reference keeps its DOI, the address it was found at and, for one read
from a Zotero library, the item's URI there. A file of citations,

  [{"paragraph": 4, "after": "as shown before", "refs": ["smith2020"]}]

puts each citation straight after the words "after" names in that
paragraph, which must occur there once. Two forms are written:

  word    Word's own citations: a CITATION field per citation and the
          reference in the document's source list (References, Manage
          Sources), with its DOI and address, so Insert Bibliography and
          Update Field work in any copy of Word with no add-in.
  zotero  Zotero's field, ADDIN ZOTERO_ITEM CSL_CITATION, whose data names
          the item's URI in the owner's library, so Zotero's Refresh in Word
          takes it as a citation of its own; every reference must have a uri.

Each citation goes in as a tracked insertion under the author's name, so the
owner accepts or rejects it in Word, and the result is written to a copy
(--out), never over the document read.

  python3 tools/docx_cite.py FILE.docx --refs references.json --cite CITES.json --out OUT.docx [--form word|zotero]

Standard library only, with tools/docx_review.py's reading and writing.
"""

import argparse
import datetime
import hashlib
import io
import json
import re
import sys
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))

import docx_review as dr  # noqa: E402

W = dr.W
B_URI = "http://schemas.openxmlformats.org/officeDocument/2006/bibliography"
B = "{%s}" % B_URI
DS_URI = "http://schemas.openxmlformats.org/officeDocument/2006/customXml"
REL_URI = "http://schemas.openxmlformats.org/package/2006/relationships"
CUSTOM_XML_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml"
PROPS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXmlProps"
PROPS_TYPE = "application/vnd.openxmlformats-officedocument.customXmlProperties+xml"
DOCUMENT_RELS = "word/_rels/document.xml.rels"
CONTENT_TYPES = "[Content_Types].xml"
CSL_SCHEMA = "https://github.com/citation-style-language/schema/raw/master/csl-citation.json"
TAG = re.compile(r"[A-Za-z0-9_:.-]{1,255}")
FORMS = ("word", "zotero")


class Refused(Exception):
    """A citation that cannot be written, said in one line."""


# What a citation shows

def short_name(reference):
    first = (reference.get("authors") or [""])[0]
    if first:
        return name_parts(first)[0]
    return reference.get("title", "")[:30] or reference["key"]


def label(reference):
    names = reference.get("authors") or []
    name = short_name(reference) + (" et al." if len(names) > 2 else "")
    if len(names) == 2:
        name += " and " + name_parts(names[1])[0]
    return f"{name}, {reference.get('year') or 'n.d.'}"


def shown_text(references):
    return "(" + "; ".join(label(each) for each in references) + ")"


# The two forms of the field's code

def word_code(references):
    tags = [word_tag(each) for each in references]
    return " CITATION " + tags[0] + " \\l 1033 " + "".join(f"\\m {tag} " for tag in tags[1:])


def word_tag(reference):
    key = reference["key"]
    return key if TAG.fullmatch(key) else "ref" + hashlib.sha256(key.encode()).hexdigest()[:10]


def zotero_code(references, citation_id):
    items = []
    for reference in references:
        if not reference.get("uri"):
            raise Refused(f"reference {reference['key']!r} has no Zotero uri; read it from the library (refs --zotero)")
        items.append({"id": reference["uri"], "uris": [reference["uri"]],
                      "itemData": csl_item(reference["uri"], reference)})
    text = shown_text(references)
    data = {"citationID": citation_id, "properties": {"formattedCitation": text, "plainCitation": text,
                                                       "noteIndex": 0},
            "citationItems": items, "schema": CSL_SCHEMA}
    return " ADDIN ZOTERO_ITEM CSL_CITATION " + json.dumps(data, ensure_ascii=True, separators=(",", ":")) + " "


def csl_item(item_id, reference):
    item = {"id": item_id, "type": "article-journal", "title": reference.get("title", "")}
    item["author"] = [person(name) for name in reference.get("authors", [])]
    if reference.get("year"):
        item["issued"] = {"date-parts": [[int(reference["year"])]]}
    for field, csl in (("doi", "DOI"), ("url", "URL"), ("venue", "container-title")):
        if reference.get(field):
            item[csl] = reference[field]
    return item


def name_parts(name):
    """Family and given name from "Last, First" or "First Last"."""
    name = " ".join(str(name).split())
    if "," in name:
        family, _, given = name.partition(",")
        return family.strip(), given.strip()
    given, _, family = name.rpartition(" ")
    return (family, given) if given else (name, "")


def person(name):
    family, given = name_parts(name)
    return {"family": family, "given": given} if given else {"literal": family}


# The field in the paragraph

def field_runs(code, text, rpr):
    """A space, then the runs of one complex field: begin, its code,
    separate, what it shows, end. The space stays outside the field, since
    Word and Zotero replace the field's result with their own."""
    def run(*children):
        element = dr.make_run(rpr)
        for child in children:
            element.append(child)
        return element
    instr = ET.Element(W + "instrText", {dr.XML_SPACE: "preserve"})
    instr.text = code
    shown = ET.Element(W + "t", {dr.XML_SPACE: "preserve"})
    shown.text = text
    space = ET.Element(W + "t", {dr.XML_SPACE: "preserve"})
    space.text = " "
    return [run(space), run(ET.Element(W + "fldChar", {W + "fldCharType": "begin"})), run(instr),
            run(ET.Element(W + "fldChar", {W + "fldCharType": "separate"})), run(shown),
            run(ET.Element(W + "fldChar", {W + "fldCharType": "end"}))]


def check_plain(paragraph, index):
    plain = all(child.tag in dr.PLAIN_PARAGRAPH for child in paragraph) and all(
        part.tag in dr.PLAIN_RUN for run in paragraph.iter(W + "r") for part in run)
    if not plain:
        raise Refused(f"paragraph {index} holds a field, a link or a tracked change; cite in it by hand")


def atoms_of(paragraph):
    """Each character the paragraph shows, as (run, element, index in its
    text), a tab counting as one character at index 0 of its w:tab."""
    atoms = []
    for run in paragraph:
        if run.tag != W + "r":
            continue
        for element in run:
            if element.tag == W + "t":
                atoms += [(run, element, at) for at in range(len(element.text or ""))]
            elif element.tag == W + "tab":
                atoms.append((run, element, 0))
    return atoms


def insertion_end(paragraph, after, index):
    """Where in the paragraph's text "after" ends; it must occur there once."""
    text = dr.paragraph_text(paragraph)
    if not after or text.count(after) != 1:
        raise Refused(f"paragraph {index}: the words after which to cite must occur there exactly once")
    return text.index(after) + len(after)


def split_at(paragraph, end):
    """Split the paragraph's runs after its character end - 1 and return
    where in the paragraph a citation goes in."""
    run, element, at = atoms_of(paragraph)[end - 1]
    children = list(run)
    after_element = children[children.index(element) + 1:]
    tail = dr.make_run(run.find(W + "rPr"))
    if element.tag == W + "t" and at + 1 < len(element.text or ""):
        rest = ET.SubElement(tail, W + "t", {dr.XML_SPACE: "preserve"})
        rest.text = element.text[at + 1:]
        element.text = element.text[:at + 1]
        element.set(dr.XML_SPACE, "preserve")
    for child in after_element:
        if child.tag != W + "rPr":
            run.remove(child)
            tail.append(child)
    position = list(paragraph).index(run) + 1
    if len([child for child in tail if child.tag != W + "rPr"]):
        paragraph.insert(position, tail)
    return position, run.find(W + "rPr")


# Word's source list

def sources_part(parts):
    """The name of the customXml part holding b:Sources, or None."""
    for name, data in parts.items():
        if re.fullmatch(r"customXml/item\d+\.xml", name) and dr.parse(data).tag == B + "Sources":
            return name
    return None


def source_element(reference):
    source = ET.Element(B + "Source")
    def put(tag, value):
        if value:
            ET.SubElement(source, B + tag).text = str(value)
    put("Tag", word_tag(reference))
    put("SourceType", "JournalArticle" if reference.get("venue") else "Misc")
    put("Guid", "{" + str(uuid_of(reference["key"])).upper() + "}")
    names = reference.get("authors") or []
    if names:
        name_list = ET.SubElement(ET.SubElement(ET.SubElement(source, B + "Author"), B + "Author"), B + "NameList")
        for name in names:
            family, given = name_parts(name)
            one = ET.SubElement(name_list, B + "Person")
            ET.SubElement(one, B + "Last").text = family
            if given:
                ET.SubElement(one, B + "First").text = given
    put("Title", reference.get("title"))
    put("JournalName", reference.get("venue"))
    put("Year", reference.get("year"))
    put("DOI", reference.get("doi"))
    put("URL", reference.get("url") or (f"https://doi.org/{reference['doi']}" if reference.get("doi") else ""))
    return source


def uuid_of(text):
    return uuid.uuid5(uuid.NAMESPACE_URL, "symphony-citation:" + text)


def add_sources(parts, references):
    name = sources_part(parts)
    if name is None:
        name = new_sources_part(parts)
    root = dr.parse(parts[name])
    have = {}
    for source in root.iter(B + "Source"):
        have[source.findtext(B + "Tag")] = source.findtext(B + "Title") or ""
    for reference in references:
        tag = word_tag(reference)
        if tag in have and have[tag] != (reference.get("title") or ""):
            raise Refused(f"the document's source list already has a different work tagged {tag!r}")
        if tag not in have:
            root.append(source_element(reference))
            have[tag] = reference.get("title") or ""
    ET.register_namespace("b", B_URI)
    body = ET.tostring(root, encoding="unicode")
    parts[name] = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body).encode("utf-8")


def new_sources_part(parts):
    number = 1
    while any(name in parts for name in (f"customXml/item{number}.xml", f"customXml/itemProps{number}.xml",
                                         f"customXml/_rels/item{number}.xml.rels")):
        number += 1
    item, props = f"customXml/item{number}.xml", f"customXml/itemProps{number}.xml"
    parts[item] = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   f'<b:Sources xmlns:b="{B_URI}" SelectedStyle="\\APASixthEditionOfficeOnline.xsl" '
                   f'StyleName="APA" Version="6"></b:Sources>').encode()
    guid = "{" + str(uuid_of(item)).upper() + "}"
    parts[props] = (f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
                    f'<ds:datastoreItem ds:itemID="{guid}" xmlns:ds="{DS_URI}"><ds:schemaRefs>'
                    f'<ds:schemaRef ds:uri="{B_URI}"/></ds:schemaRefs></ds:datastoreItem>').encode()
    parts[f"customXml/_rels/item{number}.xml.rels"] = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{REL_URI}">'
        f'<Relationship Id="rId1" Type="{PROPS_REL}" Target="itemProps{number}.xml"/></Relationships>').encode()
    add_relationship(parts, f"../{item}")
    add_override(parts, "/" + props, PROPS_TYPE)
    return item


def add_relationship(parts, target):
    rels = parts.get(DOCUMENT_RELS) or (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                        f'<Relationships xmlns="{REL_URI}"></Relationships>').encode()
    text = rels.decode("utf-8")
    taken = set(re.findall(r'Id="([^"]+)"', text))
    number = 1
    while f"rId{number}" in taken:
        number += 1
    entry = f'<Relationship Id="rId{number}" Type="{CUSTOM_XML_REL}" Target="{target}"/>'
    parts[DOCUMENT_RELS] = text.replace("</Relationships>", entry + "</Relationships>", 1).encode("utf-8")


def add_override(parts, name, content_type):
    text = parts[CONTENT_TYPES].decode("utf-8")
    if f'PartName="{name}"' not in text:
        entry = f'<Override PartName="{name}" ContentType="{content_type}"/>'
        text = text.replace("</Types>", entry + "</Types>", 1)
    if 'Extension="xml"' not in text:
        text = text.replace("</Types>", '<Default Extension="xml" ContentType="application/xml"/></Types>', 1)
    parts[CONTENT_TYPES] = text.encode("utf-8")


# The whole pass

def cite(path, references, citations, out, form="word", author="Claude", now=None):
    if form not in FORMS:
        raise Refused(f"the form is one of {', '.join(FORMS)}")
    if not dr.AUTHOR.fullmatch(author):
        raise Refused("the author is one line of up to 60 plain characters")
    if Path(out).resolve() == Path(path).resolve():
        raise Refused("write the citations to a copy, never over the document read")
    by_key = {each["key"]: each for each in references}
    parts = dr.read_parts(path)
    original = parts[dr.DOCUMENT]
    root = dr.parse(original)
    all_paragraphs = dr.paragraphs(root)
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids = dr.IdSource(root)
    planned = []
    for number, citation in enumerate(citations):
        index = citation.get("paragraph") if isinstance(citation, dict) else None
        if not isinstance(index, int) or not 0 <= index < len(all_paragraphs):
            raise Refused(f"citation {number}: paragraph {index} does not exist")
        keys = citation.get("refs") or []
        missing = [key for key in keys if key not in by_key]
        if not keys or missing:
            raise Refused(f"citation {number}: no reference {', '.join(map(repr, missing)) or 'given'} in references.json")
        paragraph = all_paragraphs[index]
        check_plain(paragraph, index)
        end = insertion_end(paragraph, str(citation.get("after") or ""), index)
        planned.append((index, end, [by_key[key] for key in keys]))
    spots = [(index, end) for index, end, _ in planned]
    if len(set(spots)) != len(spots):
        raise Refused("two citations fall at one place; put their references in one citation")
    used = []
    # The last place in each paragraph first, so the earlier places' runs are untouched.
    for index, end, chosen in sorted(planned, key=lambda each: (each[0], each[1]), reverse=True):
        paragraph = all_paragraphs[index]
        code = word_code(chosen) if form == "word" else zotero_code(chosen, uuid.uuid4().hex[:8])
        position, rpr = split_at(paragraph, end)
        inserted = ET.Element(W + "ins", {W + "id": ids.take(), W + "author": author, W + "date": stamp})
        for piece in field_runs(code, shown_text(chosen), rpr):
            inserted.append(piece)
        paragraph.insert(position, inserted)
        used += [each for each in chosen if each not in used]
    used.sort(key=lambda each: [entry["key"] for entry in references].index(each["key"]))
    parts[dr.DOCUMENT] = dr.serialize(root, original)
    if form == "word" and used:
        add_sources(parts, used)
    write_copy(path, parts, out)
    return {"citations": len(citations), "references": len(used), "form": form, "out": str(out)}


def write_copy(source, parts, target):
    """docx_review's writer keeps the source's order; parts added here come last."""
    with zipfile.ZipFile(source) as archive:
        order = [info.filename for info in archive.infolist()]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in order + [name for name in parts if name not in order]:
            archive.writestr(name, parts[name])
    Path(target).write_bytes(buffer.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("docx")
    parser.add_argument("--refs", required=True)
    parser.add_argument("--cite", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--form", default="word", choices=FORMS)
    parser.add_argument("--author", default="Claude")
    args = parser.parse_args(argv)
    try:
        references = json.loads(Path(args.refs).read_text(encoding="utf-8"))
        citations = json.loads(Path(args.cite).read_text(encoding="utf-8"))
        print(json.dumps(cite(args.docx, references, citations, args.out, args.form, args.author), indent=1))
    except (Refused, OSError, ValueError, KeyError) as error:
        print(f"docx_cite: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
