"""The textbook site as the files of one claude.ai artifact: the edition a
session publishes, private, on the owner's account, and republishes to the
same link after each merge (issue #236).

The members-only Pages site is built by tools/textbook_site.py. A claude.ai
artifact page cannot be framed by any other site, the Pages site included:
it answers content-security-policy frame-ancestors 'self' and two extension
ids and serves its content from a per-artifact frame origin
(docs/research/textbook-as-an-artifact.md). So the book goes to claude.ai
the other way round: the whole site is published as one multi-page artifact
on the owner's account, where the exported copies of the artifacts open as
pages of their own, interactive, and every page carries an Ask Claude box
that answers from the page's text through the artifact runtime's sample
capability, on the viewer's own Claude account.

Since #233 the site itself carries the exported artifact folders under
artifacts/<folder>/, the button that opens an artifact's page from each
figure traced to it and the embed on each artifact's own page, so this
script copies the site and changes only what the artifact needs:

- index.html becomes the artifact's page proper: the Artifact tool wraps that
  one file in its own skeleton, so it is written without doctype, html, head
  and body, its title and style first, then what the body held, the head's
  scripts after it; every other page keeps its whole document, since
  supporting files are served as they are.
- The JSON figure records are not published as files (a version holds at
  most 511 files, and the records are the repository's); "The record" points
  at the file on GitHub at the built commit instead. A data file beside a
  figure, JSON with no image or page of its own name, which is how
  tools/textbook_site.py tells the two apart, is kept: no figure page reads
  one at view time today (none under docs/textbook/figures/ calls fetch or
  XMLHttpRequest, 2026-10-24), one that did would find it, and the two there
  are small.
- The viewer's theme toggle sets data-theme on the root; the site's
  stylesheet knows only prefers-color-scheme, so the toggle's two states are
  added as token overrides on every page.
- Every page gets the Ask Claude box (ask.js, one shared file) and the front
  page a line saying which commit the edition was built from, so a reader
  can tell a stale copy from the current one. Each figure gets a button that
  opens the box with the figure named.

The output folder holds the files to publish and batches.json: the files
grouped under the Artifact tool's per-publish limits (255 files and 64 MB,
with a margin), index.html left out of every batch since it is the publish's
own file_path; a whole version must stay under 511 files and 256 MB, a
binary file under 15 MB and a text file under 16 MB, and the script says so
when one does not. The edition line carries the built commit's own date,
given as --built, never the clock, so building one commit twice gives the
same bytes and the publish workflow (.github/workflows/textbook-artifact.yml,
tools/textbook_publish.py) can tell what changed by hashing the files.

    python3 tools/textbook_artifact.py SITE OUT --repo OWNER/NAME --sha SHA --built DATE
"""

import argparse
import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

PER_PUBLISH_FILES = 240          # the tool takes 255 files a publish
PER_PUBLISH_BYTES = 60 * 1024 * 1024    # and 64 MB
VERSION_FILES = 511
VERSION_BYTES = 256 * 1024 * 1024
BINARY_LIMIT = 15 * 1024 * 1024
TEXT_LIMIT = 16 * 1024 * 1024
TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".md", ".txt", ".svg", ".csv"}
TITLE = "SchwingNet Textbook"
MARKER = ".textbook"
DEFAULT_REPO = "OpenSpineConsortium/SchwingNet"

THEME_CSS = """
/* The viewer's theme toggle: the site's stylesheet follows the system setting alone. */
:root[data-theme="dark"] { --bg:#16171a; --fg:#ececee; --muted:#a2a2aa; --line:#2c2d33; --panel:#1f2024;
  --accent:#e0a85a; --run:#1b2533; --runline:#6f93bd; --out:#1c2a1d; --outline:#7fa66c;
  --method:#f08a84; --warn:#e0a85a; --ok:#8cc47f; --soft:#1b1c20; color-scheme:dark; }
:root[data-theme="light"] { --bg:#fbfaf7; --fg:#1d1d1f; --muted:#5d5d63; --line:#e3e0d8; --panel:#f3efe6;
  --accent:#8a5a14; --run:#eaf0f7; --runline:#4a6a8f; --out:#eef4ea; --outline:#5b7f4a;
  --method:#a33a37; --warn:#9a6212; --ok:#3f7a3a; --soft:#f6f3ec; color-scheme:light; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme:dark; } }
body { padding-left:max(0px, env(safe-area-inset-left, 0px)); padding-right:max(0px, env(safe-area-inset-right, 0px)); }
.edition { font-size:14px; color:var(--muted); border-left:4px solid var(--line); padding:6px 12px; margin:10px 0 18px; }
@media (max-width: 760px) { .wrap { flex-direction:column; } nav { width:auto; border-right:0; border-bottom:1px solid var(--line); }
  main { padding:18px 16px 56px; } }
/* Ask Claude */
#ask-open { position:fixed; right:calc(18px + env(safe-area-inset-right, 0px)); bottom:calc(18px + env(safe-area-inset-bottom, 0px));
  z-index:20; border:1px solid var(--accent); background:var(--accent); color:var(--bg); border-radius:999px; padding:9px 16px;
  font:600 14px/1 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; cursor:pointer; box-shadow:0 2px 10px rgba(0,0,0,.18); }
#ask { position:fixed; right:calc(12px + env(safe-area-inset-right, 0px)); bottom:calc(12px + env(safe-area-inset-bottom, 0px));
  left:auto; width:min(440px, calc(100vw - 24px)); max-height:min(78vh, 720px); z-index:21; display:flex; flex-direction:column;
  gap:8px; background:var(--panel); color:var(--fg); border:1px solid var(--line); border-radius:12px; padding:12px 14px;
  box-shadow:0 8px 30px rgba(0,0,0,.25); font-size:14px; }
#ask[hidden] { display:none; }
#ask header { border:0; padding:0; display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
#ask header strong { font-size:15px; }
#ask textarea { width:100%; min-height:64px; resize:vertical; border:1px solid var(--line); border-radius:8px; padding:8px;
  background:var(--bg); color:var(--fg); font:14px/1.45 inherit; }
#ask .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
#ask button, #ask a.button { border:1px solid var(--accent); color:var(--accent); background:transparent; border-radius:6px;
  padding:4px 12px; font-size:13.5px; cursor:pointer; text-decoration:none; }
#ask button.primary { background:var(--accent); color:var(--bg); }
#ask button:disabled { opacity:.55; cursor:default; }
#ask-out { overflow:auto; white-space:pre-wrap; line-height:1.5; border-top:1px solid var(--line); padding-top:8px; min-height:1.4em; }
#ask-out:empty { display:none; }
#ask-run { border-top:1px solid var(--line); padding-top:8px; }
#ask-hint { color:var(--muted); font-size:12.5px; margin:0; }
#ask button:focus-visible, #ask-open:focus-visible, #ask textarea:focus-visible { outline:2px solid var(--runline); outline-offset:2px; }
@media (prefers-reduced-motion: no-preference) { #ask-open { transition:transform .15s; } #ask-open:hover { transform:translateY(-1px); } }
"""

ASK_HTML = """
<button id="ask-open" type="button" aria-controls="ask" aria-expanded="false">Ask Claude</button>
<aside id="ask" hidden aria-label="Ask Claude about this page">
<header><strong id="ask-title">Ask Claude about this page</strong><button id="ask-close" type="button" aria-label="Close">Close</button></header>
<p id="ask-hint">The answer is drawn from this page's text alone, graded as the book grades, on your own Claude account; nothing is sent anywhere else.</p>
<textarea id="ask-q" placeholder="A question about what this page says, its numbers, its grades or what would change them"></textarea>
<div class="row"><button id="ask-send" class="primary" type="button">Ask</button><button id="ask-stop" type="button" hidden>Stop</button>
<a id="ask-handoff" class="button" href="#" target="_blank" rel="noopener">Hand it to Claude in the repository</a></div>
<div id="ask-out" aria-live="polite"></div>
</aside>
"""

ASK_JS = r"""
// The Ask Claude box: answers from the page's own text through the artifact runtime's sample
// capability, which spends the viewer's own Claude usage and asks their consent on the first
// call. Where the runtime is absent (a page opened outside the viewer, or a page the viewer
// does not bridge) the box says so and points at the front page, whose box reads any chapter.
(function () {
  "use strict";
  var panel = document.getElementById("ask");
  if (!panel) return;
  var open = document.getElementById("ask-open"), close = document.getElementById("ask-close");
  var q = document.getElementById("ask-q"), out = document.getElementById("ask-out"), send = document.getElementById("ask-send");
  var stop = document.getElementById("ask-stop"), hint = document.getElementById("ask-hint"), handoff = document.getElementById("ask-handoff");
  var title = document.getElementById("ask-title");
  var repo = document.documentElement.getAttribute("data-repo") || "";
  var here = (function () { var p = location.pathname.split("/").pop() || ""; return /\.html$/.test(p) ? p : "index.html"; })();
  var LIMIT = 180000; // characters of page text sent with a question; the runtime takes 256 KiB in all
  var context = null, subject = pageTitle(), sampleFn = undefined, controller = null;

  function pageTitle() { return document.title.replace(/ - The SchwingNet textbook$/, ""); }
  function mainText(doc) {
    var m = (doc || document).querySelector("main");
    var node = m || (doc || document).body;
    var clone = node.cloneNode(true);
    clone.querySelectorAll("#ask, #ask-open, script, style, .buttons, .pager").forEach(function (n) { n.remove(); });
    return (clone.innerText || clone.textContent || "").replace(/\n{3,}/g, "\n\n").trim();
  }
  function issueUrl(question) {
    var body = ["@claude", "", "About: " + subject + " (the textbook, page " + here + ")", "",
                question || "My question or request (type it here, in place of this line, before you submit):", ""].join("\n");
    return "https://github.com/" + repo + "/issues/new?" + new URLSearchParams({title: "Ask Claude: " + subject, body: body}).toString();
  }
  function setHandoff() { handoff.href = issueUrl(q.value.trim()); }
  function show(on) {
    panel.hidden = !on; open.setAttribute("aria-expanded", on ? "true" : "false");
    if (on) { setHandoff(); q.focus(); }
  }
  open.addEventListener("click", function () { show(panel.hidden); });
  close.addEventListener("click", function () { show(false); });
  q.addEventListener("input", setHandoff);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) show(false); });

  // A figure's own button opens the box with the figure named.
  document.querySelectorAll("button.ask-fig").forEach(function (b) {
    b.addEventListener("click", function () {
      var s = b.getAttribute("data-subject") || "";
      q.value = "About " + s + ": ";
      show(true);
      q.setSelectionRange(q.value.length, q.value.length);
    });
  });

  function copyFor(code) {
    switch (code) {
      case "not_granted": return "You did not allow this page to ask Claude; the Hand it to Claude button still works.";
      case "rate_limited": return "Claude is busy with earlier questions; wait a minute and ask again.";
      case "cancelled": return "";
      default: return "Claude could not answer this time (" + code + "). The Hand it to Claude button opens the question in the repository instead.";
    }
  }
  function absent(reason) {
    sampleFn = null;
    send.disabled = true;
    var front = here === "index.html" ? "" : ' Open the <a href="index.html#ask-' + encodeURIComponent(here.replace(/\.html$/, "")) +
      '">front page\'s box</a>, which reads this page for you, or hand the question to Claude in the repository.';
    hint.innerHTML = reason + front;
  }
  function boot() {
    // Inside the viewer window.claude is there before any page script runs; a supporting page the
    // viewer does not bridge, or a copy opened elsewhere, never gets it, so the wait is short.
    var tries = 0;
    (function wait() {
      if (window.claude && typeof window.claude.use === "function") {
        window.claude.use("sample").then(function (fn) {
          if (!fn) { absent("Ask Claude is not available on this page in this viewer."); return; }
          sampleFn = fn;
        }, function () { absent("Ask Claude is not available on this page in this viewer."); });
        return;
      }
      if (++tries < 40) { setTimeout(wait, 100); return; }
      absent("Ask Claude is not available on this page outside the claude.ai viewer.");
    })();
  }
  boot();

  function loadChapter(name) {
    // The front page reads another page's text when its link says #ask-<page>.
    return fetch(name + ".html").then(function (r) { return r.ok ? r.text() : ""; }).then(function (t) {
      if (!t) return;
      var doc = new DOMParser().parseFromString(t, "text/html");
      context = mainText(doc);
      subject = (doc.title || name).replace(/ - The SchwingNet textbook$/, "");
      title.textContent = "Ask Claude about " + subject;
      show(true);
    }).catch(function () {});
  }
  var m = /^#ask-([a-z0-9-]+)$/.exec(location.hash || "");
  if (m && m[1] !== "index") loadChapter(m[1]);

  var RULES = "You are answering inside the SchwingNet textbook, a confidential book built from a research programme's " +
    "artifacts. Answer from the page text below and from nothing else; when the page does not answer, say so plainly " +
    "rather than guess. Quote the book's grades (Measured, Reported, Inferred, Unverified) and its status words as the " +
    "page gives them, and call a figure the record has not settled \"a record, not a final value\", as the book does. " +
    "Give numbers only as the page gives them, with their n and interval where it has them. Name people by role, never " +
    "by name. Plain prose, under 250 words, no headings. If the question needs work the page cannot do, a run, a fetch " +
    "or a new analysis, say what would settle it in one sentence, so the reader can hand it to Claude in the repository. " +
    "When the reader asks for a run, a training of a new combination of data and blocks, end your answer with one line " +
    "of its own, experiment: recipe=<name> epochs=<n> seed=<n> hours=<h> KEY=VALUE ..., one KEY=VALUE word per block " +
    "named, the recipe and the values spelled as the page spells them, the panel's defaults (recipe none, 20 epochs, " +
    "seed 1, 4 hours) where the reader names none, and nothing the page does not name; write no such line otherwise.";

  // The combination an answer names on its experiment: line becomes a request in the experiments panel's own
  // form (docs/research/experiments-panel.md, section 5): the prefilled issue always, and Run as me where the
  // page's dispatcher has the viewer's GitHub connector (tools/textbook_site.py MESSAGE_JS). The workflow checks
  // every value against the recipes and the blocks module, so the box checks only the shape of each word.
  var REQUEST_LINE = /^experiment:[ \t]*(.+?)[ \t]*$/m;
  var REQUEST_WORD = /^([a-z][a-z0-9_]{0,31})=([A-Za-z0-9][A-Za-z0-9._,-]{0,79})$/;
  var SETTINGS = {recipe: "none", epochs: "20", seed: "1", hours: "4"};
  var runRow = null;
  function requestOf(text) {
    var m = REQUEST_LINE.exec(text || "");
    if (!m) return null;
    var fields = {}, blocks = [];
    m[1].split(/\s+/).forEach(function (w) {
      var p = REQUEST_WORD.exec(w);
      if (!p) return;
      if (SETTINGS.hasOwnProperty(p[1])) fields[p[1]] = p[2]; else blocks.push(p[1] + "=" + p[2]);
    });
    Object.keys(SETTINGS).forEach(function (k) { if (!fields[k]) fields[k] = SETTINGS[k]; });
    return {fields: fields, blocks: blocks};
  }
  function requestTitle(r) {
    return "Experiment: " + (r.blocks.length ? r.blocks.join(" ") : "version 1 (no block named)") + ", " + r.fields.epochs + " epochs";
  }
  function requestBody(r, question) {
    var lines = ["<!-- schwingnet-experiment -->"];
    Object.keys(SETTINGS).forEach(function (k) { lines.push(k + ": " + r.fields[k]); });
    r.blocks.forEach(function (w) { lines.push("block: " + w); });
    return lines.join("\n") + "\n\nAsked in the textbook's Ask Claude box on " + subject + " (page " + here + "): " + question +
      "\n\nThe answer named this combination; the experiment workflow checks it against data/recipes/ and " +
      "src/schwingnet/blocks.py and answers with the command, the gate word and the owner's click.\n";
  }
  function requestUrl(r, question) {
    return "https://github.com/" + repo + "/issues/new?" +
      new URLSearchParams({title: requestTitle(r), labels: "experiment", body: requestBody(r, question)}).toString();
  }
  function offerRun(r, question) {
    if (runRow) { runRow.remove(); runRow = null; }
    if (!r) return;
    runRow = document.createElement("div"); runRow.className = "row"; runRow.id = "ask-run";
    var a = document.createElement("a");
    a.className = "button"; a.target = "_blank"; a.rel = "noopener"; a.href = requestUrl(r, question); a.textContent = "Request this run";
    runRow.appendChild(a);
    out.parentNode.insertBefore(runRow, out.nextSibling);
    if (typeof window.schwingnetConnector !== "function" || typeof window.schwingnetDispatch !== "function") return;
    window.schwingnetConnector().then(function (m) {
      if (!m || !runRow) return;
      var b = document.createElement("button");
      b.type = "button"; b.textContent = "Run as me";
      b.title = "Dispatches experiment.yml on " + repo + " through your GitHub connector; the workflow opens the issue and answers it";
      b.addEventListener("click", function () {
        b.disabled = true;
        window.schwingnetDispatch({repo: repo, workflow: "experiment.yml", ref: "main", label: "experiment", fallbackUrl: a.href,
                                   inputs: {recipe: r.fields.recipe, epochs: r.fields.epochs, seed: r.fields.seed, hours: r.fields.hours,
                                            blocks: r.blocks.join(" ")}})
          .then(function (res) {
            out.textContent += "\n\n" + (res.ok ? "Dispatched as you: the experiment workflow opens the issue and answers it with the gate word."
                                                 : "Not dispatched (" + res.error + "); Request this run opens the issue instead.");
            if (!res.ok) b.disabled = false;
          });
      });
      runRow.appendChild(b);
    });
  }

  send.addEventListener("click", function () {
    var question = q.value.trim();
    if (!question) { q.focus(); return; }
    if (sampleFn === undefined) { out.textContent = "The page is still connecting to Claude; try again in a moment."; return; }
    if (!sampleFn) return;
    var text = context === null ? mainText() : context;
    var input = RULES + "\n\nPage: " + subject + "\n\nPage text:\n" + text.slice(0, LIMIT) + "\n\nQuestion: " + question;
    controller = new AbortController();
    send.disabled = true; stop.hidden = false;
    offerRun(null);
    out.textContent = "Thinking...";
    sampleFn(input, {signal: controller.signal, cache: false, onText: function (e) { out.textContent = e.text; }})
      .then(function (r) {
        out.textContent = r.text + (r.truncated ? "\n\n[The answer was cut short; ask for less at a time.]" : "");
        offerRun(r.truncated ? null : requestOf(r.text), question);
      })
      .catch(function (e) { out.textContent = (e && e.text) || ""; var c = copyFor(e && e.code); if (c) out.textContent += (out.textContent ? "\n\n" : "") + c; })
      .then(function () { send.disabled = false; stop.hidden = true; controller = null; });
  });
  stop.addEventListener("click", function () { if (controller) controller.abort(); });
})();
"""

RECORD_LINK = re.compile(r'href="figures/(\d\d)/([a-z0-9-]+)\.json"')
FIGURE = re.compile(r'<figure class="fig"(?: id="([^"]*)")?>.*?</figure>', re.S)
BUTTONS_END = re.compile(r'(<div class="buttons">(?:(?!</div>).)*)(</div>)', re.S)
FIGURE_NUMBER = re.compile(r"<strong>Figure ([0-9.]+)\.</strong> ([^<]*)")


def esc(text):
    return html.escape(str(text), quote=True)


def figure_buttons(text):
    """Every figure a chapter places gets a button that asks Claude about it, named by its number
    and caption as the page already escapes them, or by its id where the caption carries no
    number."""
    def one(match):
        fig = match.group(0)
        num = FIGURE_NUMBER.search(fig)
        if num:
            caption = num.group(2).strip().replace('"', "&quot;")
            subject = f"Figure {num.group(1)}" + (f": {caption}" if caption else "")
        else:
            subject = f"figure {match.group(1) or 'on this page'}"
        button = f'<button class="button ask-fig" type="button" data-subject="{subject}">Ask about this figure</button>'
        if not BUTTONS_END.search(fig):
            # a figure with no record has no button row of its own; it gets one for this button
            return fig.replace("</figure>", f'<div class="buttons">{button}</div></figure>', 1)
        return BUTTONS_END.sub(lambda b: b.group(1) + button + b.group(2), fig, count=1)
    return FIGURE.sub(one, text)


def record_links(text, repo, sha):
    """"The record" points at the figure's record on GitHub at the built commit, since the records
    are not among the artifact's files."""
    return RECORD_LINK.sub(
        lambda m: f'href="https://github.com/{repo}/blob/{sha}/docs/textbook/figures/{m.group(1)}/{m.group(2)}.json"', text)


def edition_line(repo, sha, built):
    return (f'<p class="edition">This edition was built from <a href="https://github.com/{esc(repo)}/commit/{esc(sha)}">'
            f'{esc(sha[:7])}</a> on {esc(built)}; the repository is the source and this copy is republished after each merge to '
            f'its default branch. A figure that came from an exported artifact opens that artifact&#x27;s own page here, and '
            f'Ask Claude answers from the page you are on.</p>')


def transform(text, name, repo, sha, built):
    text = record_links(text, repo, sha)
    text = figure_buttons(text)
    text = text.replace("</style>", THEME_CSS + "</style>", 1)
    text = text.replace('<html lang="en">', f'<html lang="en" data-repo="{esc(repo)}">', 1)
    text = text.replace("</body>", ASK_HTML + '<script src="ask.js" defer></script></body>', 1)
    if name == "index.html":
        text = text.replace("</h1>", "</h1>" + edition_line(repo, sha, built), 1)
    return text


def page_proper(text, repo):
    """index.html as the Artifact tool takes its own file: no document skeleton, the title and the
    style first, then what the body held, the head's scripts after it. The data-repo attribute the
    other pages carry on html goes on by a script, since the html tag is the skeleton's."""
    style = re.search(r"<style>.*?</style>", text, re.S).group(0)
    head_scripts = "".join(re.findall(r"<script>.*?</script>", text.split("<body>", 1)[0], re.S))
    body = re.search(r"<body>(.*)</body>", text, re.S).group(1)
    return (f"<title>{TITLE}</title>\n" + style + "\n"
            + f'<script>document.documentElement.setAttribute("data-repo", "{esc(repo)}");</script>\n'
            + body + head_scripts + "\n")


def too_big(path):
    limit = TEXT_LIMIT if path.suffix.lower() in TEXT_SUFFIXES else BINARY_LIMIT
    return path.stat().st_size > limit


def left_out(site, rel):
    """What the edition does not carry: the site's marker, and every figure record, a JSON under
    figures/ with an image or a page of its own name beside it, as tools/textbook_site.py tells a
    record from the data a figure is drawn from; the data stays."""
    if rel.name == MARKER:
        return True
    if rel.parts[:1] == ("figures",) and rel.suffix == ".json":
        return any((site / rel).with_suffix(ext).exists() for ext in (".svg", ".png", ".html"))
    return False


def copy_site(site, out):
    """The site's files other than its top-level pages, as they are, keeping the tree: the figures,
    the exported artifacts and anything else the site serves; the paths copied, and the paths
    left out for their size."""
    copied, skipped = [], []
    for p in sorted(site.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(site)
        if left_out(site, rel) or (len(rel.parts) == 1 and rel.suffix == ".html"):
            continue
        if too_big(p):
            skipped.append(rel.as_posix())
            continue
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        copied.append(target)
    return copied, skipped


def batches(files, out):
    """The files grouped under the per-publish limits, as paths relative to out, in the order
    given."""
    groups, group, size = [], [], 0
    for f in files:
        n = f.stat().st_size
        if group and (len(group) >= PER_PUBLISH_FILES or size + n > PER_PUBLISH_BYTES):
            groups.append(group)
            group, size = [], 0
        group.append(f.relative_to(out).as_posix())
        size += n
    if group:
        groups.append(group)
    return groups


def built_words(text):
    """The edition's date as the page shows it, from the commit's date in ISO 8601 (git's %cI,
    with Z or an offset), in UTC to the minute; a date that does not parse stops the build,
    since a wrong edition line would outlive the run that wrote it."""
    try:
        when = dt.datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"--built {text!r} is not an ISO 8601 date")
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def build(site, out, repo, sha, built):
    """Write the edition into out, emptied first, and return the summary batches.json holds."""
    site, out = Path(site), Path(out)
    if not (site / MARKER).exists():
        raise SystemExit(f"{site}: not a textbook tools/textbook_site.py built")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    built = built_words(built)
    written = []
    for p in sorted(site.glob("*.html")):
        text = transform(p.read_text(encoding="utf-8"), p.name, repo, sha, built)
        if p.name == "index.html":
            text = page_proper(text, repo)
        (out / p.name).write_text(text, encoding="utf-8")
        written.append(out / p.name)
    (out / "ask.js").write_text(ASK_JS.strip() + "\n", encoding="utf-8")
    written.append(out / "ask.js")
    copied, skipped = copy_site(site, out)
    written += copied
    files = [f for f in written if f != out / "index.html"]
    total = sum(f.stat().st_size for f in written)
    summary = {"repo": repo, "sha": sha, "built": built, "files": len(written), "bytes": total,
               "batches": batches(files, out), "skipped": skipped}
    (out / "batches.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("site", help="the folder tools/textbook_site.py wrote")
    parser.add_argument("out", help="the folder to write the artifact's files into, emptied first")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="OWNER/NAME, for the record links and the edition line")
    parser.add_argument("--sha", required=True, help="the commit the site was built from")
    parser.add_argument("--built", required=True, help="that commit's date, ISO 8601 (git show -s --format=%%cI)")
    args = parser.parse_args(argv)
    summary = build(args.site, args.out, args.repo, args.sha, args.built)
    pages = sum(1 for b in summary["batches"] for f in b if f.startswith("artifacts/") and f.endswith("/index.html"))
    print(f"{summary['files']} files, {summary['bytes'] / 1e6:.1f} MB, {len(summary['batches'])} publish batches; "
          f"{pages} artifact pages; {len(summary['skipped'])} files over the size limit left out")
    for s in summary["skipped"]:
        print("left out:", s)
    over = []
    if summary["files"] > VERSION_FILES:
        over.append(f"{summary['files']} files is over the artifact's version limit of {VERSION_FILES}")
    if summary["bytes"] > VERSION_BYTES:
        over.append(f"{summary['bytes']} bytes is over the artifact's version limit of {VERSION_BYTES}")
    for line in over:
        print("too large:", line)
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
