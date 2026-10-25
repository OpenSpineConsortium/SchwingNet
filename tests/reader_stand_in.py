"""A stand-in for what claude.ai gives the textbook's reader, tools/textbook_reader.html (issue #294),
so the reader can be driven in a browser where claude.ai cannot be reached: the Artifact tool's
skeleton around the page, a content security policy as strict as the artifact frame's is described
(inline scripts and styles, images from data and blob addresses, fetches of the page's own origin
alone), a viewer page on another origin that frames it, and window.claude with three capabilities:
files over a folder standing in for the Claude project's files, read through this server; sample,
answering in fixed words and strict about the realm of what it is given; and permissions. What the runtime documents and this stand-in follows:
use() resolves after the page's first run, the namespaces are frozen, a listing gives at most 500
entries a page with a cursor, a read gives bytes, the file's size and a revision, and a call fails
with an object whose code says why (the artifact-capabilities skill's files.d.ts, contract 0.2.90).

Nothing here is claude.ai's own code; a reader that works here has met the documented contract,
and how claude.ai's frame and runtime behave beyond it is measured only by opening the reader there.
The browser is Playwright's Chromium, where it is installed; the tests that use it skip elsewhere.
"""

import glob
import json
import mimetypes
import os
import threading
import urllib.parse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
READER = ROOT / "tools" / "textbook_reader.html"
VIEWER_HOST, ARTIFACT_HOST = "localhost", "127.0.0.1"   # two origins, as claude.ai and an artifact's frame are
PAGE_SIZE = 500

# The artifact frame's policy, as the Artifact tool's contract describes it: scripts inline or from
# the five script hosts, styles inline or from Google Fonts, images and media from data and blob
# addresses and the page's own files, fetches of the page's own origin.
CSP = ("default-src 'none'; "
       "script-src 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://unpkg.com "
       "https://cdn.tailwindcss.com https://code.jquery.com; "
       "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src data: https://fonts.gstatic.com; "
       "img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self'; "
       "frame-src 'self' blob: data:; worker-src 'self' blob:; base-uri 'none'; form-action 'none'")

# The Artifact tool's skeleton: a charset, a viewport and a small reset, the page inside the body.
SKELETON = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,'
            'initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);'
            'padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font:14px system-ui,sans-serif}'
            'img{max-width:100%}[hidden]{display:none!important}</style><script>{runtime}</script></head><body>'
            '{page}</body></html>')

# window.claude as the viewer gives it, standing in. CONFIG is the test's: mode (normal, absent,
# denied, outsider), the number of calls refused for the rate first, and the words sample answers.
RUNTIME = r"""
(function () {
  "use strict";
  var S = CONFIG;
  var calls = [];
  Object.defineProperty(window, "standInCalls", {value: calls});
  var limited = S.rateLimited || 0;
  function fail(code, extra) {
    var e = {code: code, message: code};
    Object.keys(extra || {}).forEach(function (k) { e[k] = extra[k]; });
    return Promise.reject(e);
  }
  function refused() {
    if (S.mode === "denied") return fail("not_granted");
    if (S.mode === "outsider") return fail("not_found");
    if (limited > 0) { limited--; return fail("rate_limited", {retryAfterMs: 30}); }
    return null;
  }
  function answered(r) {
    if (r.ok) return r;
    return r.json().then(function (e) { throw e; });
  }
  var files = Object.freeze({
    list: function (o) {
      o = o || {};
      calls.push(["list", o.path || "", Boolean(o.recursive), o.cursor || ""]);
      var no = refused();
      if (no) return no;
      var q = new URLSearchParams({path: o.path || "", recursive: o.recursive ? "1" : "", cursor: o.cursor || ""});
      return fetch("/_files/list?" + q).then(answered).then(function (r) { return r.json(); });
    },
    read: function (path, o) {
      o = o || {};
      calls.push(["read", path, o.offset || 0, o.length || 0]);
      var no = refused();
      if (no) return no;
      var q = new URLSearchParams({path: path, offset: String(o.offset || 0), length: String(o.length || 0)});
      return fetch("/_files/read?" + q).then(answered).then(function (r) {
        return r.arrayBuffer().then(function (b) {
          return {bytes: new Uint8Array(b), size: Number(r.headers.get("X-Size")), revision: r.headers.get("X-Revision")};
        });
      });
    },
    download: function () { return fail("declined"); },
    asSampleTools: function () { return Promise.resolve([]); }
  });
  // sample as a strict runtime takes it: what it is given is checked by instanceof in this frame's
  // own realm, as validators commonly check it, so an array, an object or an abort signal made in
  // another frame is refused; the first tool given is run once and its answer quoted.
  function sample(input, opts) {
    opts = opts || {};
    var tools = opts.tools || [];
    calls.push(["sample", typeof input === "string" ? input.length : JSON.stringify(input).length,
                Boolean(opts.signal), tools.length]);
    if (typeof input !== "string" && !(input instanceof Array)) return fail("bad_request");
    if (opts.signal && !(opts.signal instanceof AbortSignal)) return fail("bad_request");
    if (opts.tools && !(opts.tools instanceof Array)) return fail("bad_request");
    for (var i = 0; i < tools.length; i++) {
      if (!(tools[i] instanceof Object) || typeof tools[i].execute !== "function") return fail("bad_request");
    }
    if (opts.signal && opts.signal.aborted) return fail("cancelled");
    var ran = tools.length ? Promise.resolve(tools[0].execute({query: "level"}, {signal: new AbortController().signal}))
                           : Promise.resolve(null);
    return ran.then(function (result) {
      var text = (S.answer || "A stand-in answer.") + (result ? " The tool said " + JSON.stringify(result) + "." : "");
      if (typeof opts.onText === "function") opts.onText({text: text, delta: text});
      return {text: text, truncated: false};
    });
  }
  sample.json = function () { return Promise.resolve(null); };
  sample.limits = function () { return Promise.resolve({images: false}); };
  var permissions = Object.freeze({
    state: function (name) { return Promise.resolve(name ? "granted" : {}); },
    request: function () { return Promise.resolve({}); },
    manage: function () { calls.push(["manage"]); return Promise.resolve(); }
  });
  var served = {files: S.mode === "absent" ? null : files, sample: Object.freeze(sample), permissions: permissions};
  var promised = {};
  function later(value) { return new Promise(function (done) { setTimeout(function () { done(value); }, 20); }); }
  window.claude = Object.freeze({use: function (name) {
    if (!Object.prototype.hasOwnProperty.call(served, name)) return later(null);
    if (!promised[name]) promised[name] = later(served[name]);
    return promised[name];
  }});
})();
"""


def artifact_document(config):
    """The reader as the artifact's frame serves it, with the stand-in runtime first in its head."""
    runtime = RUNTIME.replace("CONFIG", json.dumps(config)).replace("</", "<\\/")
    return SKELETON.replace("{runtime}", runtime).replace("{page}", READER.read_text(encoding="utf-8"))


def viewer_document(port, query, hash_):
    """The page standing in for claude.ai, on another origin, framing the artifact as the viewer
    does: scripts, its own origin and popups allowed, nothing else."""
    src = f"http://{ARTIFACT_HOST}:{port}/artifact.html?{query}" + (f"#{hash_}" if hash_ else "")
    return ("<!doctype html><html><head><meta charset=utf-8><title>viewer</title><link rel=icon href=\"data:,\">"
            "<style>html,body{margin:0;"
            "height:100%}iframe{display:block;border:0;width:100%;height:100%}</style></head><body>"
            f'<iframe id="artifact" src="{src}" sandbox="allow-scripts allow-same-origin allow-popups allow-forms">'
            "</iframe></body></html>")


class Project:
    """The folder standing in for the Claude project's files, listed and read as the runtime lists
    and reads them; with slashes, folders come back as /name/ and files as /name, as a runtime that
    spells paths so might, and the reader passes them back as given."""

    def __init__(self, root, slashes=False, page_size=PAGE_SIZE):
        self.root, self.slashes, self.page_size = Path(root), slashes, page_size

    def spelled(self, rel, folder):
        if not self.slashes:
            return rel
        return "/" + rel + ("/" if folder else "")

    def place(self, path):
        rel = urllib.parse.unquote(path).strip("/")
        target = (self.root / rel).resolve() if rel else self.root.resolve()
        if target != self.root.resolve() and self.root.resolve() not in target.parents:
            raise LookupError(path)
        if not target.exists():
            raise LookupError(path)
        return target

    def list(self, path, recursive, cursor):
        folder = self.place(path)
        if not folder.is_dir():
            raise ValueError(path)
        found = sorted(folder.rglob("*") if recursive else folder.iterdir())
        at = int(cursor or 0)
        entries = [{"path": self.spelled(p.relative_to(self.root).as_posix(), p.is_dir()), "isDirectory": p.is_dir(),
                    "size": 0 if p.is_dir() else p.stat().st_size} for p in found[at:at + self.page_size]]
        answer = {"entries": entries}
        if at + self.page_size < len(found):
            answer["cursor"] = str(at + self.page_size)
        return answer

    def read(self, path, offset, length):
        target = self.place(path)
        if target.is_dir():
            raise ValueError(path)
        size = target.stat().st_size
        length = min(length or 26214400, 26214400)
        with open(target, "rb") as handle:
            handle.seek(offset)
            data = handle.read(length)
        stat = target.stat()
        return data, size, f"{stat.st_mtime_ns}-{size}"


def handler(project, configs):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, body, kind, headers=None):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def error(self, status, code):
            self.send(status, json.dumps({"code": code, "message": code}).encode(), "application/json")

        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(url.query, keep_blank_values=True))
            port = self.server.server_address[1]
            if url.path == "/viewer.html":
                self.send(200, viewer_document(port, url.query.split("&hash=")[0], q.get("hash", "")).encode(),
                          "text/html; charset=utf-8")
            elif url.path == "/artifact.html":
                config = configs.get(q.get("config", ""), {})
                self.send(200, artifact_document(config).encode("utf-8"), "text/html; charset=utf-8",
                          {"Content-Security-Policy": CSP})
            elif url.path == "/_files/list":
                try:
                    answer = project.list(q.get("path", ""), q.get("recursive") == "1", q.get("cursor", ""))
                except LookupError:
                    return self.error(404, "not_found")
                except ValueError:
                    return self.error(400, "bad_request")
                self.send(200, json.dumps(answer).encode(), "application/json")
            elif url.path == "/_files/read":
                try:
                    data, size, revision = project.read(q.get("path", ""), int(q.get("offset") or 0),
                                                         int(q.get("length") or 0))
                except LookupError:
                    return self.error(404, "not_found")
                except ValueError:
                    return self.error(400, "bad_request")
                self.send(200, data, "application/octet-stream", {"X-Size": str(size), "X-Revision": revision})
            else:
                kind = mimetypes.guess_type(url.path)[0] or "application/octet-stream"
                self.send(404, b"", kind)

    return Handler


@contextmanager
def serving(project, configs):
    """The stand-in's server on a free port, in a thread, for the length of the block; configs maps
    a name a test opens the viewer with (viewer.html?config=NAME) to the runtime's CONFIG."""
    server = ThreadingHTTPServer((ARTIFACT_HOST, 0), handler(project, configs))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def viewer_url(port, config, hash_=""):
    return f"http://{VIEWER_HOST}:{port}/viewer.html?config={config}" + (f"&hash={hash_}" if hash_ else "")


def chromium(playwright):
    """Playwright's Chromium, launched as the installed one allows: by its own name, or, where the
    Python package expects another build than the one installed, by the installed build's path."""
    try:
        return playwright.chromium.launch()
    except Exception:  # the package's own build is not the one installed
        pass
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    for path in sorted(glob.glob(os.path.join(base, "chromium-*", "chrome-linux*", "chrome")), reverse=True):
        try:
            return playwright.chromium.launch(executable_path=path)
        except Exception:
            continue
    return None
