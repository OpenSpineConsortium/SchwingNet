"""The Artifact Textbook as a website: a page for each chapter of the table
of contents and for each artifact, laid out from the synthesis's records of the
artifacts, so the book a reader opens is the book this commit holds (issue
#196).

The plan is the table of contents' JSON (artifacts/_synthesis/work/out/
toc-hand.json); the records are artifacts/_synthesis/inventory.json; an
artifact's place in its cluster comes from work/out/clustering.json and the
figures the record has settled from the concept ledger, work/out/concepts.json.
A chapter's page opens with its narrative under docs/textbook/ once one is
written, and otherwise with the plan's purpose and questions; below it come
the artifacts the chapter reads, each with its record, so a chapter can be
read before a word of it is written. Nothing here is written by a model: the
synthesis's reads write the records (.github/workflows/synthesis.yml), and
this tool only lays them out.

The book is living in three ways. Every build reads the records as they
stand, so an artifact read again shows its new record, and a settled figure
shows its status as the ledger now has it: current, superseded (a record, not
a final value) or open (not to be quoted as current until it is run again).
Every build checks each chapter's narrative against the ledger with the
ledger's own code (artifacts/_synthesis/work/tools/synth_concepts.py), so a
chapter that gives a dataset count another way, or a superseded or open
figure, says so on its page; the one difference is that a figure's anchors
count equally here, where the ledger weighs them by how rare each word is
across every text, which a build without symphony-template's texts cannot
reckon. And every build lists what the book does not hold yet: a folder under
artifacts/ with no record, an artifact changed since its record was read, and
a record no chapter reads, so a new artifact is in view from the first build
after its merge, beside the chapters that read its cluster, and moves into a
chapter once the table of contents places it.

The site is built into the docs site by .github/workflows/docs.yml and
published with it, on Pages that only people who can read the repository
open, and the deploy stops unless GitHub reports the site private; nothing of
it may be copied to a public place before the provisional is filed
(docs/project.md), and a public edition waits for the owner's word. Its pages
hold what the synthesis's records hold, with what the records' own rules leave
out (artifacts/_synthesis/work/tools/redact.py) left out again, and the
owner's account names and a person named by title as well, since the book
names people by role. Each artifact also opens on claude.ai, where the owner
has shared it by its link, and in the repository.

The artifacts' own pages are in the book too (issue #233, the owner's ask of
2026-10-24: the artifacts themselves, interactive, not screenshots). Every
folder under artifacts/ whose export holds a page, index.html, is copied into
the site under artifacts/<folder>/ with its tree, dotfiles and Markdown left
out; the artifact's own page shows it in an iframe above the record, with a
link that opens it full-page, and a figure whose record traces it to such an
artifact gets a button that opens the page beside Explore and Re-run. A Docs
artifact, exported as index.md alone, keeps its links. The iframe is sandboxed
without the site's origin (EXPORT_SANDBOX says what the pages were checked
for), so a page's script cannot reach the site's other pages or storage. The
first version served no copy, since an artifact's own text holds what the
records' privacy pass leaves out and its scripts would run at the site's own
address (PR #197); the owner weighed that against seeing the artifacts as they
are, on a members-only site of the owner's own pages, and chose the pages.

The book's figures live under docs/textbook/figures/<chapter>/, each an image (or an interactive
page of the same name) beside its record, a JSON file that says where it came from: the artifact,
the script, the data, the commit and the run, as far as the record goes (the figure spec of #215).
A chapter places one with an image line and an italic caption line; the site shows the figure there
with its grade and status and a source panel read from its record, with two buttons: Explore, the
links to the method and the data, and Re-run, a prefilled issue that .github/workflows/figure.yml
answers (tools/figure_run.py). The page figures.html lists every figure with how far it is traced.

Every chapter and every figure carries Ask Claude, a prefilled new issue whose body begins "@claude"
and names what the reader is looking at and its record, which .github/workflows/claude.yml answers
for the owner, members and collaborators; and research.html shows the research loop
(.github/workflows/research.yml, issue #220) with the claims register's queue (tools/claims_rank.py
queue), its switch and its cap.

    python3 tools/textbook_site.py OUT [--repo OWNER/NAME] [--sha SHA] [--root PATH]
"""

import argparse
import collections
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import living_docs  # noqa: E402
import claims_rank  # noqa: E402

SYNTHESIS = Path("artifacts/_synthesis")
BOOK = Path("docs/textbook")
WORK = SYNTHESIS / "work" / "out"
LEDGER_TOOLS = SYNTHESIS / "work" / "tools"
ST_TREE = "https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/"
MARKER = ".textbook"
FIGURES = BOOK / "figures"
DEFAULT_REPO = "OpenSpineConsortium/SchwingNet"
RERUN_LINE = "figure-rerun-id"
FIGURE_IMAGE = re.compile(r"^!\[([^\]]+)\]\((figures/(\d\d)/([a-z0-9-]+)\.(?:png|svg))\)$")
FIGURE_CAPTION = re.compile(r"^\*Figure (\d+\.\d+)\. (.*)\*$")
SCRIPT_NAME = re.compile(r"\.(py|sh|sbatch|tex|js)\b")
# A record whose script made the numbers, the statistics or the matrix, while the artifact's own page
# drew the figure, or whose file is a table set by hand, is traced to its data, not to what drew it.
NOT_THE_DRAWING = re.compile(r"\(the (numbers|statistics|matrix)\)|a hand table|drawn by the (card|artifact)", re.I)

LABELS = {
    "confidential-method": "Results may be shown, mechanism may not, until the provisional is filed; this chapter stays in this private repository.",
    "schwingnet-internal": "SchwingNet's own work, results and rules; mechanism is left to Part III.",
    "outreach": "Outreach and funding, with people named by role only.",
    "symphony-beethoven-separable": "Symphony and Beethoven alone, so this part can be split out of the book.",
}
VALUE_STATUS = {
    "current": "current",
    "superseded": "superseded: not a final value",
    "open": "open: not settled",
}
VERDICTS = {
    "confirmed-contradiction": "the two artifacts disagree",
    "updated-later": "a later artifact revised it",
    "cannot-tell": "the record cannot tell which holds",
    "same-number-restated": "the same figure, restated",
}
OUTCOMES = {
    "agrees": "agrees with the ledger",
    "rounded": "gives the ledger's figure rounded",
    "differs": "differs from the ledger's figure",
    "superseded": "gives a superseded value",
    "open": "gives a value the record has not settled",
}
DISCLAIMER = re.compile(r"not a final value|not settled|has not settled|open in the record|superseded", re.I)
# A record's fields that name things rather than say them, left as they are by the privacy pass:
# they are matched against other records, folders and links.
NAMING_FIELDS = {"repo", "folder", "link", "link_id", "account", "date", "kind", "genre", "confidentiality"}
TITLED_PERSON = re.compile(r"\bDr\.?\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?")
ACCOUNT_SHAPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{3,38}")
# The sandbox of an exported artifact's page shown in the site. Of the twelve exported pages that
# carry a script (2026-10-24), three touch localStorage or sessionStorage, each inside try/catch, so
# they render without storage; one, a design canvas, fetches its own source only for an editor's
# save, which needs the artifact runtime the site does not have; none uses XMLHttpRequest. So no
# page needs the site's origin and allow-same-origin stays off, since with it a page's script could
# read the site's other pages and its storage; allow-popups lets a page's links open a new tab. The
# book's own interactive figures keep their stricter sandbox in figure_block.
EXPORT_SANDBOX = "allow-scripts allow-popups"
EXPORT_PAGE = "index.html"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def esc(text):
    return html.escape(str(text if text is not None else ""))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def newest_first(records):
    """Artifact ids, the dated ones newest first by the part of the date they give, then
    the undated ones by title."""
    dated, undated = [], []
    for aid, r in records.items():
        found = re.match(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", r.get("date") or "")
        if found:
            dated.append(("-".join(g or "00" for g in found.groups()), aid))
        else:
            undated.append((r["title"].lower(), aid))
    return [aid for _k, aid in sorted(dated, reverse=True)] + [aid for _k, aid in sorted(undated)]


def ledger_tools():
    """The synthesis's own modules, from this repository: its extraction, its redaction and its
    concept ledger."""
    tools = str(ROOT / LEDGER_TOOLS)
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import extract  # noqa: E402
    import redact  # noqa: E402
    import synth_concepts  # noqa: E402
    return extract, redact, synth_concepts


def exported_pages(root):
    """The folders under artifacts/ whose export holds a page, index.html, sorted by name; a Docs
    artifact, exported as index.md alone, has none, and the synthesis's folder is left out with any
    folder whose name starts with an underscore or a dot, as Book.folders leaves them out."""
    base = Path(root) / "artifacts"
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir()
                  if p.is_dir() and not p.name.startswith(("_", ".")) and (p / EXPORT_PAGE).is_file())


def exported_folder(target):
    """The folder a record's artifact path names, artifacts/<folder>/, or None for any other path
    and for a web address."""
    found = re.fullmatch(r"artifacts/([^/]+)/?", (target or "").strip())
    return found.group(1) if found else None


def export_page(folder):
    """Where an exported artifact's page is in the site."""
    return f"artifacts/{folder}/{EXPORT_PAGE}"


def leave_out(_directory, names):
    """What a copied export leaves behind at any depth: dotfiles and Markdown files, which are the
    export's notes and a Docs artifact's text, not its page."""
    return [n for n in names if n.startswith(".") or n.endswith(".md")]


def code_owners(root):
    """The logins .github/CODEOWNERS names, the owner's among them; a team's name is left out."""
    path = Path(root) / ".github" / "CODEOWNERS"
    if not path.exists():
        return set()
    text = "\n".join(line.split("#", 1)[0] for line in path.read_text(encoding="utf-8").splitlines())
    return set(re.findall(r"@([A-Za-z0-9][A-Za-z0-9-]*)(?![/A-Za-z0-9-])", text))


class Privacy:
    """What a page leaves out of a record: what the synthesis's own rules leave out (redact.RULES
    and extract.without_contacts), which a record read before a rule was added may still hold, and
    two things those rules do not take: the owner's account names, from the records' own account
    field and the code owners' file, and a person named by title, whom the book names by role."""

    def __init__(self, root, records):
        self.extract, self.redact, _concepts = ledger_tools()
        names = {r.get("account") or "" for r in records} | code_owners(root)
        names = sorted((n for n in names if ACCOUNT_SHAPE.fullmatch(n)), key=len, reverse=True)
        self.accounts = None
        if names:
            alternatives = "|".join(map(re.escape, names))
            self.accounts = re.compile(rf"(?<![A-Za-z0-9-])(?:{alternatives})(?![A-Za-z0-9-])", re.I)

    def text(self, text):
        text = self.redact.scrub(self.extract.without_contacts(text), collections.Counter())
        if self.accounts:
            text = self.accounts.sub("[the owner's account]", text)
        return TITLED_PERSON.sub("[a colleague]", text)

    def record(self, value, key=None):
        """Every string of a record but the fields that name it, as redact.walk goes through one."""
        if key in NAMING_FIELDS:
            return value
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.record(v) for v in value]
        if isinstance(value, dict):
            return {k: self.record(v, k) for k, v in value.items()}
        return value


# What a build reads

class Book:
    """The plan, the records and what they say of each other, from one root."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.plan = load_json(self.root / WORK / "toc-hand.json")
        self.inventory = load_json(self.root / SYNTHESIS / "inventory.json")
        self.clusters = load_json(self.root / WORK / "clustering.json")["judged"]["clusters"]
        self.ledger = load_json(self.root / WORK / "concepts.json")
        self.state = load_json(self.root / WORK / "state.json")
        privacy = Privacy(self.root, self.inventory["artifacts"])
        self.records = {f"{r['repo']}/{r['folder']}": privacy.record(r) for r in self.inventory["artifacts"]}
        self.figures = load_figures(self.root, privacy)
        self.exported = exported_pages(self.root)
        self.chapters = [(part, c) for part in self.plan["parts"] for c in part["chapters"]]
        self.readers = collections.defaultdict(list)  # artifact id -> [(chapter number, first or second)]
        for _part, c in self.chapters:
            for aid in c["artifacts_primary"]:
                self.readers[aid].append((c["number"], "first"))
            for aid in c.get("artifacts_secondary", []):
                self.readers[aid].append((c["number"], "second"))
        self.cluster_pages = self._cluster_pages()
        self.pages = self._pages()

    def _cluster_pages(self):
        """Each cluster's contradictions page, found by the cluster's name in its title."""
        out = {}
        for path in sorted((self.root / SYNTHESIS / "contradictions").glob("*.md")):
            first = path.read_text(encoding="utf-8").splitlines()[:1]
            if first and first[0].startswith("# Contradictions: "):
                out[first[0][len("# Contradictions: "):].strip()] = path
        return out

    def _pages(self):
        """Which page each repository path becomes, for links written in Markdown."""
        pages = {(SYNTHESIS / name).as_posix(): page for name, page in (
            ("clusters.md", "clusters.html"), ("concepts.md", "concepts.html"),
            ("contradictions.md", "contradictions.html"), ("table-of-contents.md", "plan.html"))}
        for name, path in self.cluster_pages.items():
            pages[path.relative_to(self.root).as_posix()] = contradictions_page(path)
        for aid, r in self.records.items():
            if r["repo"] == "SchwingNet":
                pages[f"artifacts/{r['folder']}"] = artifact_page(aid)
        for _part, c in self.chapters:
            pages[c["file"]] = chapter_page(c["number"])
        return pages

    def narrative(self, chapter):
        path = self.root / chapter["file"]
        return path.read_text(encoding="utf-8") if path.exists() else None

    def clusters_of(self, aid):
        """The clusters an artifact is in, with its place in each."""
        out = []
        for c in self.clusters:
            if aid not in c["members"] and aid not in c.get("secondary_members", []):
                continue
            place = {"cluster": c["name"], "role": "member" if aid in c["members"] else "secondary member"}
            if aid in c["canonical"]:
                place["role"] = "canonical"
            for s in c["superseded"]:
                if s["id"] == aid:
                    place.update(role="superseded", by=s["by"], why=s["why"])
            for d in c.get("duplicates") or []:
                if isinstance(d, dict) and d.get("id") == aid:
                    place.update(role="duplicate", by=d.get("of") or d.get("by"), why=d.get("why", ""))
            out.append(place)
        return out

    def superseded_by(self, aid):
        for place in self.clusters_of(aid):
            if place["role"] in ("superseded", "duplicate"):
                return place
        return None

    def figures_of(self, ids):
        ids = set(ids)
        return [f for f in self.ledger["figures"] if ids & set(f["artifacts"])]

    def source_checks(self, chapter):
        """The ledger's checks of the chapter's own sources that did not simply agree."""
        sources = set(chapter_ids(chapter)) | {"notes:" + p for p in chapter.get("repository_sources", [])}
        return [c for c in self.ledger["checks"] if c["source"] in sources and c["outcome"] != "agrees"]

    def folders(self):
        """The artifact folders on this commit, with each one's git tree where git can say;
        git names each path whole, quoting none, as -z asks."""
        base = self.root / "artifacts"
        names = sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith("_"))
        trees = {}
        try:
            listed = subprocess.run(["git", "-C", str(self.root), "ls-tree", "-z", "HEAD", "artifacts/"],
                                    capture_output=True, text=True, check=True).stdout
            for entry in listed.split("\0"):
                meta, _, path = entry.partition("\t")
                if meta.split()[1:2] == ["tree"]:
                    trees[path.split("/", 1)[1]] = meta.split()[2]
        except (OSError, subprocess.CalledProcessError):
            trees = None
        return names, trees

    def pending(self):
        """What the book does not hold yet: folders with no record, artifacts changed since
        their record was read, records no chapter reads, records whose folder is gone, and
        chapter files the plan does not name."""
        names, trees = self.folders()
        unread = [n for n in names if f"SchwingNet/{n}" not in self.records]
        gone = [aid for aid, r in self.records.items() if r["repo"] == "SchwingNet" and r["folder"] not in names]
        changed = []
        if trees is not None:
            stamp = self.state.get("artifacts", {})
            changed = [n for n in names if f"SchwingNet/{n}" in self.records and f"SchwingNet/{n}" in stamp
                       and trees.get(n) not in (None, stamp[f"SchwingNet/{n}"])]
        unplaced = [aid for aid in self.records if aid not in self.readers]
        planned = {c["file"] for _p, c in self.chapters}
        stray = sorted(rel for rel in (p.relative_to(self.root).as_posix() for p in (self.root / BOOK).glob("*.md"))
                       if rel not in planned and not rel.endswith("/README.md"))
        return {"unread": unread, "changed": changed, "unplaced": unplaced, "gone": gone, "stray": stray,
                "git": trees is not None}

    def likely_chapters(self, aid):
        """The chapters that read first a canonical artifact of one of this artifact's
        clusters: where a reader looks for it until the plan places it."""
        canon = {a for c in self.clusters if aid in c["members"] + c.get("secondary_members", []) for a in c["canonical"]}
        return [c["number"] for _p, c in self.chapters if canon & set(c["artifacts_primary"])]


def is_figure(path):
    """A JSON under figures/ is a figure's record when an image or a page of its own name stands
    beside it; any other JSON there is data a figure is drawn from, as chapter 35's corpora are."""
    return any(path.with_suffix(ext).exists() for ext in (".svg", ".png", ".html"))


def load_figures(root, privacy):
    """Every figure record under docs/textbook/figures/ (is_figure), by its id, with the image and the
    interactive page beside it where they exist; the records' prose goes through the same privacy
    pass as the artifacts' records."""
    out = {}
    base = Path(root) / FIGURES
    for path in sorted(base.glob("*/*.json")) if base.is_dir() else []:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(rec, dict) or not is_figure(path):
            continue
        rec = {k: (v if k in ("id", "chapter", "explore", "rerun") else privacy.record(v)) for k, v in rec.items()}
        rel = path.relative_to(Path(root) / BOOK).with_suffix("")
        rec["_stem"] = rel.as_posix()
        rec["_image"] = next((f"{rec['_stem']}{ext}" for ext in (".svg", ".png") if path.with_suffix(ext).exists()), None)
        rec["_html"] = f"{rec['_stem']}.html" if path.with_suffix(".html").exists() else None
        out[rec.get("id") or rec["_stem"].split("/", 1)[1]] = rec
    return out


def traced(rec):
    """How far a figure's record traces it: to the script that drew it, to the data only, or to
    the artifact alone."""
    source = rec.get("source") or {}
    made_by = source.get("made_by") or ""
    if SCRIPT_NAME.search(made_by) and not NOT_THE_DRAWING.search(made_by):
        return "script"
    if SCRIPT_NAME.search(made_by):
        return "data"
    if source.get("data") or source.get("run"):
        return "data"
    return "artifact"


def rerun_url(repo, rec):
    """A new issue on the repository, labelled figure-rerun, whose body carries the figure's id on a
    line of its own, the one line .github/workflows/figure.yml reads."""
    fid = rec.get("id", "")
    title = f"Re-run figure {fid}"
    body = (f"{RERUN_LINE}: {fid}\n\nOpened from the textbook's Re-run button for \"{rec.get('title', '')}\". "
            "The workflow reads only the id above and runs only what the figure's committed record says.")
    query = urllib.parse.urlencode({"labels": "figure-rerun", "title": title, "body": body})
    return f"https://github.com/{repo}/issues/new?{query}"


def ask_url(repo, subject, record, extra=()):
    """A new issue on the repository whose body begins "@claude", names what the reader is looking at
    and its record, and leaves a line for the question: .github/workflows/claude.yml answers an issue
    opened so, for the repository's owner, its organization's members and its collaborators."""
    body = "\n".join(["@claude", "", f"About: {subject}", f"Its record: {record}", *extra, "",
                      "My question or request (type it here, in place of this line, before you submit):", ""])
    query = urllib.parse.urlencode({"title": f"Ask Claude: {subject}", "body": body})
    return f"https://github.com/{repo}/issues/new?{query}"


def ask_button(repo, subject, record, extra=()):
    return f'<a class="button ask" href="{esc(ask_url(repo, subject, record, extra))}">Ask Claude</a>'


def rerun_words(rec):
    """What the Re-run button will do, and what it costs, from the record's rerun field."""
    rerun = rec.get("rerun") or {}
    where, cost = rerun.get("where"), rerun.get("cost") or "not recorded"
    if where == "actions":
        return (f"Opening the issue runs the recorded command on a GitHub runner from committed files and opens a pull "
                f"request with the figure it draws. Cost: {cost}; no grid job and no Claude.")
    if where == "grid":
        return (f"Opening the issue only asks: the workflow answers with the exact grid command and the link to the grid "
                f"workflow and submits nothing, since a grid job waits for the owner's word and the number of jobs. "
                f"Cost: {cost}.")
    return ("No command is recorded that redraws this figure, so opening the issue answers with the links to explore "
            "its method instead. Cost: nothing.")


def chapter_ids(chapter):
    return list(chapter["artifacts_primary"]) + list(chapter.get("artifacts_secondary", []))


def chapter_page(number):
    return f"chapter-{number}.html"


def artifact_page(aid):
    repo, folder = aid.split("/", 1)
    return f"artifact-{folder}.html" if repo == "SchwingNet" else f"artifact-{slug(repo)}-{folder}.html"


def contradictions_page(path):
    return f"contradictions-{Path(path).stem}.html"


# Checking a chapter's words against the ledger

class Ledger:
    """The concept ledger's own checks, run on a chapter's narrative at build time, with the
    ledger's code from this repository and its figures from the book being built."""

    def __init__(self, book):
        self.extract, self.redact, self.concepts = ledger_tools()
        self.book = book

    def check(self, source, text):
        """Each check with the whole line it was found on, since a check keeps only the start of
        its passage and a disclaimer may stand at the line's end."""
        clean = self.redact.scrub(self.extract.without_contacts(text), collections.Counter())
        lines = clean.splitlines()
        texts = {source: clean}
        equal = collections.defaultdict(lambda: 1.0)
        found = (self.concepts.check_datasets(texts, self.book.ledger["datasets"])
                 + self.concepts.check_figures(texts, self.book.ledger["figures"], equal))
        unique = {c["key"]: c for c in found}
        for c in unique.values():
            c["line_text"] = lines[c["line"] - 1] if 0 < c["line"] <= len(lines) else c["text"]
        return sorted(unique.values(), key=lambda c: (c["line"], c["concept"]))


# Laying out a page

CSS = """
:root { --method:#a33a37; --warn:#9a6212; --ok:#3f7a3a; --soft:#f6f3ec; }
@media (prefers-color-scheme: dark) { :root { --method:#f08a84; --warn:#e0a85a; --ok:#8cc47f; --soft:#1b1c20; } }
.banner { background:var(--panel); border-bottom:1px solid var(--line); font-size:13px; color:var(--muted); padding:6px 20px; }
nav h4 { margin-top:18px; }
nav a.ch { font-size:13.5px; line-height:1.35; padding:3px 0; }
.chips { display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 14px; }
.chip { font-size:12px; border:1px solid var(--line); border-radius:999px; padding:1px 9px; background:var(--panel);
        color:var(--fg); }
.chip.method { border-color:var(--method); color:var(--method); }
.chip.warn { border-color:var(--warn); color:var(--warn); }
.chip.ok { border-color:var(--ok); color:var(--ok); }
.card { border:1px solid var(--line); border-radius:10px; padding:12px 16px; margin:12px 0; background:var(--soft); }
.card.superseded { border-style:dashed; }
.card h4 { margin:0 0 4px; font-size:17px; }
.card p { margin:6px 0; }
.question { color:var(--muted); }
.links { display:flex; gap:14px; flex-wrap:wrap; font-size:14px; margin-top:8px; }
.notice { border-left:4px solid var(--accent); background:var(--panel); padding:10px 14px; border-radius:6px; margin:14px 0; }
.notice.warn { border-color:var(--warn); }
details { margin:10px 0; }
details summary { cursor:pointer; color:var(--accent); }
.pager { display:flex; justify-content:space-between; gap:12px; margin-top:40px; border-top:1px solid var(--line); padding-top:14px; }
input.filter { width:100%; padding:8px 10px; border:1px solid var(--line); border-radius:8px; background:var(--panel);
               color:var(--fg); font-size:15px; margin:8px 0 4px; }
.count { color:var(--muted); font-size:14px; }
figure.fig { margin:18px 0; padding:12px; border:1px solid var(--line); border-radius:10px; background:var(--soft); }
figure.fig img { display:block; margin:0 auto; max-width:100%; }
figure.fig iframe { width:100%; height:520px; border:0; background:#fff; border-radius:8px; }
figure.embed iframe { height:76vh; min-height:420px; }
figure.fig figcaption { margin-top:8px; font-size:14.5px; }
.source { font-size:13.5px; margin-top:8px; }
.source dt { font-weight:600; margin-top:4px; }
.source dd { margin:0 0 2px 14px; }
.buttons { display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; align-items:flex-start; }
.button, .buttons summary { display:inline-block; border:1px solid var(--accent); color:var(--accent); border-radius:6px;
                            padding:3px 12px; font-size:13.5px; text-decoration:none; cursor:pointer; list-style:none; }
.buttons details { margin:0; }
.buttons details[open] { flex-basis:100%; }
.button.ask { border-color:var(--ok); color:var(--ok); }
.asks { margin:4px 0 14px; }
"""

FILTER_JS = """
<script>
document.addEventListener("DOMContentLoaded", function () {
  var box = document.getElementById("filter"); if (!box) return;
  var rows = Array.prototype.slice.call(document.querySelectorAll("[data-find]"));
  var count = document.getElementById("shown");
  box.addEventListener("input", function () {
    var words = box.value.toLowerCase().split(/\\s+/).filter(Boolean), shown = 0;
    rows.forEach(function (row) {
      var text = row.getAttribute("data-find");
      var hit = words.every(function (w) { return text.indexOf(w) >= 0; });
      row.style.display = hit ? "" : "none"; if (hit) shown++;
    });
    if (count) count.textContent = shown;
  });
});
</script>
"""


def page(title, body, nav, meta, script=""):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{esc(title)} - The SchwingNet textbook</title><style>{living_docs.CSS}{CSS}</style>{script}</head>
<body><div class="banner">Members only. Confidential until the provisional is filed: nothing on this site may be copied to a public place.</div>
<header><a class="brand" href="index.html">The SchwingNet textbook</a><span class="meta">{meta}</span></header>
<div class="wrap"><nav>{nav}</nav><main>{body}</main></div></body></html>
"""


def nav_html(book, pending_count, here):
    def link(name, label, cls=""):
        mark = " here" if name == here else ""
        return f'<a class="{cls}{mark}" href="{name}">{esc(label)}</a>'

    out = ["<h4>The book</h4>", link("index.html", "Front page"), link("artifacts.html", "Every artifact"),
           link("figures.html", f"Every figure ({len(book.figures)})"), link("research.html", "Research loop"),
           link("pending.html", f"Not yet in the book ({pending_count})")]
    for part in book.plan["parts"]:
        out.append(f"<h4>{esc(part['label'])}: {esc(part['title'])}</h4>")
        out += [link(chapter_page(c["number"]), f"{c['number']} {c['title']}", "ch") for c in part["chapters"]]
    out += ["<h4>The record</h4>", link("clusters.html", "Clusters"), link("contradictions.html", "Contradictions"),
            link("concepts.html", "Concept ledger"), link("plan.html", "The plan of the book")]
    return "".join(out)


class Builder:
    """Writes every page of the site into one folder."""

    def __init__(self, book, out, repo, sha):
        self.book, self.out, self.repo, self.sha = book, Path(out), repo, sha
        self.pending = book.pending()
        self.pending_count = sum(len(self.pending[k]) for k in ("unread", "changed", "unplaced", "gone", "stray"))
        commit = f"commit {sha[:7]}, " if sha else ""
        self.meta = esc(f"built from {commit}the records stamped {book.state.get('stamped', 'undated')}")
        self.ledger = Ledger(book)

    # links

    def github(self, rel, directory=False):
        kind = "tree" if directory else "blob"
        if self.repo:
            return f"https://github.com/{self.repo}/{kind}/{self.sha or 'HEAD'}/{rel}"
        return f"https://github.com/OpenSpineConsortium/SchwingNet/{kind}/main/{rel}"

    def linker(self, source):
        here = (self.book.root / source).parent

        def link_for(target):
            if target.startswith(ST_TREE):
                aid = "symphony-template/" + target[len(ST_TREE):].strip("/").split("/")[0]
                return artifact_page(aid) if aid in self.book.records else target
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                return target
            path, _, anchor = target.partition("#")
            resolved = (here / path).resolve()
            try:
                rel = resolved.relative_to(self.book.root).as_posix()
            except ValueError:
                return target
            tail = f"#{anchor}" if anchor else ""
            if rel in self.book.pages:
                return self.book.pages[rel] + tail
            return self.github(rel, resolved.is_dir()) + tail

        return link_for

    def markdown(self, text, source):
        return living_docs.markdown_html(text, self.linker(source))

    # figures

    def narrative_html(self, text, source):
        """A chapter's narrative with each figure (an image line and its italic caption on the next
        line) laid out from its record in place of the two lines."""
        lines, blocks, out, i = text.splitlines(), [], [], 0
        while i < len(lines):
            found = FIGURE_IMAGE.match(lines[i])
            if found:
                caption = FIGURE_CAPTION.match(lines[i + 1]) if i + 1 < len(lines) else None
                blocks.append((found, caption))
                out += ["", f"FIGUREBLOCK{len(blocks) - 1}END", ""]
                i += 2 if caption else 1
                continue
            out.append(lines[i])
            i += 1
        rendered = self.markdown("\n".join(out), source)
        for k, (found, caption) in enumerate(blocks):
            rendered = rendered.replace(f"<p>FIGUREBLOCK{k}END</p>", self.figure_html(found, caption, source))
        return rendered

    def figure_html(self, found, caption, source):
        alt, rel, chapter, stem = found.groups()
        rec = self.book.figures.get(f"{chapter}/{stem}")
        number = caption.group(1) if caption else ""
        if rec is None:
            text = self.markdown(caption.group(2), source) if caption else ""
            return (f'<figure class="fig"><img src="{esc(rel)}" alt="{esc(alt)}"><figcaption>'
                    f"<strong>Figure {esc(number)}.</strong> {text}"
                    '<p class="notice warn">This figure has no record yet: where it came from is not written down.</p>'
                    f'<div class="buttons">{ask_button(self.repo or DEFAULT_REPO, f"figure {chapter}/{stem}", (BOOK / rel).as_posix())}</div>'
                    "</figcaption></figure>")
        return self.figure_block(rec, number, alt)

    def figure_block(self, rec, number="", alt=""):
        if rec.get("_html"):
            # sandboxed without same-origin, so a figure's script cannot reach the site's pages or storage
            shown = (f'<iframe src="{esc(rec["_html"])}" title="{esc(rec.get("title"))}" sandbox="allow-scripts" '
                     'loading="lazy"></iframe>')
        elif rec.get("_image"):
            shown = f'<img src="{esc(rec["_image"])}" alt="{esc(alt or rec.get("title"))}" loading="lazy">'
        else:
            shown = '<p class="notice warn">The image named by this record is not in the repository.</p>'
        status = rec.get("status") or "unstated"
        chips = (f'<span class="chip">{esc(rec.get("grade") or "ungraded")}</span>'
                 f'<span class="chip {"ok" if status == "current" else "warn"}">{esc(status)}</span>'
                 f'<span class="chip">traced to the {esc(traced(rec))}</span>')
        label = f"<strong>Figure {esc(number)}.</strong> " if number else ""
        anchor = "fig-" + slug(rec.get("id", ""))
        return (f'<figure class="fig" id="{anchor}">{shown}<figcaption>{label}{esc(rec.get("caption"))}'
                f'<div class="chips">{chips}</div>{self.source_panel(rec)}</figcaption></figure>')

    def href(self, target):
        """A record's link: a web address as it is, an artifact's folder to its page, any other
        repository path to the file on GitHub."""
        if re.match(r"^https://", target):
            return target
        rel = target.strip("/")
        if rel in self.book.pages:
            return self.book.pages[rel]
        return self.github(rel, target.endswith("/"))

    def source_panel(self, rec):
        source = rec.get("source") or {}
        rows = [("Artifact", source.get("artifact")), ("Made by", source.get("made_by")), ("Commit", source.get("commit")),
                ("Data", "; ".join(source.get("data") or []) or None), ("Run", source.get("run")),
                ("How it was traced", source.get("notes"))]
        items = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in rows if v)
        explore = [e for e in rec.get("explore") or [] if isinstance(e, dict) and e.get("href")]
        links = "".join(f'<li><a href="{esc(self.href(e["href"]))}">{esc(e.get("label") or e["href"])}</a></li>'
                        for e in explore)
        rerun = rec.get("rerun") or {}
        command = f"<p>Command: <code>{esc(rerun['command'])}</code></p>" if rerun.get("command") else ""
        record_link = f'<a class="button" href="{esc(rec["_stem"] + ".json")}">The record</a>'
        return (f'<div class="source"><dl>{items}</dl><div class="buttons">'
                f"<details><summary>Explore</summary><ul>{links or '<li>No link is recorded beyond the artifact.</li>'}</ul>"
                f"<p>The method: {esc(source.get('made_by') or 'not recorded')}.</p></details>"
                f'<a class="button" href="{esc(rerun_url(self.repo or DEFAULT_REPO, rec))}">Re-run</a>{record_link}'
                f"{self.open_button(rec)}{self.figure_ask(rec)}</div>"
                f'<p class="count">Re-run: {esc(rerun_words(rec))}</p>{command}</div>')

    def open_button(self, rec):
        """The button that opens the exported page of the artifact a figure's record traces it to,
        where that artifact's export holds one; a figure traced to a Docs artifact, to one not
        exported here or to no artifact gets none."""
        folder = exported_folder((rec.get("source") or {}).get("artifact"))
        if folder not in self.book.exported:
            return ""
        return f'<a class="button" href="{esc(export_page(folder))}">Open the artifact&#x27;s page</a>'

    def embed(self, folder, title):
        """An artifact's own exported page, shown above its record in an iframe sandboxed without
        the site's origin (EXPORT_SANDBOX), loaded when scrolled to, with the link that opens it
        full-page."""
        src = export_page(folder)
        return (f'<figure class="fig embed"><iframe src="{esc(src)}" title="{esc(title)}: the artifact&#x27;s own page" '
                f'loading="lazy" sandbox="{EXPORT_SANDBOX}"></iframe><figcaption>The artifact&#x27;s own page as it '
                f'was exported to the repository, interactive where it was; <a href="{esc(src)}">open it full-page</a>.'
                "</figcaption></figure>")

    def figure_ask(self, rec):
        """The Ask Claude button of a figure, naming its id, its chapter and its record's file."""
        fid = rec.get("id", "")
        chapter = rec.get("chapter") or fid.split("/", 1)[0]
        record = (FIGURES / f"{fid}.json").as_posix()
        return ask_button(self.repo or DEFAULT_REPO, f"figure {fid} ({rec.get('title', '')})", record,
                          [f"In chapter {chapter}: {self.github(self.book_file(chapter))}"])

    def book_file(self, number):
        """The chapter file the plan names for a chapter number, or the book's folder."""
        for _part, c in self.book.chapters:
            if c["number"] == number:
                return c["file"]
        return BOOK.as_posix()

    def research_page(self):
        """The research loop: what it is, its switch and cap, and the register's queue as it stands."""
        path = self.book.root / BOOK / "claims.json"
        rows = []
        if path.exists():
            register = claims_rank.load(path)
            for entry in claims_rank.queue(register):
                ready = "ready" if entry["ready"] else "waits on another item"
                status = entry["status"]
                find = " ".join(str(x) for x in (entry["id"], entry["title"], status, ready)).lower()
                rows.append(f'<tr data-find="{esc(find)}"><td>{entry["rank"]}</td><td><code>{esc(entry["id"])}</code></td>'
                            f'<td>{esc(entry["title"])}</td><td><span class="chip {"ok" if status == "open" else "warn"}">'
                            f'{esc(status)}</span></td><td>{esc(ready)}</td><td>{entry["score"]}</td>'
                            f'<td>{"yes" if entry["needs_owner_word"] else "no"}</td></tr>')
        repo = self.repo or DEFAULT_REPO
        workflow = f"https://github.com/{repo}/actions/workflows/research.yml"
        variables = f"https://github.com/{repo}/settings/variables/actions"
        issues = f"https://github.com/{repo}/issues?q=is%3Aopen+label%3Aresearch"
        owner = f"https://github.com/{repo}/issues?q=is%3Aopen+label%3Aowner-act"
        body = ["<h1>The research loop</h1>",
                "<p>Every four hours a Claude session takes the best-ranked item of the claims register that nobody "
                "holds, opens or carries on its issue labelled research, claims it under the claim protocol as the worker "
                "research-loop, works it, and opens a pull request that updates the register and the chapter the result "
                "changes; the owner merges. The owner gave it full command of grid work, fetches and training on 24 "
                "October 2026; it still keeps the size rule, refuses CT-RATE without the owner's terabytes and "
                "Radiopaedia by script, uses no usage credits and puts nothing in a public place. Letters, e-mails, "
                "counsel, the IRB and the grid's gate words, which it cannot reach, become issues labelled owner-act "
                f'assigned to the owner. Its brief is <a href="{esc(self.github(".github/symphony/research.md"))}">'
                ".github/symphony/research.md</a>.</p>",
                '<div class="notice"><p><strong>The switch.</strong> The repository variable <code>RESEARCH_LOOP</code> '
                "set to <code>off</code> stops it; <code>RESEARCH_RUNS_PER_DAY</code> caps its runs a day (6 unless it "
                f'says otherwise, 50 at most). <a href="{esc(variables)}">The variables</a> &middot; '
                f'<a href="{esc(workflow)}">Its runs, and Run workflow to start one now</a> &middot; '
                f'<a href="{esc(issues)}">Its open issues</a> &middot; <a href="{esc(owner)}">What waits on the owner</a>'
                "</p></div>",
                "<h2>The queue</h2>",
                "<p>Every item not done, ranked by the weight of the claims it bears on over its cost "
                f'(<a href="{chapter_page("33")}">chapter 33</a>). An item under way is marked doing; the loop starts '
                "only open items that are ready, and skips an item an open issue or pull request labelled research "
                "already holds. Owner's word is what the register recorded before the owner's decision of 24 October; "
                "the loop no longer waits on it for grid work, fetches or training.</p>"]
        if rows:
            body += [f'<p class="count"><span id="shown">{len(rows)}</span> shown.</p>',
                     '<input id="filter" class="filter" type="search" placeholder="Filter by any word: an id, open, doing, ready">',
                     '<div class="table"><table><thead><tr><th>Rank</th><th>Item</th><th>What</th><th>Status</th>'
                     "<th>Ready</th><th>Score</th><th>Owner's word</th></tr></thead><tbody>" + "".join(rows)
                     + "</tbody></table></div>"]
        else:
            body.append("<p>The register, docs/textbook/claims.json, is not on this commit.</p>")
        self.write("research.html", "Research loop", "\n".join(body), FILTER_JS)

    def every_figure(self):
        b = self.book
        titles = {c["number"]: c["title"] for _p, c in b.chapters}
        rows, counts = [], collections.Counter()
        for fid, rec in sorted(b.figures.items()):
            level = traced(rec)
            counts[level] += 1
            chapter = rec.get("chapter") or fid.split("/", 1)[0]
            where = (rec.get("rerun") or {}).get("where") or "none"
            find = " ".join(str(x) for x in (fid, rec.get("title"), chapter, level, where, rec.get("status"))).lower()
            rows.append(f'<tr data-find="{esc(find)}"><td><a href="{chapter_page(chapter)}#fig-{slug(fid)}">{esc(rec.get("title"))}</a>'
                        f"<br><code>{esc(fid)}</code></td><td>{esc(chapter)} {esc(titles.get(chapter, ''))}</td>"
                        f"<td>{esc(level)}</td><td>{esc(where)}</td><td>{esc(rec.get('status'))}</td>"
                        f"<td>{esc((rec.get('source') or {}).get('made_by') or 'not recorded')}</td></tr>")
        body = ["<h1>Every figure</h1>",
                f"<p>{len(rows)} figures, each with its record. Traced to the script that drew it: {counts['script']}; "
                f"to its data or run only: {counts['data']}; to the artifact alone: {counts['artifact']}. Re-run says "
                "where a figure can be drawn again: actions on a GitHub runner, grid on the lab's cluster with the owner's "
                "word, none where no command is recorded.</p>",
                f'<p class="count"><span id="shown">{len(rows)}</span> shown.</p>',
                '<input id="filter" class="filter" type="search" placeholder="Filter by any word: a chapter, script, grid, none">',
                '<div class="table"><table><thead><tr><th>Figure</th><th>Chapter</th><th>Traced to</th><th>Re-run</th>'
                "<th>Status</th><th>Made by</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"]
        self.write("figures.html", "Every figure", "\n".join(body), FILTER_JS)

    def copy_figures(self):
        base = self.book.root / FIGURES
        if base.is_dir():
            shutil.copytree(base, self.out / "figures")

    def copy_exports(self):
        """Each exported artifact that has a page, copied whole under artifacts/<folder>/ with its
        tree, so the page's own scripts, styles, data and images are beside it as they are in the
        repository; dotfiles and Markdown stay behind (leave_out)."""
        for folder in self.book.exported:
            shutil.copytree(self.book.root / "artifacts" / folder, self.out / "artifacts" / folder, ignore=leave_out)

    def artifact_links(self, aid):
        """Where the artifact itself opens: on claude.ai, and as files in its repository; an
        artifact exported as a page shows that page on its own page here (Builder.embed)."""
        r = self.book.records[aid]
        repo, folder = aid.split("/", 1)
        out = []
        if r.get("link", "").startswith("https://claude.ai/"):
            out.append(f'<a href="{esc(r["link"])}">Open it on claude.ai</a>')
        if repo != "SchwingNet":
            out.append(f'<a href="{esc(ST_TREE + folder)}/">Its files in symphony-template</a>')
        elif (self.book.root / "artifacts" / folder).is_dir():
            out.append(f'<a href="{esc(self.github("artifacts/" + folder, True))}">Its files in the repository</a>')
        return '<div class="links">' + "".join(out) + "</div>"

    # pieces

    def chips_for(self, aid):
        r = self.book.records[aid]
        chips = [r.get("date") or "undated", f"{r.get('kind')} / {r.get('genre')}", r.get("confidentiality") or ""]
        out = [f'<span class="chip">{esc(c)}</span>' for c in chips if c]
        if r.get("confidentiality") == "schwingnet-method":
            out[-1] = f'<span class="chip method">{esc(r["confidentiality"])}</span>'
        for place in self.book.clusters_of(aid):
            if place["role"] in ("superseded", "duplicate"):
                by = self.book.records.get(place["by"], {}).get("title", place["by"])
                out.append(f'<span class="chip warn">{esc(place["role"])} by {esc(by)}</span>')
            elif place["role"] == "canonical":
                out.append(f'<span class="chip ok">canonical in {esc(place["cluster"])}</span>')
        return '<div class="chips">' + "".join(out) + "</div>"

    def card(self, aid, mark=""):
        r = self.book.records.get(aid)
        if r is None:
            return f'<div class="card"><h4>{esc(aid)}</h4><p>No record yet: the synthesis has not read it.</p></div>'
        old = self.book.superseded_by(aid)
        cls = "card superseded" if old else "card"
        note = ""
        if old:
            by = self.book.records.get(old["by"], {}).get("title", old["by"])
            note = (f'<p class="notice warn">Superseded by <a href="{artifact_page(old["by"])}">{esc(by)}</a>: '
                    f"its numbers are records, not final values. {esc(old.get('why', ''))}</p>")
        head = f'<h4>{esc(mark)}<a href="{artifact_page(aid)}">{esc(r["title"])}</a></h4>'
        return (f'<div class="{cls}">{head}{self.chips_for(aid)}'
                f'<p class="question">{esc(r.get("question"))}</p><p>{esc(r.get("summary"))}</p>{note}'
                f"{self.artifact_links(aid)}</div>")

    def figure_rows(self, figures, side_of=None):
        rows = []
        for f in figures:
            sides = []
            for i, (aid, quote) in enumerate(zip(f["artifacts"], f["quotes"])):
                if side_of and aid != side_of:
                    continue
                side = "ab"[i]
                values = [v for v in f["values"] if v["side"] == side]
                shown = "; ".join(f'{esc(v["figure"])}{"%" if v["percent"] else ""} '
                                  f'<span class="chip {"ok" if v["status"] == "current" else "warn"}">'
                                  f'{esc(VALUE_STATUS.get(v["status"], v["status"]))}</span>' for v in values)
                title = self.book.records.get(aid, {}).get("title", aid)
                sides.append(f'<a href="{artifact_page(aid)}">{esc(title)}</a>: "{esc(quote)}" {shown}')
            used = "" if not f.get("unused") else f'<br><span class="count">Not used for checks: {esc(f["unused"])}</span>'
            rows.append(f'<tr><td>{esc(f["quantity"])}{used}</td><td>{esc(VERDICTS.get(f["verdict"], f["verdict"]))}</td>'
                        f'<td>{"<br>".join(sides)}</td></tr>')
        if not rows:
            return "<p>The ledger has settled no figure for these artifacts.</p>"
        return ('<div class="table"><table><thead><tr><th>Quantity</th><th>Verdict</th><th>What each artifact gives</th>'
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    def checks_table(self, checks, show_source=False):
        """The checks as a table; a narrative's superseded or open figure whose line carries no
        disclaimer is marked, as the brief for the chapters asks one to carry it."""
        rows = []
        for c in checks:
            where = esc(c["source"]) if show_source else f"line {c['line']}"
            flag = ""
            if c["outcome"] in ("superseded", "open") and "line_text" in c and not DISCLAIMER.search(c["line_text"]):
                flag = ' <span class="chip warn">no disclaimer in the passage</span>'
            rows.append(f"<tr><td>{where}</td><td>{esc(OUTCOMES.get(c['outcome'], c['outcome']))}{flag}</td>"
                        f"<td><code>{esc(c['value'])}</code></td><td>{esc(c['concept'])}</td><td>{esc(c['text'])}</td></tr>")
        return ('<div class="table"><table><thead><tr><th>Where</th><th>Outcome</th><th>Figure</th><th>Concept</th>'
                "<th>Passage</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    # pages

    def write(self, name, title, body, script=""):
        nav = nav_html(self.book, self.pending_count, name)
        (self.out / name).write_text(page(title, body, nav, self.meta, script), encoding="utf-8")

    def front(self):
        b = self.book
        written = [c for _p, c in b.chapters if b.narrative(c) is not None]
        statuses = collections.Counter(v["status"] for f in b.ledger["figures"] for v in f["values"])
        repos = collections.Counter(r["repo"] for r in b.records.values())
        body = ["<h1>The SchwingNet textbook</h1>",
                "<p>The Artifact Textbook as a website: one page for each chapter of the book's plan and one for each "
                "artifact, laid out on every build from the synthesis's records of the artifacts; an artifact exported "
                "as a page shows that page, interactive, on its own page here, and each artifact opens on claude.ai, "
                "where it was shared by its link, or in its repository. A chapter shows its written narrative once there is one, and below it every artifact it reads, with "
                "its record, its place in its cluster and the figures the record has settled. Nothing here is written "
                "at build time: the records come from the synthesis's reads, and the narratives from the chapters "
                "under docs/textbook/, both merged by pull request.</p>",
                '<div class="notice">',
                f"<p><strong>As it stands.</strong> {len(b.records)} artifacts in the record ({repos['SchwingNet']} here, "
                f"{repos['symphony-template']} in symphony-template); {len(written)} of {len(b.chapters)} chapters have "
                f"a written narrative; the ledger has settled {len(b.ledger['figures'])} figures, whose values are "
                f"{statuses['current']} current, {statuses['superseded']} superseded and {statuses['open']} open. "
                f'<a href="pending.html">{self.pending_count} not yet in the book</a>.</p></div>',
                "<h2>How to read it</h2>",
                "<p>Every statement in a chapter's provenance table carries a grade. <strong>Measured</strong>: a "
                "number read from a result file or computed by tested code on held-out data, with its n and interval. "
                "<strong>Reported</strong>: stated by an artifact or a paper without the file behind it being read. "
                "<strong>Inferred</strong>: a judgment drawn from measurements, or a design claim with no outcome "
                "measured. <strong>Unverified</strong>: asserted with no source, or contradicted by another record. "
                "A figure from a superseded or leaked family is quoted only as a record, never as a final value, with "
                "a link to where it comes from so the page follows it when the record changes.</p>",
                "<p>Each chapter carries its label:</p><ul>" + "".join(
                    f"<li><strong>{esc(k)}</strong>: {esc(v)}</li>" for k, v in LABELS.items()) + "</ul>"]
        for part in b.plan["parts"]:
            body.append(f"<h2>{esc(part['label'])}: {esc(part['title'])}</h2>")
            if part.get("purpose"):
                body.append(f"<p>{esc(part['purpose'])}</p>")
            for c in part["chapters"]:
                state = "written" if b.narrative(c) is not None else "narrative not written yet"
                label_cls = "method" if c["confidentiality"] == "confidential-method" else ""
                body.append(f'<div class="card"><h4><a href="{chapter_page(c["number"])}">{esc(c["number"])} '
                            f'{esc(c["title"])}</a></h4><div class="chips"><span class="chip {label_cls}">'
                            f'{esc(c["confidentiality"])}</span><span class="chip">{len(chapter_ids(c))} artifacts</span>'
                            f'<span class="chip {"ok" if state == "written" else ""}">{state}</span></div>'
                            f'<p>{esc(c["purpose"])}</p></div>')
        body.append("<h2>About the plan</h2>" + f"<p>{esc(b.plan['preface'])}</p>")
        self.write("index.html", "Front page", "\n".join(body))

    def chapter(self, index):
        b = self.book
        part, c = b.chapters[index]
        ids = chapter_ids(c)
        text = b.narrative(c)
        label_cls = "method" if c["confidentiality"] == "confidential-method" else ""
        body = [f"<h1>{esc(c['number'])} {esc(c['title'])}</h1>",
                f'<div class="chips"><span class="chip">{esc(part["label"])}: {esc(part["title"])}</span>'
                f'<span class="chip {label_cls}">{esc(c["confidentiality"])}</span>'
                f'<span class="chip">{len(ids)} artifacts</span></div>',
                f'<p class="count">{esc(LABELS.get(c["confidentiality"], ""))}</p>',
                '<div class="buttons asks">' + ask_button(self.repo or DEFAULT_REPO, f"chapter {c['number']} {c['title']}",
                                                          c["file"]) + "</div>"]
        plan = (f"<p>{esc(c['purpose'])}</p><p><strong>Questions it answers</strong></p><ul>"
                + "".join(f"<li>{esc(q)}</li>" for q in c["questions_answered"]) + "</ul>")
        if text is None:
            body.append('<div class="notice">The narrative of this chapter is not written yet. The plan\'s purpose and '
                        "questions follow, then every artifact the chapter reads, with its record.</div>")
            body.append(plan)
        else:
            lines = text.splitlines()
            rest = "\n".join(lines[1:] if lines and lines[0].startswith("# ") else lines)
            body.append(self.narrative_html(rest, c["file"]))
            body.append(f"<details><summary>The plan for this chapter</summary>{plan}</details>")
            body.append(self.narrative_checks(c, text))
        body.append("<h2>The artifacts this chapter reads</h2>")
        body.append("<h3>Read first</h3>" + "".join(self.card(a) for a in c["artifacts_primary"]))
        if c.get("artifacts_secondary"):
            body.append("<h3>Read second</h3>" + "".join(self.card(a) for a in c["artifacts_secondary"]))
        new = [a for a in self.pending["unplaced"] if c["number"] in b.likely_chapters(a)]
        if new:
            body.append("<h3>New, not yet placed by the plan</h3><p>The plan does not place these yet; they are in a "
                        "cluster whose canonical artifact this chapter reads first.</p>" + "".join(self.card(a) for a in new))
        body.append("<h2>Figures the record has settled for these artifacts</h2>")
        body.append("<p>From the concept ledger, as it stands on this build. A value marked superseded is a record, not "
                    "a final value; one marked open is one the record has not settled, not quoted as current until it is "
                    "run again.</p>")
        body.append(self.figure_rows(b.figures_of(ids)))
        checks = b.source_checks(c)
        if checks:
            body.append("<h2>Where this chapter's sources part from the ledger</h2><p>The ledger's own checks of the "
                        "artifacts and repository files this chapter reads, those that did not simply agree: a "
                        "script's match, for a reader to weigh.</p>" + self.checks_table(checks, show_source=True))
        body.append(self.disagreements(ids))
        if c.get("repository_sources"):
            link_for = self.linker(c["file"])
            body.append("<h2>Repository files beside them</h2><ul>" + "".join(
                f'<li><a href="{esc(link_for("../../" + p))}"><code>{esc(p)}</code></a></li>'
                for p in c["repository_sources"]) + "</ul>")
        body.append(f"<h2>What research still owes this chapter</h2><p>{esc(c['research_needed'])}</p>")
        body.append(self.pager(index))
        self.write(chapter_page(c["number"]), f"{c['number']} {c['title']}", "\n".join(body))

    def narrative_checks(self, chapter, text):
        found = self.ledger.check(f"book:{chapter['file']}", text)
        agree = [c for c in found if c["outcome"] == "agrees"]
        flagged = [c for c in found if c["outcome"] != "agrees"]
        head = ("<h2>This chapter checked against the ledger</h2><p>The ledger's checks, run on this chapter's text "
                f"at this build, found {len(agree) + len(flagged)} passages that give a dataset count or a settled "
                f"figure: {len(agree)} agree with the ledger and {len(flagged)} give one another way, listed below. "
                "A figure's anchors count equally here, where the ledger weighs them by rarity. A script's match, "
                "for a reader to weigh.</p>")
        return head + (self.checks_table(flagged) if flagged else "")

    def disagreements(self, ids):
        b = self.book
        seen, items = set(), []
        for aid in ids:
            for place in b.clusters_of(aid):
                name = place["cluster"]
                if name in seen or name not in b.cluster_pages:
                    continue
                seen.add(name)
                canon = [b.records.get(a, {}).get("title", a) for c in b.clusters if c["name"] == name for a in c["canonical"]]
                items.append(f'<li><a href="{contradictions_page(b.cluster_pages[name])}">{esc(name)}</a>: canonical '
                             f'{esc("; ".join(canon))}</li>')
        if not items:
            return ""
        return ("<h2>Where the artifacts disagree</h2><p>The contradictions pages of the clusters these artifacts belong "
                "to, each disagreement with its verdict and the words it rests on.</p><ul>" + "".join(items) + "</ul>")

    def pager(self, index):
        chapters = self.book.chapters
        prev = chapters[index - 1][1] if index > 0 else None
        nxt = chapters[index + 1][1] if index + 1 < len(chapters) else None
        left = f'<a href="{chapter_page(prev["number"])}">{esc(prev["number"])} {esc(prev["title"])}</a>' if prev else "<span></span>"
        right = f'<a href="{chapter_page(nxt["number"])}">{esc(nxt["number"])} {esc(nxt["title"])}</a>' if nxt else "<span></span>"
        return f'<div class="pager">{left}{right}</div>'

    def artifact(self, aid):
        b = self.book
        r = b.records[aid]
        body = [f"<h1>{esc(r['title'])}</h1>", self.chips_for(aid), self.artifact_links(aid)]
        old = b.superseded_by(aid)
        if old:
            by = b.records.get(old["by"], {}).get("title", old["by"])
            body.append(f'<div class="notice warn">Superseded by <a href="{artifact_page(old["by"])}">{esc(by)}</a>. '
                        f"Its numbers are records, not final values. {esc(old.get('why', ''))}</div>")
        if r["repo"] == "SchwingNet" and r["folder"] in b.exported:
            body.append(self.embed(r["folder"], r["title"]))
        body.append(f"<h2>What it answers</h2><p class=\"question\">{esc(r.get('question'))}</p><p>{esc(r.get('summary'))}</p>")
        readers = b.readers.get(aid, [])
        if readers:
            titles = {c["number"]: c["title"] for _p, c in b.chapters}
            body.append("<h2>The chapters that read it</h2><ul>" + "".join(
                f'<li><a href="{chapter_page(n)}">{esc(n)} {esc(titles[n])}</a>, read {esc(order)}</li>'
                for n, order in readers) + "</ul>")
        else:
            likely = b.likely_chapters(aid)
            body.append('<div class="notice">No chapter of the plan reads it yet.' + (
                " Its clusters' canonical artifacts are read first by chapters " + ", ".join(
                    f'<a href="{chapter_page(n)}">{esc(n)}</a>' for n in likely) + "." if likely else "") + "</div>")
        places = b.clusters_of(aid)
        if places:
            body.append("<h2>Its place in the clusters</h2><ul>" + "".join(
                f"<li>{esc(p['cluster'])}: {esc(p['role'])}" + (
                    f" by {esc(b.records.get(p['by'], {}).get('title', p['by']))}: {esc(p.get('why', ''))}" if p.get("by") else "")
                + "</li>" for p in places) + "</ul>")
        body.append(self.record_tables(aid, r))
        body.append("<h2>Figures the record has settled</h2>" + self.figure_rows(b.figures_of([aid]), side_of=aid))
        body.append(self.read_notes(r))
        self.write(artifact_page(aid), r["title"], "\n".join(body))

    def record_tables(self, aid, r):
        out = []
        claims = r.get("key_claims") or []
        if claims:
            out.append("<h2>Key claims</h2><div class=\"table\"><table><thead><tr><th>Claim</th><th>Grade hint</th>"
                       "<th>Evidence in the artifact</th></tr></thead><tbody>" + "".join(
                           f"<tr><td>{esc(c.get('claim'))}</td><td>{esc(c.get('grade_hint'))}</td>"
                           f"<td>{esc(c.get('evidence_in_artifact'))}</td></tr>" for c in claims) + "</tbody></table></div>")
        numbers = r.get("numbers") or []
        if numbers:
            out.append("<h2>Numbers</h2><div class=\"table\"><table><thead><tr><th>Value</th><th>Unit</th><th>n</th>"
                       "<th>Interval</th><th>Of what</th></tr></thead><tbody>" + "".join(
                           f"<tr><td>{esc(n.get('value'))}</td><td>{esc(n.get('unit'))}</td><td>{esc(n.get('n'))}</td>"
                           f"<td>{esc(n.get('interval'))}</td><td>{esc(n.get('context'))}</td></tr>" for n in numbers)
                       + "</tbody></table></div>")
        decisions = r.get("decisions") or []
        if decisions:
            out.append("<h2>Decisions</h2><div class=\"table\"><table><thead><tr><th>Date</th><th>Decision</th><th>By</th>"
                       "<th>Why</th></tr></thead><tbody>" + "".join(
                           f"<tr><td>{esc(d.get('date'))}</td><td>{esc(d.get('decision'))}</td><td>{esc(d.get('owner'))}</td>"
                           f"<td>{esc(d.get('reason'))}</td></tr>" for d in decisions) + "</tbody></table></div>")
        for key, title in (("open_questions", "Open questions"), ("unsourced_assertions", "Asserted without a source"),
                           ("stale_markers", "Dated or pending"), ("datasets", "Datasets it names"),
                           ("tools", "Tools it names"), ("models", "Models it names"),
                           ("cross_references", "What it refers to"), ("people_by_role", "People, by role")):
            items = r.get(key) or []
            if items:
                out.append(f"<h2>{title}</h2><ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>")
        sources = r.get("external_sources") or []
        if sources:
            out.append("<h2>Sources it cites</h2><ul>" + "".join(
                f"<li>{esc(s.get('title'))}: {self.maybe_link(s.get('url_or_citation'))}</li>" for s in sources) + "</ul>")
        related = r.get("related_titles") or []
        if related:
            by_title = collections.defaultdict(list)
            for other, x in self.book.records.items():
                by_title[x["title"]].append(other)
            out.append("<h2>Related artifacts</h2><ul>" + "".join(self.related_item(aid, x, by_title) for x in related)
                       + "</ul>")
        return "\n".join(out)

    def related_item(self, aid, related, by_title):
        """A related artifact named by its title, linked where one other record holds that title;
        where several do, as two versions of one artifact may, each is linked by its date."""
        title = related.get("title")
        others = [a for a in by_title.get(title, []) if a != aid]
        if len(others) == 1:
            name = f'<a href="{artifact_page(others[0])}">{esc(title)}</a>'
        elif others:
            name = esc(title) + " (" + ", ".join(
                f'<a href="{artifact_page(a)}">{esc(self.book.records[a].get("date") or a)}</a>' for a in others) + ")"
        else:
            name = esc(title)
        return f"<li>{name} ({esc(related.get('relation'))}): {esc(related.get('why'))}</li>"

    @staticmethod
    def maybe_link(text):
        text = text or ""
        if re.match(r"^https://\S+$", text):
            return f'<a href="{esc(text)}">{esc(text)}</a>'
        return esc(text)

    @staticmethod
    def read_notes(r):
        parts = [("When it is from", r.get("date_evidence")), ("How it was read", r.get("coverage_notes")),
                 ("Notes", r.get("notes"))]
        return "<h2>How the record was made</h2>" + "".join(
            f"<p><strong>{esc(t)}.</strong> {esc(v)}</p>" for t, v in parts if v)

    def every_artifact(self):
        b = self.book
        rows = []
        for aid in newest_first(b.records):
            r = b.records[aid]
            chapters = ", ".join(n for n, _o in b.readers.get(aid, [])) or "none yet"
            old = b.superseded_by(aid)
            status = f"{old['role']}" if old else ""
            find = " ".join(str(x) for x in (r["title"], r.get("readme_summary"), r.get("genre"), r.get("kind"),
                                             r.get("confidentiality"), aid, chapters, status)).lower()
            rows.append(f'<tr data-find="{esc(find)}"><td><a href="{artifact_page(aid)}">{esc(r["title"])}</a></td>'
                        f"<td>{esc(r.get('date'))}</td><td>{esc(r.get('genre'))}</td><td>{esc(r.get('confidentiality'))}</td>"
                        f"<td>{esc(status)}</td><td>{esc(chapters)}</td><td>{esc(r.get('readme_summary'))}</td></tr>")
        body = ["<h1>Every artifact</h1>",
                f'<p class="count">{len(rows)} artifacts, newest first; <span id="shown">{len(rows)}</span> shown.</p>',
                '<input id="filter" class="filter" type="search" placeholder="Filter by any word: a title, a genre, a chapter number">',
                '<div class="table"><table><thead><tr><th>Artifact</th><th>Date</th><th>Genre</th><th>Confidentiality</th>'
                "<th>Status</th><th>Chapters</th><th>What it is</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"]
        self.write("artifacts.html", "Every artifact", "\n".join(body), FILTER_JS)

    def pending_page(self):
        b, p = self.book, self.pending
        body = ["<h1>Not yet in the book</h1>",
                "<p>What this build found that the book does not hold yet. A new artifact's folder appears here on the "
                "first build after its merge; the synthesis reads it into its record within a day "
                "(.github/workflows/synthesis.yml), and the plan places it in a chapter once a person adds it to the "
                "table of contents (artifacts/_synthesis/work/tools/textbook_toc.py).</p>"]
        body.append("<h2>Folders with no record yet</h2>")
        body.append("<ul>" + "".join(f'<li><a href="{esc(self.github("artifacts/" + n, True))}">{esc(n)}</a></li>'
                                     for n in p["unread"]) + "</ul>" if p["unread"] else "<p>None.</p>")
        body.append("<h2>Changed since its record was read</h2>")
        if not p["git"]:
            body.append("<p>Not checked: git could not list this build's trees.</p>")
        elif p["changed"]:
            body.append("<ul>" + "".join(f'<li><a href="{artifact_page("SchwingNet/" + n)}">{esc(b.records["SchwingNet/" + n]["title"])}</a>'
                                         "</li>" for n in p["changed"]) + "</ul>")
        else:
            body.append("<p>None here. symphony-template's artifacts are checked by the synthesis's daily look.</p>")
        body.append("<h2>Read, but no chapter reads it yet</h2>")
        if p["unplaced"]:
            body.append("".join(self.card(a) for a in p["unplaced"]))
        else:
            body.append("<p>None: every artifact in the record has a chapter.</p>")
        body.append("<h2>Recorded, but its folder is gone</h2>")
        body.append("".join(self.card(a) for a in p["gone"]) if p["gone"] else "<p>None.</p>")
        body.append("<h2>Chapter files the plan does not name</h2>")
        if p["stray"]:
            body.append("<p>A chapter's page shows only the file the plan names for it.</p><ul>" + "".join(
                f'<li><a href="{esc(self.github(rel))}"><code>{esc(rel)}</code></a></li>' for rel in p["stray"]) + "</ul>")
        else:
            body.append("<p>None.</p>")
        skipped = len(b.inventory.get("skipped") or [])
        if skipped:
            body.append(f"<p class=\"count\">{skipped} artifacts the index marks as not copied, since they hold personal "
                        "details, are neither read nor shown.</p>")
        self.write("pending.html", "Not yet in the book", "\n".join(body))

    def record_pages(self):
        b = self.book
        sources = [("clusters.md", "clusters.html"), ("concepts.md", "concepts.html"),
                   ("contradictions.md", "contradictions.html"), ("table-of-contents.md", "plan.html")]
        for name, out in sources:
            rel = (SYNTHESIS / name).as_posix()
            text = (b.root / rel).read_text(encoding="utf-8")
            self.write(out, living_docs.title_of(text), self.markdown(text, rel))
        for _name, path in b.cluster_pages.items():
            rel = path.relative_to(b.root).as_posix()
            text = path.read_text(encoding="utf-8")
            self.write(contradictions_page(path), living_docs.title_of(text), self.markdown(text, rel))

    def build(self):
        self.front()
        for i in range(len(self.book.chapters)):
            self.chapter(i)
        for aid in self.book.records:
            self.artifact(aid)
        self.every_artifact()
        self.every_figure()
        self.research_page()
        self.copy_figures()
        self.copy_exports()
        self.pending_page()
        self.record_pages()
        (self.out / MARKER).write_text("built by tools/textbook_site.py\n", encoding="utf-8")


def prepare(out):
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        if not (out / MARKER).exists():
            raise SystemExit(f"{out}: not empty and not a textbook this tool built; give an empty or new folder")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", help="the folder to write the site into, empty or new")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="OWNER/NAME, for links to files")
    parser.add_argument("--sha", default="", help="the commit the site describes")
    parser.add_argument("--root", default=str(ROOT), help="the repository to build from (this one by default)")
    args = parser.parse_args(argv)
    out = prepare(args.out)
    builder = Builder(Book(args.root), out, args.repo, args.sha)
    builder.build()
    pages = len(list(out.glob("*.html")))
    print(f"textbook written to {out} ({pages} pages, {builder.pending_count} items not yet in the book)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
