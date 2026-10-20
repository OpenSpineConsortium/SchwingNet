"""The living documents: lessons whose commands the required check runs,
notebooks generated from them, and a site built from the lessons, the
guides, the code's own docstrings and the test suite's results.

A lesson is a Markdown file under docs/learn/ whose fenced blocks marked
"bash run" are commands and whose blocks marked "output" say what the block
before them prints. `test` runs every lesson in a practice folder of its own
and fails when an output no longer appears, so a lesson cannot drift from
the code it teaches: what a reader sees on the page is what the vendored
release does today. The comparison is by lines, in order, each expected line
found within an actual one, so a lesson quotes the part that matters and not
a hash or a date.

Each block runs in a bash of its own and opens with `cd "$LAB"`, the
practice folder, written on the page so a reader pasting it gets the same,
because that is how a notebook's %%bash cells run; the notebook made from a
lesson (`notebooks`) is then the same commands, cell for cell, and `check`
fails when a notebook is out of date with its lesson. A lesson's one block
marked "bash setup" makes $LAB for a reader at a terminal; the check makes
its own, and a notebook's first cell takes its place. In the check the
library is tools/sdlc_protocol; in a notebook it is the public library's
newest release, found and cloned by that first cell, so a notebook needs no
access to this repository and does not go stale when a release is vendored.

`check` also holds the code to its own documentation, as Javadoc's lint
does: every module under tools/ and scripts/ opens with a docstring and
every shell script with a comment, since the Reference page is made from
them. `report` runs the test suite and writes each test's result as JSON,
and `site` builds the static site that .github/workflows/docs.yml publishes.

    python3 tools/living_docs.py test
    python3 tools/living_docs.py check
    python3 tools/living_docs.py notebooks
    python3 tools/living_docs.py report results.json
    python3 tools/living_docs.py site _site --tests results.json --repo OWNER/NAME --sha SHA
"""

import argparse
import ast
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LESSONS = ROOT / "docs" / "learn"
NOTEBOOKS = LESSONS / "notebooks"
LIBRARY_URL = "https://github.com/OpenSpineConsortium/symphony-protocol"
FENCE = re.compile(r"^```(.*)$")
BLOCK_SECONDS = 60

# git reads none of the reader's settings and leaves no background job
# behind in a practice folder that is about to be deleted
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_DATE": "2026-10-20T09:00:00Z", "GIT_COMMITTER_DATE": "2026-10-20T09:00:00Z",
    "GIT_CONFIG_COUNT": "4",
    "GIT_CONFIG_KEY_0": "gc.auto", "GIT_CONFIG_VALUE_0": "0",
    "GIT_CONFIG_KEY_1": "gc.autoDetach", "GIT_CONFIG_VALUE_1": "false",
    "GIT_CONFIG_KEY_2": "maintenance.auto", "GIT_CONFIG_VALUE_2": "false",
    "GIT_CONFIG_KEY_3": "maintenance.autoDetach", "GIT_CONFIG_VALUE_3": "false",
}


# Reading a lesson

def parse(text):
    """The lesson as segments in order: ("md", text), ("run", code),
    ("output", text), or ("code", text) for any other fenced block."""
    segments, prose, lines = [], [], text.splitlines()
    i = 0
    while i < len(lines):
        opened = FENCE.match(lines[i])
        if not opened:
            prose.append(lines[i])
            i += 1
            continue
        info, body, i = opened.group(1).strip(), [], i + 1
        while i < len(lines) and not lines[i].startswith("```"):
            body.append(lines[i])
            i += 1
        i += 1
        if "".join(prose).strip():
            segments.append(("md", "\n".join(prose)))
        prose = []
        segments.append((kind_of(info), "\n".join(body), info))
    if "".join(prose).strip():
        segments.append(("md", "\n".join(prose)))
    return [s if len(s) == 3 else (*s, "") for s in segments]


def kind_of(info):
    if info == "bash run":
        return "run"
    if info == "bash setup":
        return "setup"
    if info == "output":
        return "output"
    return "code"


def lessons():
    return sorted(p for p in LESSONS.glob("[0-9]*.md"))


def steps(path):
    """Each command of a lesson with the output it promises, or None."""
    segments = parse(path.read_text(encoding="utf-8"))
    found = []
    for k, (kind, body, _) in enumerate(segments):
        if kind != "run":
            continue
        after = segments[k + 1] if k + 1 < len(segments) else None
        found.append((body, after[1] if after and after[0] == "output" else None))
    return found


# Running a lesson

def run_block(code, lab, library):
    # a caller's GIT_DIR or GIT_INDEX_FILE, as a hook has, would point the
    # lesson's git at the real repository
    inherited = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env = dict(inherited, **GIT_ENV, LAB=str(lab), PYTHONPATH=str(library))
    try:
        done = subprocess.run(["bash", "-c", code], env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=BLOCK_SECONDS)
    except subprocess.TimeoutExpired as stopped:
        return f"{stopped.output or ''}\n(stopped after {BLOCK_SECONDS} seconds)"
    return done.stdout


def missing_lines(expected, actual):
    """The first expected line not found, in order, within the actual lines;
    a line may match the same actual line as the one before it."""
    got = [line.strip() for line in actual.splitlines()]
    at = 0
    for want in (line.strip() for line in expected.splitlines()):
        if not want:
            continue
        while at < len(got) and want not in got[at]:
            at += 1
        if at == len(got):
            return want
    return None


def shown(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def test_lesson(path, library):
    problems = []
    with tempfile.TemporaryDirectory(prefix="symphony-lesson-") as lab:
        for n, (code, expected) in enumerate(steps(path), 1):
            actual = run_block(code, Path(lab), library)
            if expected is None:
                continue
            lost = missing_lines(expected, actual)
            if lost:
                printed = "\n    ".join(actual.splitlines()[-12:])
                problems.append(f"{shown(path)}: block {n} never printed {lost!r}; it printed:\n    {printed}")
    return problems


def test(_args):
    problems, count = [], 0
    for path in lessons():
        problems += test_lesson(path, ROOT / "tools")
        count += len(steps(path))
    for line in problems:
        print(line)
    if problems:
        return 1
    print(f"lessons ok ({len(lessons())} lessons, {count} blocks)")
    return 0


# Notebooks made from the lessons

def vendored_tag():
    first = (ROOT / "tools" / "VENDORED").read_text(encoding="utf-8").split()
    return "v" + first[1]


def setup_cell():
    return f'''# The practice folder, and the newest release of the public claim-protocol library.
import os, re, subprocess, tempfile
tags = subprocess.run(["git", "ls-remote", "--tags", "{LIBRARY_URL}"], capture_output=True, text=True, check=True).stdout
releases = sorted({{tuple(map(int, m)) for m in re.findall(r"refs/tags/v(\\d+)\\.(\\d+)\\.(\\d+)$", tags, re.M)}})
TAG = "v%d.%d.%d" % releases[-1]
LAB = tempfile.mkdtemp(prefix="symphony-lesson-")
LIBRARY = os.path.join(tempfile.mkdtemp(), "symphony-protocol")
subprocess.run(["git", "-c", "advice.detachedHead=false", "clone", "--quiet", "--depth", "1",
                "--branch", TAG, "{LIBRARY_URL}", LIBRARY], check=True)
os.environ.update({json.dumps(GIT_ENV)})
os.environ.update(LAB=LAB, PYTHONPATH=LIBRARY)
print("symphony-protocol", TAG, "; practice folder:", LAB)'''


def cell(kind, text):
    made = {"cell_type": kind, "metadata": {}, "source": text.splitlines(True)}
    if kind == "code":
        made.update(execution_count=None, outputs=[])
    return made


def notebook_of(path):
    cells = []
    for kind, body, _ in parse(path.read_text(encoding="utf-8")):
        if kind == "md" and body.strip():
            cells.append(cell("markdown", rewrite_links_for_notebook(body.strip("\n"))))
        elif kind == "setup":
            cells.append(cell("code", setup_cell()))
        elif kind == "run":
            cells.append(cell("code", f"%%bash\n{body}"))
        elif kind == "output":
            cells.append(cell("markdown", "You should see lines like these:\n\n```\n" + body + "\n```"))
        else:
            cells.append(cell("markdown", f"```{_}\n{body}\n```"))
    for n, made in enumerate(cells):
        made["id"] = f"cell-{n}"
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 5}


def rewrite_links_for_notebook(text):
    """A lesson's neighbours are notebooks too; any other relative link is
    one folder deeper from docs/learn/notebooks/ than from the lesson."""
    def moved(match):
        label, target = match.groups()
        if re.match(r"^(0\d-[a-z0-9-]+)\.md$", target):
            return f"[{label}]({target[:-3]}.ipynb)"
        if re.match(r"^([a-z]+:|#)", target):
            return match.group(0)
        return f"[{label}](../{target})"
    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", moved, text)


def notebook_text(path):
    return json.dumps(notebook_of(path), indent=1, ensure_ascii=True) + "\n"


def notebooks(args):
    stale = []
    NOTEBOOKS.mkdir(exist_ok=True)
    for path in lessons():
        target = NOTEBOOKS / (path.stem + ".ipynb")
        text = notebook_text(path)
        if target.exists() and target.read_text(encoding="utf-8") == text:
            continue
        if args.check:
            stale.append(target)
        else:
            target.write_text(text, encoding="utf-8")
            print(f"wrote {target.relative_to(ROOT)}")
    for target in stale:
        print(f"{target.relative_to(ROOT)}: out of date with its lesson; run python3 tools/living_docs.py notebooks")
    names = {p.stem for p in lessons()}
    orphans = [p for p in NOTEBOOKS.glob("*.ipynb") if p.stem not in names]
    for target in orphans:
        print(f"{target.relative_to(ROOT)}: no lesson of that name; delete it with its lesson")
    return 1 if stale or orphans else 0


# Holding the code to its documentation

def documented_modules():
    return sorted(list((ROOT / "tools").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))
                  + list((ROOT / "tools" / "sdlc_protocol").rglob("*.py")))


def shell_scripts():
    return sorted((ROOT / "scripts").glob("*.sh"))


def script_comment(path):
    """The comment block under a shell script's first line, without the #."""
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    kept = []
    for line in lines:
        if not line.startswith("#"):
            break
        kept.append(line[1:].strip())
    return "\n".join(kept).strip()


def lesson_shape(path):
    """A lesson has one setup block, before its first command, and every
    command opens in the practice folder, as a notebook cell does."""
    segments = parse(path.read_text(encoding="utf-8"))
    kinds = [kind for kind, _, _ in segments]
    problems = []
    if kinds.count("setup") != 1 or ("run" in kinds and kinds.index("setup") > kinds.index("run")):
        problems.append(f"{path.relative_to(ROOT)}: one block marked bash setup, before the first bash run block")
    for n, (kind, body, _) in enumerate(s for s in segments if s[0] == "run"):
        if not body.startswith('cd "$LAB"\n'):
            problems.append(f'{path.relative_to(ROOT)}: block {n + 1} does not open with cd "$LAB"')
    return problems


def check(args):
    problems = []
    for path in documented_modules():
        if not ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))):
            problems.append(f"{path.relative_to(ROOT)}: no module docstring; the Reference page is made from it")
    for path in shell_scripts():
        if not script_comment(path):
            problems.append(f"{path.relative_to(ROOT)}: no comment under its first line saying what it does and why")
    index = (LESSONS / "README.md").read_text(encoding="utf-8")
    for path in lessons():
        if f"({path.name})" not in index:
            problems.append(f"docs/learn/README.md: lesson {path.name} is not in the table")
        if not steps(path):
            problems.append(f"{path.relative_to(ROOT)}: no block marked bash run, so the check tests nothing")
        problems += lesson_shape(path)
    for line in problems:
        print(line)
    if problems:
        return 1
    stale = notebooks(argparse.Namespace(check=True))
    if not stale:
        print(f"living docs ok ({len(documented_modules())} modules, {len(shell_scripts())} scripts documented)")
    return stale


# The test suite's results, for the site

class Recorder(unittest.TextTestResult):
    """A result that keeps each test's outcome and time as well as
    printing the usual dots."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records, self.started = [], 0.0

    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def note(self, test, outcome):
        self.records.append({"id": test.id(), "outcome": outcome,
                             "seconds": round(time.monotonic() - self.started, 3)})

    def addSuccess(self, test):
        super().addSuccess(test)
        self.note(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.note(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self.note(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.note(test, "skipped")

    def addSubTest(self, test, subtest, err):
        # a test whose subtests fail is never reported by addFailure
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.note(subtest, "failed")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.note(test, "passed")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.note(test, "failed")


def report(args):
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT / "tests"))
    runner = unittest.TextTestRunner(resultclass=Recorder, verbosity=0, stream=sys.stderr)
    result = runner.run(suite)
    Path(args.out).write_text(json.dumps({"tests": result.records}, indent=1) + "\n", encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


# Markdown to HTML, the parts the guides use

INLINE_CODE = re.compile(r"`([^`]+)`")
LINK = re.compile(r"(!?)\[([^\]]+)\]\(([^)\s]+)\)")
STRONG = re.compile(r"\*\*([^*]+)\*\*")


def inline(text, link_for):
    codes = []

    def keep_code(match):
        codes.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    text = INLINE_CODE.sub(keep_code, text)
    text = html.escape(text, quote=False)

    def make_link(match):
        bang, label, target = match.groups()
        href = html.escape(safe_href(link_for(html.unescape(target))))
        if bang:
            return f'<img src="{href}" alt="{html.escape(html.unescape(label))}">'
        return f'<a href="{href}">{label}</a>'

    text = LINK.sub(make_link, text)
    text = STRONG.sub(r"<strong>\1</strong>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def safe_href(target):
    return target if not re.match(r"^\s*(javascript|data|vbscript):", target, re.I) else "#"


def cells_of(line):
    """A table row's cells, a pipe escaped as \\| or inside a code span
    staying in its cell."""
    cells, current, in_code, i = [], "", False, 0
    text = line.strip()
    text = text[1:] if text.startswith("|") else text
    text = text[:-1] if text.endswith("|") and not text.endswith("\\|") else text
    while i < len(text):
        ch = text[i]
        if ch == "\\" and text[i + 1:i + 2] == "|":
            current += "|"
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append(current.strip())
            current = ""
        else:
            current += ch
        i += 1
    cells.append(current.strip())
    return cells


def table(lines, link_for):
    rows = [cells_of(line) for line in lines]
    head, body = rows[0], rows[2:]
    out = ["<div class=\"table\"><table><thead><tr>"]
    out += [f"<th>{inline(c, link_for)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{inline(c, link_for)}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def block_html(kind, body, info):
    if kind == "setup":
        return f'<div class="run"><div class="tag">run it once, at the top of a clone</div><pre><code>{html.escape(body)}</code></pre></div>'
    if kind == "run":
        return f'<div class="run"><div class="tag">run it</div><pre><code>{html.escape(body)}</code></pre></div>'
    if kind == "output":
        return f'<div class="output"><div class="tag">you should see</div><pre><code>{html.escape(body)}</code></pre></div>'
    return f"<pre><code>{html.escape(body)}</code></pre>"


def prose_html(text, link_for):
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            anchor = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            out.append(f'<h{level} id="{anchor}">{inline(title, link_for)}</h{level}>')
            i += 1
        elif line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(table(rows, link_for))
        elif re.match(r"^\s*([-*]|\d+\.) ", line):
            ordered = bool(re.match(r"^\s*\d+\.", line))
            items = []
            while i < len(lines) and lines[i].strip():
                if re.match(r"^\s*([-*]|\d+\.) ", lines[i]) and not lines[i].startswith("   "):
                    items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t, link_for)}</li>" for t in items) + f"</{tag}>")
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(("#", "|")) \
                    and not re.match(r"^\s*([-*]|\d+\.) ", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(f"<p>{inline(' '.join(para), link_for)}</p>")
    return "\n".join(out)


def markdown_html(text, link_for):
    parts = []
    for kind, body, info in parse(text):
        parts.append(prose_html(body, link_for) if kind == "md" else block_html(kind, body, info))
    return "\n".join(parts)


# The site

class Site:
    """Which page each source becomes, and how a link from one resolves."""

    def __init__(self, out, repo, sha):
        self.out, self.repo, self.sha = Path(out), repo, sha
        self.pages = {}  # source path relative to ROOT -> page name

    def add(self, source, name):
        self.pages[source] = name

    def linker(self, source):
        here = (ROOT / source).parent

        def link_for(target):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                return target
            path, _, anchor = target.partition("#")
            resolved = (here / path).resolve()
            try:
                relative = resolved.relative_to(ROOT).as_posix()
            except ValueError:
                return target
            if relative in self.pages:
                return self.pages[relative] + (f"#{anchor}" if anchor else "")
            if resolved.suffix == ".svg" and resolved.exists():
                shutil.copy(resolved, self.out / resolved.name)
                return resolved.name
            if self.repo:
                kind = "tree" if resolved.is_dir() else "blob"
                return f"https://github.com/{self.repo}/{kind}/{self.sha or 'HEAD'}/{relative}" + (f"#{anchor}" if anchor else "")
            return relative

        return link_for


CSS = """
:root { --bg:#fbfaf7; --fg:#1d1d1f; --muted:#5d5d63; --line:#e3e0d8; --panel:#f3efe6;
        --accent:#8a5a14; --run:#eaf0f7; --runline:#4a6a8f; --out:#eef4ea; --outline:#5b7f4a; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#16171a; --fg:#ececee; --muted:#a2a2aa; --line:#2c2d33; --panel:#1f2024;
          --accent:#e0a85a; --run:#1b2533; --runline:#6f93bd; --out:#1c2a1d; --outline:#7fa66c; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:16px/1.6 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
header { border-bottom:1px solid var(--line); padding:14px 20px; display:flex; gap:16px; align-items:baseline; flex-wrap:wrap; }
header .brand { font-weight:700; font-size:18px; color:var(--fg); text-decoration:none; }
header .meta { color:var(--muted); font-size:13px; }
.wrap { display:flex; max-width:1180px; margin:0 auto; }
nav { width:240px; flex:none; padding:20px; border-right:1px solid var(--line); font-size:14px; }
nav h4 { margin:16px 0 6px; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }
nav a { display:block; padding:3px 0; color:var(--fg); text-decoration:none; }
nav a.here { color:var(--accent); font-weight:600; }
main { flex:1; min-width:0; padding:24px 32px 64px; max-width:860px; }
a { color:var(--accent); }
h1 { font-size:30px; line-height:1.25; margin-top:4px; }
h2 { margin-top:36px; border-top:1px solid var(--line); padding-top:20px; }
code { font:14px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
p code, li code, td code { background:var(--panel); padding:1px 5px; border-radius:4px; }
pre { background:var(--panel); padding:12px 14px; border-radius:8px; overflow-x:auto; margin:0; }
.run, .output { margin:14px 0; border-left:4px solid var(--runline); border-radius:8px; background:var(--run); }
.output { border-color:var(--outline); background:var(--out); }
.run pre, .output pre { background:transparent; }
.tag { font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); padding:8px 14px 0; }
.table { overflow-x:auto; }
table { border-collapse:collapse; margin:14px 0; font-size:14px; }
th, td { border:1px solid var(--line); padding:6px 9px; text-align:left; vertical-align:top; }
th { background:var(--panel); }
img { max-width:100%; height:auto; background:#fff; border-radius:8px; border:1px solid var(--line); }
.actions { display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 20px; }
.button { display:inline-block; padding:7px 14px; border:1px solid var(--line); border-radius:8px; background:var(--panel);
          color:var(--fg); text-decoration:none; font-size:14px; }
.verified { font-size:13px; color:var(--muted); border:1px solid var(--line); border-radius:8px; padding:8px 12px; margin:12px 0; }
.passed { color:var(--outline); } .failed, .error { color:#c0392b; }
@media (max-width: 760px) { .wrap { display:block; } nav { width:auto; border-right:0; border-bottom:1px solid var(--line); }
  main { padding:16px; } }
"""


def page(title, body, nav, meta):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - Symphony docs</title><style>{CSS}</style></head>
<body><header><a class="brand" href="index.html">Symphony docs</a><span class="meta">{meta}</span></header>
<div class="wrap"><nav>{nav}</nav><main>{body}</main></div></body></html>
"""


def title_of(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def nav_html(sections, here):
    out = []
    for heading, entries in sections:
        out.append(f"<h4>{html.escape(heading)}</h4>")
        for name, label in entries:
            mark = ' class="here"' if name == here else ""
            out.append(f'<a href="{name}"{mark}>{html.escape(label)}</a>')
    return "".join(out)


def lesson_actions(path, site):
    if not site.repo:
        return ""
    notebook = f"docs/learn/notebooks/{path.stem}.ipynb"
    colab = f"https://colab.research.google.com/github/{site.repo}/blob/{site.sha or 'main'}/{notebook}"
    codespace = (f"https://codespaces.new/{site.repo}?quickstart=1"
                 "&devcontainer_path=.devcontainer%2Fdemo%2Fdevcontainer.json")
    return (f'<div class="actions"><a class="button" href="{colab}">Open in Colab</a>'
            f'<a class="button" href="{codespace}">Open a Codespace</a></div>')


def verified_note(path, site):
    blocks = len(steps(path))
    commit = f" at commit {site.sha[:7]}" if site.sha else ""
    return (f'<div class="verified">Every one of the {blocks} commands on this page ran in CI{commit} against '
            f"symphony-protocol {vendored_tag()}, and printed what the page says it prints.</div>")


def reference_html(site):
    out = ["<h1>Reference</h1><p>Made from the code's own docstrings and script comments when the site is built, "
           "so it describes the code on this commit. <code>python3 tools/living_docs.py check</code> fails a pull "
           "request that adds a module without one.</p>"]
    groups = [("Tools", sorted((ROOT / "tools").glob("*.py"))),
              (f"The claim-protocol library, {vendored_tag()}", sorted((ROOT / "tools" / "sdlc_protocol").rglob("*.py"))),
              ("Scripts", sorted((ROOT / "scripts").glob("*.py")) + shell_scripts())]
    link_for = site.linker("docs/start/README.md")
    for heading, paths in groups:
        out.append(f"<h2>{html.escape(heading)}</h2>")
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix == ".sh":
                doc = script_comment(path)
            else:
                doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or ""
            first = doc.split("\n\n")[0].replace("\n", " ")
            href = html.escape(link_for("../../" + relative))
            out.append(f'<h3 id="{relative}"><a href="{href}"><code>{relative}</code></a></h3><p>{html.escape(first)}</p>')
    return "\n".join(out)


def tests_html(results, site):
    tests = results.get("tests", []) if results else []
    by_file = {}
    for record in tests:
        by_file.setdefault(record["id"].split(".")[0], []).append(record)
    passed = sum(1 for r in tests if r["outcome"] == "passed")
    ci = f"https://github.com/{site.repo}/actions/workflows/ci.yml" if site.repo else "../../.github/workflows/ci.yml"
    out = ["<h1>Tests</h1>",
           f"<p>Every test the repository has ever added lives in <code>tests/</code> and runs on every pull request "
           f"and push in the required check, <code>bash scripts/check.sh</code>. This page lists the results of the run "
           f"that built it. Run them again at any time: on your machine with "
           f"<code>python3 -m unittest discover -s tests</code>, or on GitHub from "
           f'<a href="{html.escape(ci)}">the CI workflow</a> with its Run workflow button.</p>']
    if not tests:
        out.append("<p>This build was made without test results.</p>")
        return "\n".join(out)
    out.append(f'<p class="verified">{passed} of {len(tests)} tests passed in {len(by_file)} files.</p>')
    link_for = site.linker("docs/start/README.md")
    out.append("<div class=\"table\"><table><thead><tr><th>File</th><th>Tests</th><th>Passed</th><th>Not passed</th></tr></thead><tbody>")
    for name in sorted(by_file):
        records = by_file[name]
        bad = [r["id"].split(".")[-1] for r in records if r["outcome"] not in ("passed", "skipped")]
        href = html.escape(link_for(f"../../tests/{name}.py"))
        good = sum(1 for r in records if r["outcome"] == "passed")
        out.append(f'<tr><td><a href="{href}"><code>{name}.py</code></a></td><td>{len(records)}</td>'
                   f'<td class="passed">{good}</td><td class="failed">{html.escape(", ".join(bad))}</td></tr>')
    out.append("</tbody></table></div>")
    return "\n".join(out)


def site(args):
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        if not (out / ".nojekyll").exists():
            print(f"{out}: not empty and not a site this tool built; give an empty or new folder")
            return 1
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    built = Site(out, args.repo, args.sha)
    guides = [("docs/learn/README.md", "index.html"), ("docs/start/capabilities.md", "capabilities.html")]
    learn = [(p.relative_to(ROOT).as_posix(), p.stem + ".html") for p in lessons()]
    for source, name in guides + learn:
        built.add(source, name)
    sections = [("Start", [("index.html", "Learn by doing"), ("capabilities.html", "What Symphony can do")]),
                ("Lessons", [(name, title_of((ROOT / source).read_text(encoding="utf-8"))) for source, name in learn]),
                ("Reference", [("reference.html", "Code reference"), ("tests.html", "Tests")])]
    commit = f"commit {args.sha[:7]}, " if args.sha else ""
    meta = html.escape(f"built from {commit}symphony-protocol {vendored_tag()}")
    for source, name in guides + learn:
        text = (ROOT / source).read_text(encoding="utf-8")
        body = markdown_html(text, built.linker(source))
        path = ROOT / source
        if path.parent == LESSONS and path.name != "README.md":
            head, _, rest = body.partition("\n")
            body = head + lesson_actions(path, built) + verified_note(path, built) + rest
        (out / name).write_text(page(title_of(text), body, nav_html(sections, name), meta), encoding="utf-8")
    results = json.loads(Path(args.tests).read_text(encoding="utf-8")) if args.tests else None
    extras = {"reference.html": ("Code reference", reference_html(built)),
              "tests.html": ("Tests", tests_html(results, built))}
    for name, (title, body) in extras.items():
        (out / name).write_text(page(title, body, nav_html(sections, name), meta), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")
    print(f"site written to {out} ({len(list(out.glob('*.html')))} pages)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("test", help="run every lesson's commands and compare their outputs")
    sub.add_parser("check", help="every module documented, every lesson listed, the notebooks up to date")
    made = sub.add_parser("notebooks", help="write each lesson's notebook under docs/learn/notebooks/")
    made.add_argument("--check", action="store_true", help="fail, writing nothing, when one is out of date")
    reported = sub.add_parser("report", help="run the test suite and write each test's result as JSON")
    reported.add_argument("out")
    built = sub.add_parser("site", help="build the static documentation site")
    built.add_argument("out")
    built.add_argument("--tests", help="the JSON report to show on the Tests page")
    built.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="OWNER/NAME, for links to files and Colab")
    built.add_argument("--sha", default="", help="the commit the site describes")
    args = parser.parse_args(argv)
    return {"test": test, "check": check, "notebooks": notebooks, "report": report, "site": site}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
