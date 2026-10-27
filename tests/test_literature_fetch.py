"""grid/literature_fetch.py and grid/literature.sbatch against stand-ins for Europe PMC, PMC's
open-access service, Elsevier's article API and Semantic Scholar on a loopback server: each paper
lands from the source that allows it or is listed with the reason it did not; Elsevier's key and
token travel only in Elsevier's request headers, Semantic Scholar's only in its own, never through a
redirect, and never into a file, the output or the report; the landing is 0700 and every file 0600;
a body past its bound or one that is not what it promised is deleted; the job lands nothing until
the size rule admits the plan. Standard library only.

    python3 -m unittest tests/test_literature_fetch.py
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
ELSEVIER_KEY = "els0key0aaaa1111bbbb2222cccc3333"
ELSEVIER_TOKEN = "insttoken9zzzz8888yyyy7777xxxx6666"
S2_KEY = "s2keyQQQQ5555RRRR4444SSSS3333TTTT"
KEYS = (ELSEVIER_KEY, ELSEVIER_TOKEN, S2_KEY)
PDF = b"%PDF-1.7\n" + b"x" * 2000
LIST = """id,doi,pmcid,held
heldone,10.1097/held.1,,bordercall archive/bordercall/reference/papers
oapaper,10.1007/oa.1,PMC111,
closedpmc,10.1007/closed.1,PMC222,
elsgot,10.1016/j.ok.1,,
elsabs,10.1016/j.abs.1,,
elsno,10.1016/j.no.1,,
redir,10.1016/j.redir.1,,
s2got,10.1234/s2.got,,
s2html,10.1234/s2.html,,
liar,10.1234/s2.liar,,
nothing,,,
"""


def load_tool():
    spec = importlib.util.spec_from_file_location("literature_fetch", ROOT / "grid" / "literature_fetch.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class Services(BaseHTTPRequestHandler):
    """Every service the tool asks, by the first part of the path; each request is noted."""

    calls = []

    def log_message(self, *args):
        pass

    def answer(self, code, body=b"", kind="application/json", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        if "Content-Length" not in (headers or {}):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        Services.calls.append((self.command, self.path, {name.lower(): value for name, value in self.headers.items()}))
        parts = urlsplit(self.path)
        path, query = unquote(parts.path), parse_qs(parts.query)
        if path == "/epmc/search":
            return self.europe_pmc_search(query["query"][0].split(":", 1)[1])
        if path.startswith("/epmc/") and path.endswith("/fullTextXML"):
            return self.answer(200, b"<article><front/><body><p>text</p></body></article>", "application/xml")
        if path == "/pmc_oa":
            return self.oa_service(query["id"][0])
        if path.startswith("/elsevier/entitlement/doi/"):
            return self.entitlement(path[len("/elsevier/entitlement/doi/"):])
        if path.startswith("/elsevier/doi/"):
            return self.elsevier_article(path[len("/elsevier/doi/"):])
        if path.startswith("/s2/DOI:"):
            return self.semantic_scholar(path[len("/s2/DOI:"):])
        if path.startswith("/files/"):
            return self.file(path[len("/files/"):])
        return self.answer(404, b"{}")

    def base(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def europe_pmc_search(self, pmcid):
        record = {"pmcid": pmcid, "isOpenAccess": "Y" if pmcid == "PMC111" else "N", "license": "cc by",
                  "fullTextUrlList": {"fullTextUrl": [
                      {"documentStyle": "pdf", "availabilityCode": "OA", "url": f"{self.base()}/files/epmc.pdf"},
                      {"documentStyle": "html", "availabilityCode": "OA", "url": "https://example.org/x"}]}}
        self.answer(200, json.dumps({"resultList": {"result": [record]}}).encode())

    def oa_service(self, pmcid):
        if pmcid != "PMC111":
            return self.answer(200, b'<OA><error code="idIsNotOpenAccess">no</error></OA>', "text/xml")
        body = f'<OA><records><record id="{pmcid}"><link format="tgz" href="{self.base()}/files/a.tgz"/>' \
               f'<link format="pdf" href="{self.base()}/files/oa.pdf"/></record></records></OA>'
        self.answer(200, body.encode(), "text/xml")

    def keyed_as_elsevier(self):
        return self.headers.get("X-ELS-APIKey") == ELSEVIER_KEY and self.headers.get("X-ELS-Insttoken") == ELSEVIER_TOKEN

    def entitlement(self, doi):
        if not self.keyed_as_elsevier():
            return self.answer(401, b'{"service-error":{"status":{"statusCode":"AUTHENTICATION_ERROR"}}}')
        if doi == "10.1016/j.redir.1":
            return self.answer(302, b"", headers={"Location": f"{self.base()}/elsewhere"})
        verdict = doi in ("10.1016/j.ok.1", "10.1016/j.abs.1")
        body = {"entitlement-response": {"document-entitlement": {"entitled": verdict, "status": "found"}}}
        self.answer(200, json.dumps(body).encode())

    def elsevier_article(self, doi):
        if not self.keyed_as_elsevier():
            return self.answer(401, b"{}")
        wants_pdf = self.headers.get("Accept") == "application/pdf"
        if doi == "10.1016/j.abs.1":
            if wants_pdf:
                return self.answer(403, b"{}")
            return self.answer(200, b"<full-text-retrieval-response><coredata/></full-text-retrieval-response>", "text/xml")
        if wants_pdf:
            return self.answer(200, PDF, "application/pdf")
        return self.answer(200, b"<full-text-retrieval-response><originalText><xocs:doc><ce:sections>"
                                b"<ce:para>t</ce:para></ce:sections></xocs:doc></originalText>"
                                b"</full-text-retrieval-response>", "text/xml")

    def semantic_scholar(self, doi):
        links = {"10.1007/closed.1": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC222/pdf/x.pdf",
                 "10.1234/s2.got": f"{self.base()}/files/s2got.pdf",
                 "10.1234/s2.html": f"{self.base()}/files/page.html",
                 "10.1234/s2.liar": f"{self.base()}/files/liar.pdf"}
        found = {"url": links[doi], "status": "GREEN", "license": "CCBY"} if doi in links else None
        self.answer(200, json.dumps({"isOpenAccess": found is not None, "openAccessPdf": found}).encode())

    def file(self, name):
        if name == "page.html":
            return self.answer(200, b"<html>sign in</html>", "text/html")
        if name == "liar.pdf":
            return self.answer(200, PDF if self.command == "GET" else b"", "application/pdf", {"Content-Length": "10"}
                               if self.command == "HEAD" else None)
        return self.answer(200, PDF, "application/pdf")


def serve(test):
    Services.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Services)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    return f"http://127.0.0.1:{server.server_address[1]}"


def service_env(address):
    return {"LITERATURE_EPMC": f"{address}/epmc", "LITERATURE_PMC_OA": f"{address}/pmc_oa",
            "LITERATURE_ELSEVIER": f"{address}/elsevier", "LITERATURE_S2": f"{address}/s2", "LITERATURE_PAUSE": "0"}


def home_with_keys(folder, elsevier=True, s2=True, mode=0o600):
    """A home whose key files are as hpcworker's gate word key writes them."""
    home = Path(folder) / "home"
    if elsevier:
        (home / ".elsevier").mkdir(parents=True, mode=0o700)
        path = home / ".elsevier" / "token.env"
        path.write_text(f"ELSEVIER_API_KEY={ELSEVIER_KEY}\nELSEVIER_INSTTOKEN={ELSEVIER_TOKEN}\n", encoding="utf-8")
        path.chmod(mode)
    if s2:
        (home / ".fluorocap").mkdir(parents=True, mode=0o700)
        path = home / ".fluorocap" / "credentials.env"
        path.write_text(f"KAGGLE_USERNAME=someone\nS2_API_KEY={S2_KEY}\n", encoding="utf-8")
        path.chmod(0o600)
    home.mkdir(exist_ok=True)
    return home


class FetchToolTest(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.address = serve(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.list = self.tmp / "testlist.csv"
        self.list.write_text(LIST, encoding="ascii")
        self.landing = self.tmp / "data" / "literature_testlist"
        self.report = self.tmp / "LITERATURE-testlist.md"
        self.home = home_with_keys(self.tmp)
        saved = dict(os.environ)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        os.environ.update(service_env(self.address), HOME=str(self.home))

    def run_step(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.tool.main(list(args))
        return code, out.getvalue()

    def plan(self):
        return self.run_step("plan", "--list", str(self.list), "--landing", str(self.landing))

    def fetch(self):
        return self.run_step("fetch", "--landing", str(self.landing), "--report", str(self.report))

    def lines_of(self, report):
        return {line.split(":", 1)[0][2:]: line for line in report.splitlines() if line.startswith("- ") and ":" in line}

    def test_each_paper_lands_from_a_source_that_allows_it_or_is_named_with_why(self):
        code, said = self.plan()
        self.assertEqual(code, 0, said)
        total, need, how = said.strip().splitlines()[-1].split(" ", 2)
        self.assertGreater(int(need), 0)
        self.assertEqual(int(total), int(need))
        self.assertRegex(how, r"^[a-z0-9 ;]+$")
        code, said = self.fetch()
        self.assertEqual(code, 0, said)
        report = self.report.read_text(encoding="ascii")
        every = report.split("## Every paper", 1)[1]
        line = self.lines_of(every)
        self.assertIn("got epmc xml", line["oapaper"])
        self.assertIn("pmc pdf", line["oapaper"])
        self.assertIn("got elsevier xml", line["elsgot"])
        self.assertIn("elsevier pdf", line["elsgot"])
        self.assertIn("not got; elsevier xml: abstract only", line["elsabs"])
        self.assertIn("elsevier pdf: http 403", line["elsabs"])
        self.assertIn("not got; Elsevier: not entitled to the full text under the key and insttoken", line["elsno"])
        self.assertIn("no open-access copy that Semantic Scholar knows of", line["elsno"])
        self.assertIn("PMC holds it outside the open-access subset, which no script may fetch", line["closedpmc"])
        self.assertIn("Semantic Scholar's copy is on www.ncbi.nlm.nih.gov, not scripted here", line["closedpmc"])
        self.assertIn("Elsevier entitlement check: redirect refused", line["redir"])
        self.assertIn("got s2 pdf", line["s2got"])
        self.assertIn("s2 pdf: not a PDF", line["s2html"])
        self.assertIn("s2 pdf: larger than its bound of 10 bytes, so deleted", line["liar"])
        self.assertIn("no DOI or PMC id", line["nothing"])
        self.assertIn("held already, in bordercall archive", line["heldone"])
        missing = report.split("## Not got", 1)[1].split("## Every paper", 1)[0]
        for paper in ("closedpmc", "elsabs", "elsno", "redir", "s2html", "liar", "nothing"):
            self.assertIn(f"- {paper}: not got", missing)
        for paper in ("oapaper", "elsgot", "s2got", "heldone"):
            self.assertNotIn(f"- {paper}:", missing)
        self.assertIn("https://doi.org/10.1016/j.no.1", missing)
        self.assertIn("https://pmc.ncbi.nlm.nih.gov/articles/PMC222/", missing)
        self.assertIn("11 papers; 3 got, 1 held already, 7 not got", report)
        self.assertIn("keys on the grid: Elsevier key and insttoken; Semantic Scholar key", report)

    def test_the_landing_is_the_owners_alone_and_holds_only_what_was_promised(self):
        self.plan()
        self.fetch()
        self.assertEqual(self.landing.stat().st_mode & 0o777, 0o700)
        files = [path for path in self.landing.rglob("*") if path.is_file()]
        self.assertTrue(files)
        for path in files:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600, path)
        for path in self.landing.rglob("*"):
            if path.is_dir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o700, path)
        names = sorted(str(path.relative_to(self.landing)) for path in files)
        self.assertIn("text/elsgot/elsgot.elsevier.pdf", names)
        self.assertIn("text/elsgot/elsgot.elsevier.xml", names)
        self.assertIn("text/oapaper/oapaper.epmc.xml", names)
        self.assertIn("text/oapaper/oapaper.pmc.pdf", names)
        self.assertIn("text/s2got/s2got.s2.pdf", names)
        # an abstract is kept as what it is; a page sent in place of a PDF and a body past its bound are not
        self.assertIn("text/elsabs/elsabs.elsevier.xml", names)
        self.assertNotIn("text/s2html/s2html.s2.pdf", names)
        self.assertNotIn("text/liar/liar.s2.pdf", names)
        self.assertFalse([name for name in names if name.endswith(".part")])
        self.assertTrue((self.landing / "INDEX.md").exists() and (self.landing / "README.md").exists())
        self.assertIn("never used to train a model", (self.landing / "README.md").read_text(encoding="utf-8"))
        # the PDF came from PMC's open-access service, the first link it offers
        self.assertTrue(any(path.endswith("/files/oa.pdf") for _, path, _ in Services.calls))

    def test_keys_travel_only_in_their_own_services_headers(self):
        _, planned = self.plan()
        _, fetched = self.fetch()
        for method, path, headers in Services.calls:
            for key in KEYS:
                self.assertNotIn(key, path)
            elsevier = path.startswith("/elsevier/")
            self.assertEqual("x-els-apikey" in headers, elsevier, path)
            self.assertEqual("x-els-insttoken" in headers, elsevier, path)
            self.assertEqual("x-api-key" in headers, path.startswith("/s2/"), path)
            if elsevier:
                self.assertEqual(method, "GET", "a keyed call is never sized by a HEAD of its own")
        self.assertFalse([path for _, path, _ in Services.calls if path.startswith("/elsewhere")],
                         "a redirect of a keyed call is never followed")
        written = [planned, fetched] + [path.read_text(encoding="utf-8", errors="replace")
                                        for path in [self.report, *self.landing.rglob("*")] if path.is_file()]
        for text in written:
            for key in KEYS:
                self.assertNotIn(key, text)

    def test_a_second_send_lands_only_what_is_still_missing(self):
        self.plan()
        self.fetch()
        before = len(Services.calls)
        code, said = self.plan()
        self.assertEqual(code, 0)
        total, need, how = said.strip().splitlines()[-1].split(" ", 2)
        self.assertGreater(int(total), int(need))
        # an abstract is no text, so Elsevier is asked again for the paper whose access may have opened
        self.assertIn("5 files held already", how)
        self.report.unlink()
        self.fetch()
        again = [path for _, path, _ in Services.calls[before:]]
        self.assertFalse([path for path in again if path.startswith(("/files/s2got", "/files/oa.pdf"))], again)
        self.assertTrue([path for path in again if path.startswith("/elsevier/doi/10.1016/j.abs.1")], again)
        self.assertIn("- elsgot: got elsevier xml", self.report.read_text(encoding="ascii"))

    def test_a_key_file_others_may_read_is_never_used(self):
        (self.home / ".elsevier" / "token.env").chmod(0o644)
        code, said = self.plan()
        self.assertEqual(code, 0, said)
        self.assertIn("Elsevier key: none (others may read it, so it is not used)", said)
        self.assertFalse([path for _, path, _ in Services.calls if path.startswith("/elsevier/")])
        self.fetch()
        self.assertIn("elsgot: not got; Elsevier: no key on the grid", self.report.read_text(encoding="ascii"))

    def test_with_no_key_files_semantic_scholar_is_asked_with_no_key(self):
        shutil.rmtree(self.home / ".elsevier")
        shutil.rmtree(self.home / ".fluorocap")
        code, said = self.plan()
        self.assertEqual(code, 0, said)
        self.assertIn("Elsevier key: none (no file); Semantic Scholar key: none (no file)", said)
        s2_calls = [headers for _, path, headers in Services.calls if path.startswith("/s2/")]
        self.assertTrue(s2_calls)
        self.assertFalse([headers for headers in s2_calls if "x-api-key" in headers])

    def test_a_list_out_of_its_shape_is_refused(self):
        for text in ("id,doi\nx,10.1000/a\n", "id,doi,pmcid,held\nx,,,\nx,,,\n", "id,doi,pmcid,held\nx,doi:1,,\n",
                     "id,doi,pmcid,held\nx,,123,\n", "id,doi,pmcid,held\nX Y,,,\n"):
            self.list.write_text(text, encoding="ascii")
            code, said = self.plan()
            self.assertEqual(code, 2, (text, said))
            self.assertFalse(Services.calls)

    def test_a_keyed_call_goes_only_to_its_own_service(self):
        with self.assertRaises(ValueError):
            self.tool.check_target("https://example.org/content/article/doi/x", "elsevier")
        with self.assertRaises(ValueError):
            self.tool.check_target(f"{self.address}/s2/DOI:x", "elsevier")
        self.tool.check_target(f"{self.address}/elsevier/doi/x", "elsevier")
        os.environ["LITERATURE_ELSEVIER"] = "https://example.org/content/article"
        self.assertEqual(self.tool.base("elsevier"), "https://api.elsevier.com/content/article")

    def test_every_service_is_asked_over_https(self):
        for service, address in self.tool.DEFAULTS.items():
            self.assertTrue(address.startswith("https://"), service)


class CommittedListTest(unittest.TestCase):
    def test_the_synthetic_spine_list_reads_whole(self):
        rows = load_tool().read_list(ROOT / "grid" / "literature" / "synthetic_spine.csv")
        self.assertEqual(len(rows), 42)
        self.assertEqual(sum(1 for row in rows if row["held"]), 3)
        bach = [row for row in rows if row["id"] == "bach2019"][0]
        self.assertTrue(bach["doi"].startswith("10.1016/"))
        self.assertEqual(sorted(row["id"] for row in rows if not row["doi"] and not row["pmcid"]),
                         ["ahmed2019", "alonge2021", "chaudhary2015"])


def chain_helpers():
    """The size rule's stand-ins, kept with the X-ray chain's tests."""
    spec = importlib.util.spec_from_file_location("xray_chain_helpers", ROOT / "tests" / "test_xray_chain.py")
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    return helpers


class LiteratureJobTest(unittest.TestCase):
    """grid/literature.sbatch under the size rule, with the X-ray chain's stand-ins for CephFS and Slurm."""

    def setUp(self):
        helpers = chain_helpers()
        self.gb = helpers.GB
        self.repo = helpers.repo_copy(self)
        (self.repo / "grid" / "literature" / "testlist.csv").write_text(LIST, encoding="ascii")
        self.volume = helpers.volume_in(self, quota=20 * self.gb, used=10 * self.gb)
        self.landing = self.volume.data / "literature_testlist"
        self.address = serve(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = home_with_keys(tmp.name)

    def job(self, **extra):
        env = dict(os.environ, SCHWINGNET=str(self.repo), LITERATURE_PYTHON=sys.executable,
                   XATTR_PYTHON=sys.executable, LIST_ID="testlist", SLURM_JOB_ID="77", HOME=str(self.home),
                   TMPDIR=str(self.home), **service_env(self.address))
        env.update(self.volume.env(**extra))
        done = subprocess.run(["bash", str(self.repo / "grid" / "literature.sbatch")], env=env,
                              cwd=self.repo / "grid", capture_output=True, text=True, timeout=120)
        return done.returncode, done.stdout + done.stderr

    def test_it_fetches_once_admitted_and_writes_its_report(self):
        code, out = self.job()
        self.assertEqual(code, 0, out)
        self.assertIn("literature_testlist: admitted", out)
        state, job = (self.landing / "meta" / "SIZE").read_text(encoding="utf-8").split()[:2]
        self.assertEqual((state, job), ("admitted", "77"))
        report = (self.repo / "grid" / "logs" / "LITERATURE-testlist.md").read_text(encoding="ascii")
        lines = report.splitlines()
        self.assertRegex(lines[0], r"^# literature testlist: job 77 on .*, commit unknown, ")
        self.assertRegex(lines[-1], r"^- exit 0 at ")
        self.assertIn("- elsgot: got elsevier xml", report)
        self.assertEqual(self.landing.stat().st_mode & 0o777, 0o700)
        self.assertTrue((self.landing / "text" / "elsgot" / "elsgot.elsevier.pdf").exists())
        for key in KEYS:
            self.assertNotIn(key, out + report)

    def test_it_lands_nothing_where_the_room_is_too_small(self):
        self.volume.attribute(self.volume.path, "ceph.dir.rbytes", 20 * self.gb)
        code, out = self.job()
        self.assertEqual(code, 4, out)
        self.assertIn("literature_testlist: refused for space", out)
        self.assertFalse((self.landing / "text").exists())
        report = (self.repo / "grid" / "logs" / "LITERATURE-testlist.md").read_text(encoding="ascii")
        self.assertRegex(report.splitlines()[-1], r"^- exit 4 at ")

    def test_a_list_the_checkout_does_not_hold_is_refused(self):
        code, out = self.job(LIST_ID="nolist")
        self.assertEqual(code, 2, out)
        self.assertIn("no list grid/literature/nolist.csv", (self.repo / "grid" / "logs" / "LITERATURE-nolist.md")
                      .read_text(encoding="ascii"))


if __name__ == "__main__":
    unittest.main()
