"""Check that the repository's documents still work as a Claude project.

CLAUDE.md, the rules, the skills and docs/memory/ are the project's
instructions and memory: an import that resolves to nothing, a memory file
the index forgets, or a secret pasted into a document is a broken project,
not a typo. The checks are cheap and run before every pull request from
scripts/check.sh. One line per problem, "path: problem"; exit 1 when there is
any, 0 with a count otherwise.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

MARK_BEGIN = "<!-- cswap:checkpoint:begin -->"
MARK_END = "<!-- cswap:checkpoint:end -->"
CLAUDE_MD = "CLAUDE.md"
MEMORY_DIR = Path("docs") / "memory"
MEMORY_INDEX = "MEMORY.md"
EVENT_LOG_SUFFIX = ".events.json"
SKIPPED_FOLDERS = {".git", "__pycache__"}
# Where the documents live that must stay ASCII with LF endings.
PLAIN_TEXT_ROOTS = (".claude", "docs", "tools", ".github")
PLAIN_TEXT_FILES = (CLAUDE_MD, "README.md")

# An import is any "@path" outside code spans and fenced code; Claude Code
# follows it wherever it stands in the line, so the check must too. The
# character before the "@" may not be a word character, so an e-mail
# address is not an import.
IMPORT_TOKEN = re.compile(r"(?<![\w`])@([^\s`]+)")
CODE_SPAN = re.compile(r"`[^`]*`")
FENCE_LINE = re.compile(r"^\s*(```|~~~)")
LINK_TARGET = re.compile(r"\]\(([^)\s]+)\)")

# The patterns are assembled from pieces so this file never matches itself:
# a check that flagged its own source would have to be excluded, and an
# exclusion is one more place a real secret could hide. The tests build
# their fake secrets the same way.
SECRET_SHAPES = (
    ("Anthropic API key", "sk-" + "ant-" + r"[A-Za-z0-9_-]{20,}"),
    ("GitHub token", "gh" + "p_" + r"[A-Za-z0-9]{30,}"),
    ("GitHub fine-grained token", "github_" + "pat_" + r"[A-Za-z0-9_]{30,}"),
    ("GitHub OAuth token", "gh" + "o_" + r"[A-Za-z0-9]{30,}"),
    ("AWS access key", "AK" + "IA" + r"[0-9A-Z]{16}"),
    ("private key", "-----BEGIN " + r"[A-Z ]*" + "PRIVATE " + "KEY-----"),
)
SECRET_PATTERNS = tuple((name, re.compile(shape)) for name, shape in SECRET_SHAPES)


def tracked_files(root):
    """The files the checks look at, relative to root.

    With a .git, git decides: tracked files plus the ones not yet added and
    not ignored, since a secret in a file about to be committed is the one
    worth catching. Without one, every file except .git's own and Python's
    caches, which .gitignore would hide too.
    """
    if (root / ".git").exists():
        listing = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, check=True,
        ).stdout.decode("utf-8", "surrogateescape")
        names = [n for n in listing.split("\0") if n]
    else:
        names = [
            str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file() and not SKIPPED_FOLDERS & set(p.relative_to(root).parts)
        ]
    return sorted(Path(n) for n in names if (root / n).is_file())


def read_text(path):
    """The file as text, or None when it is not UTF-8 and so not a document."""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return None


def check_markers(root):
    """CLAUDE.md carries the checkpoint marker pair exactly once, in order."""
    path = root / CLAUDE_MD
    if not path.is_file():
        return [f"{CLAUDE_MD}: missing"]
    text = read_text(path)
    if text is None:
        return [f"{CLAUDE_MD}: not UTF-8"]
    problems = []
    for marker in (MARK_BEGIN, MARK_END):
        count = text.count(marker)
        if count != 1:
            problems.append(f"{CLAUDE_MD}: marker {marker} appears {count} times, expected once")
    if not problems and text.find(MARK_BEGIN) > text.find(MARK_END):
        problems.append(f"{CLAUDE_MD}: the end marker comes before the begin marker")
    return problems


def imports(text):
    """The (line number, path) of every import outside code spans and
    fenced code, in the order they stand."""
    found = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE_LINE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in IMPORT_TOKEN.finditer(CODE_SPAN.sub("", line)):
            found.append((number, match.group(1)))
    return found


def check_imports(root):
    """Every @import in CLAUDE.md names a file that exists."""
    text = read_text(root / CLAUDE_MD) if (root / CLAUDE_MD).is_file() else None
    if text is None:
        return []
    problems = []
    for number, target in imports(text):
        where = Path(target).expanduser()
        if not where.is_absolute():
            where = root / where
        if not where.exists():
            problems.append(f"{CLAUDE_MD}: line {number} imports @{target}, which does not exist")
    return problems


def link_targets(text):
    """The local link targets of a Markdown text, without fragments; links to
    the web are not files and are left alone."""
    targets = []
    for target in LINK_TARGET.findall(text):
        if "://" in target or target.startswith("#"):
            continue
        targets.append(target.split("#", 1)[0])
    return targets


def check_memory_index(root):
    """MEMORY.md lists every fact file under docs/memory/, and every file it
    links to exists; a fact the index forgets is a fact no session reads."""
    folder = root / MEMORY_DIR
    if not folder.is_dir():
        return []
    index = folder / MEMORY_INDEX
    if not index.is_file():
        return [f"{MEMORY_DIR.as_posix()}/{MEMORY_INDEX}: missing"]
    text = read_text(index)
    if text is None:
        return [f"{MEMORY_DIR.as_posix()}/{MEMORY_INDEX}: not UTF-8"]
    where = f"{MEMORY_DIR.as_posix()}/{MEMORY_INDEX}"
    targets = link_targets(text)
    listed = {(folder / t).resolve() for t in targets}
    problems = []
    for fact in sorted(folder.rglob("*.md")):
        if fact == index:
            continue
        if fact.resolve() not in listed:
            problems.append(f"{where}: does not list {fact.relative_to(folder).as_posix()}")
    for target in targets:
        if not (folder / target).exists():
            problems.append(f"{where}: links to {target}, which does not exist")
    return problems


def check_no_event_logs(files):
    """No .events.json anywhere: those logs belong to a session, not to the
    repository, and docs/history/ takes prose instead."""
    return [f"{f.as_posix()}: event log committed" for f in files if f.name.endswith(EVENT_LOG_SUFFIX)]


def check_secrets(root, files):
    """No secret-shaped string in any text file."""
    problems = []
    for rel in files:
        text = read_text(root / rel)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    problems.append(f"{rel.as_posix()}: line {number} looks like a {name}")
    return problems


def is_plain_text_place(rel):
    """Whether a path is one the ASCII and LF rule covers."""
    return rel.parts[0] in PLAIN_TEXT_ROOTS or rel.as_posix() in PLAIN_TEXT_FILES


def check_ascii_lf(root, files):
    """ASCII and LF under the document folders: a stray smart quote or a CRLF
    file renders differently on every machine and in every diff. A file that
    is not UTF-8 at all is an image or another binary, not a document, and
    the rule does not reach it."""
    problems = []
    for rel in files:
        if not is_plain_text_place(rel):
            continue
        data = (root / rel).read_bytes()
        if read_text(root / rel) is None:
            continue
        if b"\r" in data:
            number = data[: data.index(b"\r")].count(b"\n") + 1
            problems.append(f"{rel.as_posix()}: line {number} has a CR (CRLF line ending)")
        if any(byte > 127 for byte in data):
            first = next(i for i, byte in enumerate(data) if byte > 127)
            number = data[:first].count(b"\n") + 1
            problems.append(f"{rel.as_posix()}: line {number} is not ASCII")
    return problems


def run_checks(root):
    """Every problem found under root, and how many files were looked at."""
    files = tracked_files(root)
    problems = []
    problems += check_markers(root)
    problems += check_imports(root)
    problems += check_memory_index(root)
    problems += check_no_event_logs(files)
    problems += check_secrets(root, files)
    problems += check_ascii_lf(root, files)
    return problems, len(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the repository's documents.")
    parser.add_argument("--root", default=".", help="the repository root (default: the current directory)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    problems, count = run_checks(root)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"docs ok ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
