"""Run the document checks the moment an edit touches the documents.

Claude Code runs this as a PostToolUse hook on Edit and Write
(.claude/settings.json). CI runs the same checks (tools/check_docs.py)
on every pull request, but a session that hears about a broken import
or a forgotten index line only from CI has long moved on; exit code 2
feeds the problems straight back while the edit is still in hand. An
edit outside the document folders, or a payload this script cannot
read, passes in silence: CI remains the fence that counts.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_docs

# The places whose files are the project's instructions and memory, the
# same ones tools/check_docs.py holds to ASCII and LF.
DOCUMENT_ROOTS = {".claude", "docs", "tools", ".github"}
DOCUMENT_FILES = {"CLAUDE.md", "README.md"}


def is_document(root, file_path):
    """Whether an edited path is one the document checks cover."""
    try:
        rel = Path(file_path).resolve().relative_to(Path(root).resolve())
    except (ValueError, OSError):
        return False
    return rel.parts[0] in DOCUMENT_ROOTS or rel.as_posix() in DOCUMENT_FILES


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    if not file_path or not is_document(root, file_path):
        return 0
    try:
        problems, _ = check_docs.run_checks(Path(root).resolve())
    except Exception:
        return 0
    if not problems:
        return 0
    print("The document checks fail after this edit (tools/check_docs.py):", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
