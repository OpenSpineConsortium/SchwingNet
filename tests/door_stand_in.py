"""A stand-in for what claude.ai gives the front door, tools/front_door.html, so the door can be
driven in a browser where neither claude.ai nor GitHub can be reached: the Artifact tool's skeleton
around the page, the artifact frame's content security policy, a viewer page on another origin that
frames it (all three from tests/reader_stand_in.py), and window.claude with three capabilities: mcp,
whose one server "GitHub" answers get_file_contents, list_commits and search_code through this
server over folders standing in for the repository's branches, in the shapes GitHub's own MCP server
gives (a folder as one text block of JSON, a file as a resource block of text or of base64 beside a
text block that says it was downloaded, a path it has not as a tool error naming 404, commits and
code search as the REST API's JSON); sample, answering in fixed words after running the first tool
it is given; and permissions. What the runtime documents and this stand-in follows: use() resolves
after the page's first run, the namespaces are frozen, a call fails with an object whose code says
why, listTools names the servers the viewer has, and a viewer with no GitHub connector gets
server_not_connected (the artifact-capabilities skill's mcp.d.ts, contract 0.2.90).

Nothing here is claude.ai's or GitHub's own code; a door that works here has met the documented
contracts, and how claude.ai's runtime and GitHub's server behave beyond them is measured only by
opening the door on claude.ai with a GitHub connector.
"""

import base64
import json
import mimetypes
import re
import threading
import urllib.parse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from reader_stand_in import ARTIFACT_HOST, CSP, SKELETON, VIEWER_HOST, chromium, viewer_document  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
DOOR = ROOT / "tools" / "front_door.html"
LOADER = ROOT / "tools" / "front_door_loader.html"
OWNER, REPO = "OpenSpineConsortium", "SchwingNet"
TOOLS = ("get_file_contents", "list_commits", "search_code")
TEXT = re.compile(r"\.(?:md|html?|css|js|json|txt|csv|py|sh|ya?ml|toml|svg|xml)$", re.I)

# window.claude as the viewer gives it, standing in. CONFIG is the test's: mode (normal, absent,
# notConnected, denied), the number of calls refused for the rate first, the words sample answers
# and the input it runs the first tool with.
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
    if (limited > 0) { limited--; return fail("rate_limited", {retryAfterMs: 30}); }
    return null;
  }
  function post(tool, input) {
    return fetch("/_github/" + tool, {method: "POST", headers: {"Content-Type": "application/json"},
                                      body: JSON.stringify(input === undefined ? null : input)}).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) throw j; return j; });
    });
  }
  function known(server, tool) {
    if (S.mode === "notConnected") return fail("server_not_connected");
    if (server !== "GitHub") return fail("server_not_found");
    if (tool !== undefined && ["get_file_contents", "list_commits", "search_code"].indexOf(tool) < 0) return fail("not_in_manifest");
    return null;
  }
  var mcp = Object.freeze({
    listTools: function (server) {
      calls.push(["listTools", server || ""]);
      var no = known(server || "GitHub");
      if (no) return no;
      return Promise.resolve({servers: [{name: "GitHub", kind: "connector", tools: [
        {name: "get_file_contents", description: "", annotations: {readOnlyHint: true}},
        {name: "list_commits", description: "", annotations: {readOnlyHint: true}},
        {name: "search_code", description: "", annotations: {readOnlyHint: true}}]}]});
    },
    callTool: function (server, tool, input) {
      calls.push(["callTool", server, tool, JSON.parse(JSON.stringify(input === undefined ? null : input))]);
      var no = known(server, tool) || refused();
      if (no) return no;
      if (input !== undefined && input !== null && typeof input !== "object") return fail("bad_request");
      return post(tool, input);
    },
    server: function (name) {
      var no = known(name);
      if (no) return no;
      var handle = {};
      ["get_file_contents", "list_commits", "search_code"].forEach(function (t) {
        handle[t] = function (input) { return mcp.callTool(name, t, input).then(function (r) { return r.payload; }); };
      });
      return Promise.resolve(Object.freeze(handle));
    },
    describeTool: function () { return fail("unavailable"); },
    invalidate: function () { return Promise.resolve(); }
  });
  // sample as a strict runtime takes it: the first tool given is run once with the input the
  // test names and its answer quoted, so a page's tools are seen to reach what they read.
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
    var ran = tools.length ? Promise.resolve(tools[0].execute(S.toolInput || {path: ""}, {signal: new AbortController().signal}))
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
  var served = {mcp: S.mode === "absent" ? null : mcp, sample: Object.freeze(sample), permissions: permissions};
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
    """The door as the artifact's frame serves it, with the stand-in runtime first in its head; a
    config whose page is "loader" serves the door's loader, the page published at the link, in its place."""
    runtime = RUNTIME.replace("CONFIG", json.dumps(config)).replace("</", "<\\/")
    page = LOADER if config.get("page") == "loader" else DOOR
    return SKELETON.replace("{runtime}", runtime).replace("{page}", page.read_text(encoding="utf-8"))


class ToolError(Exception):
    """What GitHub's server answers a call it cannot serve with: a tool error whose message says why."""


class Repository:
    """Folders standing in for the repository's branches, read as GitHub's MCP server reads a
    repository: refs maps a branch's name to its folder; commits is what list_commits answers."""

    def __init__(self, refs, commits):
        self.refs = {name: Path(folder) for name, folder in refs.items()}
        self.commits = commits

    def branch(self, ref):
        name = str(ref or "refs/heads/main").replace("refs/heads/", "")
        if name not in self.refs:
            raise ToolError(f"failed to get file contents: GET {name}: 404 Not Found []")
        return self.refs[name]

    def place(self, root, path):
        rel = urllib.parse.unquote(str(path or "")).strip("/")
        target = (root / rel).resolve() if rel else root.resolve()
        if target != root.resolve() and root.resolve() not in target.parents or not target.exists():
            raise ToolError(f"failed to get file contents: GET https://api.github.com/repos/{OWNER}/{REPO}/contents/{rel}"
                            ": 404 Not Found []")
        return target, rel

    def get_file_contents(self, input_):
        root = self.branch(input_.get("ref"))
        target, rel = self.place(root, input_.get("path", "/"))
        if target.is_dir():
            entries = []
            for p in sorted(target.iterdir()):
                path = p.relative_to(root).as_posix()
                entries.append({"type": "dir" if p.is_dir() else "file", "name": p.name, "path": path,
                                "size": 0 if p.is_dir() else p.stat().st_size, "sha": "0" * 40,
                                "html_url": f"https://github.com/{OWNER}/{REPO}/{'tree' if p.is_dir() else 'blob'}/main/{path}"})
            return {"content": [{"type": "text", "text": json.dumps(entries)}], "payload": entries}
        data = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        uri = f"repo://{OWNER}/{REPO}/sha/{'0' * 40}/contents/{rel}"
        if TEXT.search(target.name):
            resource = {"uri": uri, "mimeType": mime, "text": data.decode("utf-8")}
            note = "successfully downloaded text file"
        else:
            resource = {"uri": uri, "mimeType": mime, "blob": base64.b64encode(data).decode("ascii")}
            note = "successfully downloaded binary file"
        return {"content": [{"type": "text", "text": note}, {"type": "resource", "resource": resource}], "payload": note}

    def list_commits(self, input_):
        per_page = int(input_.get("perPage") or 30)
        found = self.commits[:per_page]
        return {"content": [{"type": "text", "text": json.dumps(found)}], "payload": found}

    def search_code(self, input_):
        words = [w for w in str(input_.get("query", "")).split() if not w.startswith("repo:")]
        root = self.refs["main"]
        items = []
        for p in sorted(root.rglob("*")):
            if not p.is_file() or not TEXT.search(p.name):
                continue
            body = p.read_text(encoding="utf-8", errors="replace")
            if words and all(w.lower() in body.lower() for w in words):
                line = next((ln for ln in body.splitlines() if words[0].lower() in ln.lower()), "")
                items.append({"name": p.name, "path": p.relative_to(root).as_posix(), "sha": "0" * 40,
                              "repository": {"full_name": f"{OWNER}/{REPO}"}, "text_matches": [{"fragment": line}]})
        found = {"total_count": len(items), "incomplete_results": False, "items": items}
        return {"content": [{"type": "text", "text": json.dumps(found)}], "payload": found}

    def call(self, tool, input_):
        if tool not in TOOLS:
            raise ToolError(f"unknown tool {tool}")
        return getattr(self, tool)(input_ or {})


def handler(repository, configs):
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
            else:
                self.send(404, b"", "text/plain")

        def do_POST(self):
            url = urllib.parse.urlsplit(self.path)
            length = int(self.headers.get("Content-Length") or 0)
            try:
                input_ = json.loads(self.rfile.read(length) or b"null")
            except ValueError:
                input_ = None
            if not url.path.startswith("/_github/"):
                return self.send(404, b"", "text/plain")
            try:
                answer = repository.call(url.path[len("/_github/"):], input_)
            except ToolError as error:
                return self.send(400, json.dumps({"code": "tool_error", "message": str(error)}).encode(), "application/json")
            self.send(200, json.dumps(answer).encode(), "application/json")

    return Handler


@contextmanager
def serving(repository, configs):
    """The stand-in's server on a free port, in a thread, for the length of the block; configs maps
    a name a test opens the viewer with (viewer.html?config=NAME) to the runtime's CONFIG."""
    server = ThreadingHTTPServer((ARTIFACT_HOST, 0), handler(repository, configs))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def viewer_url(port, config, hash_=""):
    return f"http://{VIEWER_HOST}:{port}/viewer.html?config={config}" + (f"&hash={hash_}" if hash_ else "")
