"""Notebooks: groups of a drive's files that Claude works on where they are.

A notebook is what Gemini's NotebookLM calls one: a handful of files put
together as one context, a paper with its data and its sources, say, that a
session reads as a whole. Nothing in the drive moves to make one. The
notebook lives in a private repository of its own, which points at its files
by the drive's ids and keeps beside them what Claude makes of them: the
research it gathers, the drafts and derivatives it writes, and the reference
list. Edits go back to the drive's files as tracked changes in a copy
beside each one (the lens-review skill), never over the owner's file
unless the owner says so.

  python3 tools/notebook.py check --notebooks NOTEBOOKS.json --catalog catalog.json
  python3 tools/notebook.py show --notebooks NOTEBOOKS.json --catalog catalog.json
  python3 tools/notebook.py make --notebooks NOTEBOOKS.json --catalog catalog.json --slug SLUG --out DIR
  python3 tools/notebook.py refs --export FILE --out references.json

notebooks.json is the session's proposal, written beside catalog.json on the
branch drive-catalog, where the control panel reads both: a list of notebooks,
each with a slug, a title, a summary, the catalog paths of its files and the
name of its repository, and the paths it left out. A file may sit in several
notebooks, since none of them moves it. check holds the proposal to the
catalog, show prints each notebook's counts, and make writes the files a
notebook's repository starts with: notebook.json, every item with its drive
id, item id and link; NOTEBOOK.md, the same as a page to read; and the
folders research/ and drafts/. refs reads a citation manager's export, BibTeX
(.bib) or RIS (.ris), which Mendeley, EndNote and Zotero all write, into
references.json, so a notebook takes its references with no connector, key
or account of its own.

A notebook names a person's files: its repository is private, and a proposal
lives only on a private repository's branch drive-catalog. Standard library
only.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
MAX_NOTEBOOKS = 30
ITEM_FIELDS = ("path", "name", "kind", "size", "modified", "web", "drive", "id")


class NotebookError(Exception):
    """A step that cannot go on, said in one line."""


# The proposal

def files_by_path(made):
    files = made.get("files") if isinstance(made, dict) else None
    if not isinstance(files, list):
        raise NotebookError("the catalog holds no list of files")
    return {entry["path"]: entry for entry in files if isinstance(entry, dict) and isinstance(entry.get("path"), str)}


def problems_of(proposal, made):
    """Each way the proposal does not hold together with the catalog."""
    known = files_by_path(made)
    if not isinstance(proposal, dict):
        return ["the proposal is not an object"]
    notebooks = proposal.get("notebooks")
    if not isinstance(notebooks, list) or not notebooks:
        return ["notebooks is not a list of at least one notebook"]
    if len(notebooks) > MAX_NOTEBOOKS:
        return [f"{len(notebooks)} notebooks, more than {MAX_NOTEBOOKS}"]
    problems, slugs = [], set()
    for number, notebook in enumerate(notebooks, 1):
        problems += notebook_problems(number, notebook, known, slugs)
    left_out = proposal.get("left_out", [])
    if not isinstance(left_out, list) or not all(isinstance(path, str) for path in left_out):
        return problems + ["left_out is not a list of paths"]
    for path in left_out:
        if path not in known:
            problems.append(f"left_out names {path!r}, which the catalog does not list")
    return problems


def notebook_problems(number, notebook, known, slugs):
    where = f"notebook {number}"
    if not isinstance(notebook, dict):
        return [f"{where} is not an object"]
    slug = notebook.get("slug")
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        return [f"{where}'s slug is not lowercase letters, digits and dashes"]
    where = f"notebook {slug}"
    problems = []
    if slug in slugs:
        problems.append(f"{where} is named twice")
    slugs.add(slug)
    for field in ("title", "summary"):
        if not isinstance(notebook.get(field), str) or not notebook[field].strip():
            problems.append(f"{where} has no {field}")
    if not isinstance(notebook.get("repository"), str) or not REPO.fullmatch(notebook["repository"]):
        problems.append(f"{where}'s repository is not a repository name")
    files = notebook.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(path, str) for path in files):
        return problems + [f"{where} holds no list of file paths"]
    for path in files:
        if path not in known:
            problems.append(f"{where} names {path!r}, which the catalog does not list")
    if len(set(files)) != len(files):
        problems.append(f"{where} names a file twice")
    return problems


def checked(proposal, made):
    problems = problems_of(proposal, made)
    if problems:
        raise NotebookError("; ".join(problems))
    return proposal


def summary_of(notebook, known):
    """What a notebook's card shows: its counts, never its file names."""
    items = [known[path] for path in notebook["files"]]
    dates = sorted(item.get("modified") or "" for item in items)
    return {
        "slug": notebook["slug"],
        "title": notebook["title"],
        "repository": notebook["repository"],
        "files": len(items),
        "bytes": sum(int(item.get("size") or 0) for item in items),
        "kinds": dict(Counter(item.get("kind") or "other" for item in items).most_common()),
        "latest": dates[-1] or None,
    }


# A notebook's repository

def items_of(notebook, known):
    return [{field: known[path].get(field) for field in ITEM_FIELDS} for path in notebook["files"]]


def notebook_record(notebook, known):
    return {
        "slug": notebook["slug"],
        "title": notebook["title"],
        "summary": notebook["summary"],
        "items": items_of(notebook, known),
    }


def plain(text):
    """One line of Markdown text from a name someone else wrote."""
    text = " ".join(str(text).split())
    text = re.sub(r"([\\`*_\[\]<>|#~!()])", r"\\\1", text)
    return re.sub(r"^([-+=]|\d+\.)", r"\\\1", text)


def link(url):
    """A drive link as Markdown takes it, or nothing for one that is not https."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    return re.sub(r"[\s<>|()]", lambda match: "%{:02X}".format(ord(match.group())), url)


def notebook_markdown(record):
    lines = [f"# {plain(record['title'])}", "", plain(record["summary"]), "",
             "The files below stay where they are on the drive; this repository points at them.", "",
             "| File | Kind | Modified |", "| --- | --- | --- |"]
    for item in record["items"]:
        name = plain(item["name"] or item["path"])
        url = link(item.get("web"))
        shown = f"[{name}]({url})" if url else name
        lines.append(f"| {shown} | {item.get('kind') or ''} | {(item.get('modified') or '')[:10]} |")
    lines += ["", "research/ holds what Claude finds out, drafts/ what it writes, references.json the references."]
    return "\n".join(lines) + "\n"


def make(proposal, made, slug, out):
    known = files_by_path(made)
    notebook = next((each for each in proposal["notebooks"] if each["slug"] == slug), None)
    if notebook is None:
        raise NotebookError(f"no notebook {slug!r} in the proposal")
    record = notebook_record(notebook, known)
    out = Path(out)
    if (out / "tools" / "notebook.py").exists():
        raise NotebookError(f"{out} is a copy of this template, where no file name may go; give the notebook's own clone")
    for folder in ("research", "drafts"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    (out / "notebook.json").write_text(json.dumps(record, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    (out / "NOTEBOOK.md").write_text(notebook_markdown(record), encoding="utf-8")
    (out / "research" / "README.md").write_text("# Research\n\nOne file per question, each opening with its sources.\n", encoding="utf-8")
    (out / "drafts" / "README.md").write_text("# Drafts\n\nWhat Claude writes from the notebook's files, one file each.\n", encoding="utf-8")
    return record


# References

BIB_START = re.compile(r"@(\w+)\s*([{(])")
BIB_NAME = re.compile(r"\s*(\w[\w-]*)\s*=\s*")
RIS_LINE = re.compile(r"^([A-Z][A-Z0-9])  - ?(.*)$")
ACCENT = re.compile(r"\{?\\[\"'`^~=.]\{?(\w)\}?\}?")


def closing(text, start, opener):
    """Where the bracket opened just before start closes, braces counted
    inside it, or the text's end where it never closes."""
    depth = 0
    for at in range(start, len(text)):
        char = text[at]
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0 and opener == "{":
                return at
            depth = max(depth - 1, 0)
        elif char == ")" and depth == 0 and opener == "(":
            return at
    return len(text)


def bib_value(body, at):
    """One field's value starting at body[at], and where it ends."""
    if at < len(body) and body[at] == "{":
        end = closing(body, at + 1, "{")
        return body[at + 1:end], end + 1
    if at < len(body) and body[at] == '"':
        end = body.find('"', at + 1)
        end = len(body) if end < 0 else end
        return body[at + 1:end], end + 1
    match = re.match(r"[^,]*", body[at:])
    return match.group(), at + match.end()


def bib_fields(body):
    fields, at = {}, 0
    while True:
        match = BIB_NAME.match(body, at)
        if not match:
            comma = body.find(",", at)
            if comma < 0:
                return fields
            at = comma + 1
            continue
        value, at = bib_value(body, match.end())
        fields[match.group(1).lower()] = unbraced(value)
        comma = body.find(",", at)
        if comma < 0:
            return fields
        at = comma + 1


def unbraced(value):
    value = ACCENT.sub(r"\1", value)
    return " ".join(value.replace("{", "").replace("}", "").split())


def bibtex(text):
    references, at = [], 0
    while match := BIB_START.search(text, at):
        end = closing(text, match.end(), match.group(2))
        at = end + 1
        if match.group(1).lower() in ("comment", "string", "preamble"):
            continue
        key, _, body = text[match.end():end].partition(",")
        fields = bib_fields(body)
        authors = [" ".join(name.split()) for name in fields.get("author", "").split(" and ") if name.strip()]
        references.append(reference(key.strip(), fields.get("title"), authors, fields.get("year"), fields.get("doi"),
                                    fields.get("journal") or fields.get("booktitle"), fields.get("url")))
    return references


def ris(text):
    references, entry = [], None
    for line in text.splitlines():
        match = RIS_LINE.match(line.rstrip())
        if not match:
            continue
        tag, value = match.groups()
        if tag == "TY":
            entry = {"authors": []}
        elif entry is None:
            continue
        elif tag == "ER":
            references.append(reference(entry.get("ID"), entry.get("TI"), entry["authors"], entry.get("PY"),
                                        entry.get("DO"), entry.get("JO"), entry.get("UR")))
            entry = None
        elif tag in ("AU", "A1"):
            entry["authors"].append(value.strip())
        else:
            entry.setdefault({"T1": "TI", "Y1": "PY", "T2": "JO", "JF": "JO"}.get(tag, tag), value.strip())
    return references


def reference(key, title, authors, year, doi, venue, url=None, uri=""):
    """One reference: url is where it was found, uri the item in a Zotero
    library, so a citation written from it names its own source."""
    year = re.search(r"\d{4}", year or "")
    return {"key": key or "", "title": title or "", "authors": authors, "year": year.group() if year else "",
            "doi": (doi or "").strip().lower(), "venue": venue or "", "url": (url or "").strip(), "uri": uri}


def zotero(items, library):
    """References from a Zotero web API answer (GET /users/<id>/items, the
    default JSON), each with the item's URI in the library, which a Zotero
    field in Word names: library is users/<id> or groups/<id>."""
    if not re.fullmatch(r"(users|groups)/\d{1,12}", library or ""):
        raise NotebookError("the Zotero library is users/<id> or groups/<id>")
    if not isinstance(items, list):
        raise NotebookError("the Zotero answer is not a list of items")
    found = []
    for item in items:
        data = item.get("data") if isinstance(item, dict) else None
        if not isinstance(data, dict) or data.get("itemType") in ("attachment", "note", "annotation", None):
            continue
        authors = [creator_name(each) for each in data.get("creators", [])
                   if isinstance(each, dict) and each.get("creatorType", "author") == "author"]
        doi = data.get("DOI") or extra_doi(data.get("extra"))
        venue = data.get("publicationTitle") or data.get("bookTitle") or data.get("proceedingsTitle")
        found.append(reference(data.get("key"), data.get("title"), [a for a in authors if a], data.get("date"),
                               doi, venue or data.get("conferenceName"),
                               data.get("url"), f"http://zotero.org/{library}/items/{data.get('key')}"))
    return found


def extra_doi(extra):
    """A DOI Zotero keeps in Extra for an item type with no DOI field."""
    match = re.search(r"^DOI:\s*(\S+)", str(extra or ""), re.M | re.I)
    return match.group(1) if match else ""


def creator_name(creator):
    if creator.get("name"):
        return str(creator["name"])
    return ", ".join(str(part) for part in (creator.get("lastName"), creator.get("firstName")) if part)


def read_references(path):
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    found = ris(text) if re.search(r"^TY  - ", text, re.M) else bibtex(text)
    if text.strip() and not found:
        raise NotebookError(f"{path} holds no BibTeX or RIS reference")
    for number, entry in enumerate(found, 1):
        entry["key"] = entry["key"] or f"ref{number}"
    return found


# The command line

def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise NotebookError(f"{path} could not be read as JSON: {error}") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "show", "make"):
        command = commands.add_parser(name)
        command.add_argument("--notebooks", required=True)
        command.add_argument("--catalog", required=True)
        if name == "make":
            command.add_argument("--slug", required=True)
            command.add_argument("--out", required=True)
    refs = commands.add_parser("refs")
    source = refs.add_mutually_exclusive_group(required=True)
    source.add_argument("--export", help="a BibTeX or RIS file")
    source.add_argument("--zotero", help="a Zotero web API answer, saved as JSON")
    refs.add_argument("--library", help="users/<id> or groups/<id>, with --zotero")
    refs.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(run(args), indent=1))
    except NotebookError as error:
        print(f"notebook: {error}", file=sys.stderr)
        return 1
    return 0


def run(args):
    if args.command == "refs":
        found = zotero(load(args.zotero), args.library) if args.zotero else read_references(args.export)
        Path(args.out).write_text(json.dumps(found, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
        return {"references": len(found), "with_doi": sum(1 for each in found if each["doi"])}
    made = load(args.catalog)
    proposal = checked(load(args.notebooks), made)
    known = files_by_path(made)
    if args.command == "check":
        return {"notebooks": len(proposal["notebooks"]), "problems": 0}
    if args.command == "show":
        return [summary_of(notebook, known) for notebook in proposal["notebooks"]]
    record = make(proposal, made, args.slug, args.out)
    return {"slug": record["slug"], "items": len(record["items"]), "out": args.out}


if __name__ == "__main__":
    sys.exit(main())
