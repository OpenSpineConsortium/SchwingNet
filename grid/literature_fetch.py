"""Fetch the papers of one reading list onto the grid, each from a source that allows it, and say
which ones it could not get, so the owner can fetch those by hand (his word of 2026-10-27).

A list is a CSV under grid/literature/ with the columns id, doi, pmcid and held. The tool runs in
two passes inside one Slurm job (grid/literature.sbatch, queued by the gate word `literature <list>`):

    plan   asks each source what it holds for each paper and writes the plan, meta/PLAN.json, under
           the landing; no paper's bytes land. Its last line is the size rule's: the bytes the plan
           may write, what is still to land and how they were read (grid/size-rule.sh).
    fetch  downloads what the plan names, each file bounded by the size its server stated or, where
           it stated none, by a cap, then writes the landing's INDEX.md and README.md and the report.

The sources, in order. A paper the list marks held is not fetched. A PMC id in the open-access
subset gets Europe PMC's JATS XML and a PDF (the PMC open-access service's link, else Europe PMC's).
A DOI of Elsevier's (10.1016/) goes through Elsevier's article API with the owner's key and
institutional token, after its entitlement check, whether or not PMC holds it too, so the answer
shows what the key and token reach. Any other DOI with no PDF yet gets the open-access PDF Semantic
Scholar names, unless that link lies on a host this tool never scripts: PMC's and Europe PMC's own
article pages, whose terms bar automated retrieval outside the open-access subset, and Elsevier's,
which is read only through its API. Every paper with no text after that is listed in the report
with the reason, for the owner.

The keys: Elsevier's from ~/.elsevier/token.env (ELSEVIER_API_KEY, ELSEVIER_INSTTOKEN) and Semantic
Scholar's from ~/.fluorocap/credentials.env (S2_API_KEY), as hpcworker's gate word key writes them,
each read only from a plain file of this account's that no one else may read. A key goes only in
its service's request headers (X-ELS-APIKey and X-ELS-Insttoken, x-api-key), to that service's own
address, never through a redirect, and never into a file, a line of output or the report. Elsevier's
text stays on the grid, as the owner told Elsevier: the landing is 0700, every file in it 0600, and
its README.md says what each file may be used for. Standard library only; Python 3.8 or later.

    python3 grid/literature_fetch.py plan --list grid/literature/synthetic_spine.csv \
        --landing <data>/literature_synthetic_spine
    python3 grid/literature_fetch.py fetch --landing <data>/literature_synthetic_spine \
        --report grid/logs/LITERATURE-synthetic_spine.md
"""

import argparse
import csv
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
from pathlib import Path

USER_AGENT = "SchwingNet-literature/1 (one research job on a university grid)"
CAP_BYTES = 50 * 10**6
SMALL_BYTES = 4 * 10**6
TIMEOUT_SECONDS = 60
PAUSE_SECONDS = 1.0
DEFAULTS = {
    "epmc": "https://www.ebi.ac.uk/europepmc/webservices/rest",
    "pmc_oa": "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
    "elsevier": "https://api.elsevier.com/content/article",
    "s2": "https://api.semanticscholar.org/graph/v1/paper",
}
# Hosts whose links from Semantic Scholar this tool never follows (the module's docstring says why).
UNSCRIPTED_HOSTS = ("ncbi.nlm.nih.gov", "europepmc.org", "ebi.ac.uk", "sciencedirect.com", "elsevier.com")
ELSEVIER_PREFIX = "10.1016/"
ELSEVIER_FILE = (".elsevier", "token.env")
S2_FILE = (".fluorocap", "credentials.env")
ID_SHAPE = re.compile(r"^[a-z0-9_]{1,40}$")
DOI_SHAPE = re.compile(r"^10\.[0-9]{4,9}/[!-~]{1,200}$")
PMC_SHAPE = re.compile(r"^PMC[0-9]{1,9}$")
KEY_SHAPE = re.compile(r"^[!-~]{8,1024}$")
REFUSED = 2


class ListError(ValueError):
    """A reading list the tool will not read, with the line that stopped it."""


class TooLarge(Exception):
    """A body that passed the bound its plan gave it."""


class Answer:
    """What one request got: the status (0 where no answer came), the body, the headers and, for
    anything but a plain success, a short reason."""

    def __init__(self, code, body=b"", headers=None, reason=""):
        self.code = code
        self.body = body
        self.headers = headers
        self.reason = reason or f"http {code}"


def base(service):
    """The service's address: its default, or a test's stand-in, which only a loopback address may
    be, so that no setting can send a key anywhere but the service itself."""
    given = os.environ.get("LITERATURE_" + service.upper(), "")
    if given.startswith("http://127.0.0.1:"):
        return given.rstrip("/")
    return DEFAULTS[service]


def plain(text, limit=80):
    """TEXT with nothing but letters, digits, spaces and . _ - left, cut to LIMIT, for a reason
    that a server or an exception wrote."""
    return re.sub(r"[^A-Za-z0-9 ._-]", "", str(text))[:limit].strip()


def loopback(url):
    """A test's stand-in address, which a link from a real service never is."""
    return url.startswith("http://127.0.0.1:")


def pause():
    time.sleep(float(os.environ.get("LITERATURE_PAUSE", PAUSE_SECONDS)))


def read_list(path):
    """The rows of a reading list, each id once, each DOI and PMC id in its shape."""
    rows, seen = [], set()
    with open(path, encoding="ascii", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["id", "doi", "pmcid", "held"]:
            raise ListError("the header is not id,doi,pmcid,held")
        for number, row in enumerate(reader, start=2):
            row = {name: (row.get(name) or "").strip() for name in ("id", "doi", "pmcid", "held")}
            if not ID_SHAPE.match(row["id"]) or row["id"] in seen:
                raise ListError(f"line {number}: an id is lower-case letters, digits and _, each once")
            if row["doi"] and not DOI_SHAPE.match(row["doi"]):
                raise ListError(f"line {number}: {row['id']}'s DOI is not in a DOI's shape")
            if row["pmcid"] and not PMC_SHAPE.match(row["pmcid"]):
                raise ListError(f"line {number}: {row['id']}'s PMC id is not PMC and digits")
            seen.add(row["id"])
            rows.append(row)
    return rows


def private_values(path, names):
    """(values, why): the NAME=value lines among NAMES of a plain file of this account's that no one
    else may read, or no values and why the file was not read; a link is not followed."""
    try:
        handle = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return {}, "no file"
    except OSError as error:
        return {}, "not read: " + plain(error.__class__.__name__)
    with os.fdopen(handle, encoding="utf-8", errors="replace") as text:
        info = os.fstat(text.fileno())
        if not stat.S_ISREG(info.st_mode):
            return {}, "not a plain file"
        if info.st_uid != os.getuid():
            return {}, "another account's file"
        if info.st_mode & 0o077:
            return {}, "others may read it, so it is not used"
        values = {}
        for line in text:
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            name, sep, value = line.partition("=")
            value = value.strip().strip("'\"")
            if sep and name.strip() in names and KEY_SHAPE.match(value):
                values[name.strip()] = value
    return values, "read"


def read_keys(home=None):
    """(keys, words): the keys the grid holds, and what was found of them, in words with no value."""
    home = Path(home or Path.home())
    elsevier, elsevier_why = private_values(home.joinpath(*ELSEVIER_FILE), ("ELSEVIER_API_KEY", "ELSEVIER_INSTTOKEN"))
    s2, s2_why = private_values(home.joinpath(*S2_FILE), ("S2_API_KEY",))
    keys = dict(elsevier, **s2)
    if "ELSEVIER_API_KEY" in keys:
        elsevier_words = "key and insttoken" if "ELSEVIER_INSTTOKEN" in keys else "key alone, no insttoken"
    else:
        elsevier_words = "none (" + (elsevier_why if elsevier_why != "read" else "no key line") + ")"
    s2_words = "key" if "S2_API_KEY" in keys else "none (" + (s2_why if s2_why != "read" else "no key line") + ")"
    return keys, {"elsevier": elsevier_words, "s2": s2_words}


def headers_for(keyed, keys, accept=""):
    """The request headers of a call to KEYED's service: the key, and Elsevier's token, only there."""
    headers = {"Accept": accept} if accept else {}
    if keyed == "elsevier":
        headers["X-ELS-APIKey"] = keys["ELSEVIER_API_KEY"]
        if keys.get("ELSEVIER_INSTTOKEN"):
            headers["X-ELS-Insttoken"] = keys["ELSEVIER_INSTTOKEN"]
    elif keyed == "s2" and keys.get("S2_API_KEY"):
        headers["x-api-key"] = keys["S2_API_KEY"]
    return headers


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect of a keyed call, so a key never travels to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def opener(keyed):
    return urllib.request.build_opener(NoRedirect()) if keyed else urllib.request.build_opener()


def check_target(url, keyed):
    """A keyed call goes only under its own service's address."""
    if keyed and not url.startswith(base(keyed) + "/"):
        raise ValueError(f"a {keyed} key is sent only to {base(keyed)}")


def request_of(url, headers, method="GET"):
    headers = dict(headers or {})
    headers["User-Agent"] = USER_AGENT
    return urllib.request.Request(url, headers=headers, method=method)


def ask(url, headers=None, keyed="", method="GET", limit=SMALL_BYTES):
    """One small request, read into memory and never written: an Answer. A 429 is asked twice more."""
    check_target(url, keyed)
    for attempt in range(3):
        try:
            with opener(keyed).open(request_of(url, headers, method), timeout=TIMEOUT_SECONDS) as answer:
                body = b"" if method == "HEAD" else answer.read(limit + 1)
                return Answer(answer.getcode(), body[:limit], answer.headers, "body cut" if len(body) > limit else "ok")
        except urllib.error.HTTPError as error:
            body = error.read(64 * 1024) if error.fp else b""
            if error.code == 429 and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            reason = "redirect refused" if 300 <= error.code < 400 and keyed else f"http {error.code}"
            return Answer(error.code, body, error.headers, reason)
        except (urllib.error.URLError, OSError, ValueError) as error:
            return Answer(0, b"", None, plain(getattr(error, "reason", error)) or error.__class__.__name__)
    return Answer(429, b"", None, "http 429")


def json_of(answer):
    """The JSON object an answer holds, else None."""
    try:
        data = json.loads(answer.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def failed(service, answer):
    """Why a call to SERVICE gave nothing to read."""
    return f"{service}: {answer.reason if answer.code != 200 else 'an answer that is not JSON'}"


def item(row, source, kind, urls, keyed="", accept="", licence=""):
    """One file the plan may download: where from, how, and the name it lands under."""
    return {"id": row["id"], "source": source, "kind": kind, "urls": urls, "keyed": keyed, "accept": accept,
            "licence": plain(licence, 120), "file": f"text/{row['id']}/{row['id']}.{source}.{kind}"}


def europe_pmc_record(pmcid):
    """(record, why): Europe PMC's core record of PMCID, or None and why."""
    query = urllib.parse.urlencode({"query": f"PMCID:{pmcid}", "resultType": "core", "format": "json"})
    answer = ask(f"{base('epmc')}/search?{query}")
    pause()
    data = json_of(answer) if answer.code == 200 else None
    if data is None:
        return None, failed("Europe PMC search", answer)
    for record in data.get("resultList", {}).get("result", []):
        if record.get("pmcid") == pmcid:
            return record, ""
    return None, "Europe PMC lists no record of it"


def oa_service_pdfs(pmcid):
    """The PDF links PMC's open-access service gives PMCID, as https addresses."""
    answer = ask(f"{base('pmc_oa')}?id={pmcid}")
    pause()
    if answer.code != 200:
        return []
    try:
        root = ElementTree.fromstring(answer.body)
    except ElementTree.ParseError:
        return []
    links = []
    for link in root.iter("link"):
        href = link.get("href", "")
        if link.get("format") == "pdf" and (href.startswith(("ftp://ftp.ncbi.nlm.nih.gov/", "https://")) or loopback(href)):
            links.append("https://" + href[len("ftp://"):] if href.startswith("ftp://") else href)
    return links


def europe_pmc_pdfs(record):
    """Europe PMC's own open-access PDF links in its record."""
    links = []
    for entry in record.get("fullTextUrlList", {}).get("fullTextUrl", []):
        url = entry.get("url", "")
        host = urllib.parse.urlsplit(url).hostname or ""
        on_europe_pmc = url.startswith("https://") and (host == "europepmc.org" or host.endswith(".europepmc.org"))
        if entry.get("documentStyle") == "pdf" and entry.get("availabilityCode") == "OA" and (on_europe_pmc or loopback(url)):
            links.append(url)
    return links


def pmc_items(row):
    """The open-access copies PMC holds of ROW, and why there are none where there are none."""
    record, why = europe_pmc_record(row["pmcid"])
    if record is None:
        return [], [why]
    if record.get("isOpenAccess") != "Y":
        return [], ["PMC holds it outside the open-access subset, which no script may fetch"]
    licence = record.get("license", "")
    items = [item(row, "epmc", "xml", [f"{base('epmc')}/{row['pmcid']}/fullTextXML"], licence=licence)]
    pdfs = oa_service_pdfs(row["pmcid"]) + europe_pmc_pdfs(record)
    if pdfs:
        items.append(item(row, "pmc", "pdf", pdfs, licence=licence))
    return items, []


def elsevier_status(answer):
    """Elsevier's own word for an answer, from its X-ELS-Status header or its error's status code."""
    said = answer.headers.get("X-ELS-Status", "") if answer.headers is not None else ""
    error = (json_of(answer) or {}).get("service-error", {})
    error = error.get("status", {}) if isinstance(error, dict) else {}
    word = plain(error.get("statusCode", "") if isinstance(error, dict) else "") or plain(said)
    return f" ({word})" if word else ""


def entitled(data):
    """Whether Elsevier's entitlement answer says the token's institution may read the full text."""
    found = (data or {}).get("entitlement-response", {})
    found = found.get("document-entitlement", {}) if isinstance(found, dict) else {}
    if isinstance(found, list):
        found = found[0] if found else {}
    return isinstance(found, dict) and str(found.get("entitled", "")).lower() == "true"


def elsevier_items(row, keys, words):
    """Elsevier's XML and PDF of ROW where its entitlement check says the token reaches them."""
    if "ELSEVIER_API_KEY" not in keys:
        return [], [f"Elsevier: no key on the grid, {words['elsevier']}"]
    doi = urllib.parse.quote(row["doi"], safe="/")
    answer = ask(f"{base('elsevier')}/entitlement/doi/{doi}", headers_for("elsevier", keys, "application/json"),
                 keyed="elsevier")
    pause()
    if answer.code != 200:
        return [], [f"Elsevier entitlement check: {answer.reason}{elsevier_status(answer)}"]
    if not entitled(json_of(answer)):
        return [], ["Elsevier: not entitled to the full text under the key and insttoken"]
    url = f"{base('elsevier')}/doi/{doi}"
    return [item(row, "elsevier", "xml", [url + "?view=FULL"], keyed="elsevier", accept="text/xml"),
            item(row, "elsevier", "pdf", [url], keyed="elsevier", accept="application/pdf")], []


def unscripted(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == name or host.endswith("." + name) for name in UNSCRIPTED_HOSTS)


def s2_items(row, keys):
    """The open-access PDF Semantic Scholar names for ROW's DOI, where it lies on a host scripted here."""
    doi = urllib.parse.quote(row["doi"], safe="/")
    keyed = "s2" if "S2_API_KEY" in keys else ""
    answer = ask(f"{base('s2')}/DOI:{doi}?fields=isOpenAccess,openAccessPdf", headers_for(keyed, keys), keyed=keyed)
    pause()
    data = json_of(answer) if answer.code == 200 else None
    if data is None:
        return [], [failed("Semantic Scholar", answer)]
    found = data.get("openAccessPdf") or {}
    url = found.get("url") or ""
    if not url.startswith(("https://", "http://")):
        return [], ["no open-access copy that Semantic Scholar knows of"]
    host = plain(urllib.parse.urlsplit(url).hostname or "", 60)
    if unscripted(url):
        return [], [f"Semantic Scholar's copy is on {host}, not scripted here"]
    return [item(row, "s2", "pdf", [url], licence=found.get("license") or found.get("status") or "")], []


def plan_paper(row, keys, words):
    """(items, why): what the sources offer for one paper, and why each offered nothing."""
    if row["held"]:
        return [], ["held already: " + row["held"]]
    if not row["doi"] and not row["pmcid"]:
        return [], ["no DOI or PMC id was found for it"]
    items, why = [], []
    if row["pmcid"]:
        got, said = pmc_items(row)
        items, why = items + got, why + said
    if row["doi"].startswith(ELSEVIER_PREFIX):
        got, said = elsevier_items(row, keys, words)
        items, why = items + got, why + said
    if row["doi"] and not any(entry["kind"] == "pdf" for entry in items):
        got, said = s2_items(row, keys)
        items, why = items + got, why + said
    return items, why


def stated_size(url):
    """The size a server states for URL to a HEAD, or None."""
    answer = ask(url, method="HEAD")
    length = answer.headers.get("Content-Length", "") if answer.code == 200 and answer.headers is not None else ""
    return int(length) if length.isdigit() and len(length) <= 15 else None


def bound_items(items, landing):
    """Each item's bound and whether the landing has it already: a keyed call is never sized by a
    HEAD of its own, and a file no server states a size for is bounded by the cap."""
    for entry in items:
        target = landing / entry["file"]
        if target.is_file() and target.stat().st_size > 0 and not what_it_holds(entry, target):
            entry.update(have=target.stat().st_size, bound=0, stated=True)
            continue
        sizes = [None] if entry["keyed"] else [stated_size(url) for url in entry["urls"]]
        entry["stated"] = all(size is not None for size in sizes)
        entry["bound"] = max(sizes) if entry["stated"] else CAP_BYTES
        entry["have"] = 0
    return items


def size_words(items):
    """The size rule's HOW, in lower-case words and digits alone."""
    to_land = [entry for entry in items if not entry["have"]]
    stated = sum(1 for entry in to_land if entry["stated"])
    capped = len(to_land) - stated
    return (f"{stated} sizes the servers stated and a cap of {CAP_BYTES // 10**6} mb for each of {capped} "
            f"files that state none; {len(items) - len(to_land)} files held already")


def private_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def write_private(path, text):
    """TEXT into PATH, 0600, written whole and renamed into place."""
    part = path.with_name(path.name + ".part")
    handle = os.open(str(part), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(text)
    os.replace(str(part), str(path))


def run_plan(list_path, landing, home=None):
    """The plan of one list written under LANDING; the size rule's line, printed last."""
    rows = read_list(list_path)
    keys, words = read_keys(home)
    papers, items = [], []
    for row in rows:
        got, why = plan_paper(row, keys, words)
        papers.append(dict(row, why=why))
        items.extend(got)
    private_folder(landing)
    private_folder(landing / "meta")
    bound_items(items, landing)
    plan = {"list": Path(list_path).stem, "papers": papers, "items": items, "keys": words, "cap": CAP_BYTES}
    write_private(landing / "meta" / "PLAN.json", json.dumps(plan, indent=1) + "\n")
    need = sum(entry["bound"] for entry in items)
    total = need + sum(entry["have"] for entry in items)
    print(f"plan: {len(rows)} papers, {len(items)} files offered; Elsevier key: {words['elsevier']}; "
          f"Semantic Scholar key: {words['s2']}")
    print(f"{total} {need} {size_words(items)}")
    return 0


def write_body(answer, part, bound):
    """The body of an open answer into PART, 0600, at most BOUND bytes; the bytes written."""
    written = 0
    handle = os.open(str(part), os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(handle, "wb") as out:
        os.fchmod(out.fileno(), 0o600)
        while True:
            block = answer.read(1 << 16)
            if not block:
                return written
            written += len(block)
            if written > bound:
                raise TooLarge()
            out.write(block)


def download(url, target, bound, headers=None, keyed=""):
    """(bytes, why): URL's body landed at TARGET through TARGET.part, at most BOUND bytes; nothing
    is left behind where it fails."""
    check_target(url, keyed)
    part = target.with_name(target.name + ".part")
    try:
        with opener(keyed).open(request_of(url, headers), timeout=TIMEOUT_SECONDS) as answer:
            written = write_body(answer, part, bound)
    except TooLarge:
        why = f"larger than its bound of {bound} bytes, so deleted"
    except urllib.error.HTTPError as error:
        why = "redirect refused" if 300 <= error.code < 400 and keyed else f"http {error.code}"
    except (urllib.error.URLError, OSError, ValueError) as error:
        why = plain(getattr(error, "reason", error)) or error.__class__.__name__
    else:
        os.replace(str(part), str(target))
        return written, ""
    if part.exists():
        part.unlink()
    return 0, why


def what_it_holds(entry, path):
    """'' where the file is what its item promised, else why not: a PDF starts %PDF-, an XML file
    with <, and an XML file holds the article's body, not only its abstract."""
    with open(str(path), "rb") as handle:
        data = handle.read(CAP_BYTES + 1)
    if entry["kind"] == "pdf":
        return "" if data.startswith(b"%PDF-") else "not a PDF (the server sent a page instead)"
    if not data.lstrip().startswith(b"<"):
        return "not XML"
    if entry["source"] == "elsevier":
        whole = b"<ce:sections" in data or b"<xocs:rawtext" in data
        return "" if whole else "abstract only: Elsevier sent no full text"
    return "" if b"<body" in data else "no article body in the XML"


def fetch_item(entry, landing, keys):
    """Land one item from the first of its addresses that gives what it promised."""
    target = landing / entry["file"]
    private_folder(target.parent)
    if entry.get("have"):
        return dict(entry, got=entry["have"], why=what_it_holds(entry, target) if target.is_file() else "gone since the plan")
    if entry["keyed"] == "elsevier" and "ELSEVIER_API_KEY" not in keys:
        return dict(entry, got=0, why="the Elsevier key was gone by the fetch")
    headers = headers_for(entry["keyed"], keys, entry["accept"])
    why = "no address"
    for url in entry["urls"]:
        written, why = download(url, target, entry["bound"], headers, entry["keyed"])
        pause()
        if not why:
            why = what_it_holds(entry, target)
            if not why or why.startswith("abstract only"):
                return dict(entry, got=written, why=why)
            target.unlink()
    return dict(entry, got=0, why=why)


def has_text(results):
    return any(result["got"] and not result["why"] for result in results)


def kb(count):
    """A byte count as KB, rounded up, or MB."""
    return f"{(count + 999) // 1000} KB" if count < 10**6 else f"{count / 10**6:.1f} MB"


def paper_lines(paper, results):
    """One line of the report for a paper: what landed, or why nothing did, and what each source
    that gave nothing said, so a paper got from PMC still shows Elsevier's answer."""
    if paper["held"]:
        return f"- {paper['id']}: held already, in {paper['held']}"
    reasons = list(paper["why"]) + [f"{r['source']} {r['kind']}: {r['why']}" for r in results if r["why"]]
    if has_text(results):
        got = ", ".join(f"{r['source']} {r['kind']} {kb(r['got'])}" for r in results if r["got"] and not r["why"])
        return f"- {paper['id']}: got {got}" + "".join(f"; {reason}" for reason in reasons)
    return f"- {paper['id']}: not got; " + "; ".join(reasons or ["no source offered a copy"])


def links_of(paper):
    links = []
    if paper["doi"]:
        links.append("https://doi.org/" + paper["doi"])
    if paper["pmcid"]:
        links.append(f"https://pmc.ncbi.nlm.nih.gov/articles/{paper['pmcid']}/")
    return " ".join(links) or "no link: search the citation in spine-program synthetic_spine/sources.csv"


def index_text(plan, results_of):
    """The landing's INDEX.md: each paper and the files that hold it, for the reader on the grid."""
    lines = [f"# {plan['list']}: what this landing holds", "",
             "Each paper by its id in the list, with its files under text/<id>/ and where they came from.", ""]
    for paper in plan["papers"]:
        results = results_of[paper["id"]]
        lines.append(paper_lines(paper, results))
        for result in results:
            if result["got"]:
                licence = f", licence {result['licence']}" if result["licence"] else ""
                note = f" ({result['why']})" if result["why"] else ""
                lines.append(f"  - {result['file']}: {result['source']} {result['kind']}{licence}{note}")
    return "\n".join(lines) + "\n"


README = """# The papers of this reading list, kept on the grid

Fetched by SchwingNet's grid/literature_fetch.py (the gate word literature) for the owner's research.
INDEX.md lists every paper and its files under text/<id>/.

- Files named .elsevier. came through Elsevier's API under the owner's key and Wayne State's
  institutional token. Elsevier's terms for them: they stay on this grid, are read here only, are never
  copied into git, an issue, a chat, a public place or a browser, and are never used to train a model.
- Files named .epmc. or .pmc. are from PMC's open-access subset and carry the licence INDEX.md gives.
- Files named .s2. are the open-access copies Semantic Scholar names; their licence is as INDEX.md gives,
  and a copy with no licence is for reading only.

The folder is 0700 and every file 0600: only the owner's account, and the Claude sessions it runs on the
grid, read them.
"""


def report_text(plan, results_of):
    """The report the gate word prints: counts, the papers not got with their links, every paper."""
    got = [p for p in plan["papers"] if has_text(results_of[p["id"]])]
    held = [p for p in plan["papers"] if p["held"]]
    missing = [p for p in plan["papers"] if p not in got and p not in held]
    files = [r for results in results_of.values() for r in results if r["got"]]
    lines = [f"- list {plan['list']}: {len(plan['papers'])} papers; {len(got)} got, {len(held)} held already, "
             f"{len(missing)} not got",
             f"- keys on the grid: Elsevier {plan['keys']['elsevier']}; Semantic Scholar {plan['keys']['s2']}",
             f"- landed: {len(files)} files, {kb(sum(r['got'] for r in files))}, under the landing "
             f"literature_{plan['list']} of the data root (0700, files 0600; INDEX.md lists them)",
             "", "## Not got: for the owner to fetch by hand", ""]
    for paper in missing:
        lines.append(paper_lines(paper, results_of[paper["id"]]))
        lines.append(f"  {links_of(paper)}")
    lines += ["", "## Every paper", ""]
    lines += [paper_lines(paper, results_of[paper["id"]]) for paper in plan["papers"]]
    return "\n".join(lines) + "\n"


def run_fetch(landing, report, home=None):
    """Land what the plan names, then write INDEX.md, README.md and the report."""
    plan = json.loads((landing / "meta" / "PLAN.json").read_text(encoding="utf-8"))
    keys, _ = read_keys(home)
    results_of = {paper["id"]: [] for paper in plan["papers"]}
    for entry in plan["items"]:
        results_of[entry["id"]].append(fetch_item(entry, landing, keys))
    write_private(landing / "INDEX.md", index_text(plan, results_of))
    write_private(landing / "README.md", README)
    text = report_text(plan, results_of)
    with open(str(report), "a", encoding="ascii", errors="replace") as out:
        out.write(text)
    got = sum(1 for paper in plan["papers"] if has_text(results_of[paper["id"]]))
    print(f"fetch: {got} of {len(plan['papers'])} papers have their text on the grid")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    steps = parser.add_subparsers(dest="step", required=True)
    plan = steps.add_parser("plan", help="ask the sources and write the plan; print the size rule's line")
    plan.add_argument("--list", required=True, type=Path)
    plan.add_argument("--landing", required=True, type=Path)
    fetch = steps.add_parser("fetch", help="land what the plan names and write the report")
    fetch.add_argument("--landing", required=True, type=Path)
    fetch.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)
    if sys.version_info < (3, 8):
        print("literature_fetch: Python 3.8 or later")
        return REFUSED
    os.umask(0o077)
    try:
        if args.step == "plan":
            return run_plan(args.list, args.landing)
        return run_fetch(args.landing, args.report)
    except (ListError, OSError, ValueError) as error:
        print(f"literature_fetch {args.step}: {plain(error, 200)}")
        return REFUSED


if __name__ == "__main__":
    sys.exit(main())
