"""Keep one marked section of a Markdown file up to date.

The checkpoint skill rewrites the block between two HTML-comment markers at
the end of CLAUDE.md and touches nothing else in the file. The markers are
cswap's, so `cswap checkpoint write` and the skill update the same block and
neither leaves a second copy behind. The function is a copy of cswap's
upsert_marked_section and keeps its behaviour: replace between the first
marker pair, append after one blank line when there is none, write the whole
file when it is empty, keep everything outside the markers byte for byte, and
keep a CRLF file CRLF.

Command line: `python3 tools/marked_section.py CLAUDE.md < section.md`
rewrites the file in place and prints what it did.
"""

import sys
from pathlib import Path

MARK_BEGIN = "<!-- cswap:checkpoint:begin -->"
MARK_END = "<!-- cswap:checkpoint:end -->"


def upsert_marked_section(existing, section):
    """``existing`` with ``section`` between the first marker pair.

    Replaced in place when the pair exists, appended after one blank line when
    it does not, the whole file when there is none. Everything outside the
    markers is kept byte for byte, and a CRLF file stays CRLF. An unpaired
    marker is a file someone edited by hand, which is refused rather than
    guessed at.
    """
    if not existing:
        return section + "\n"
    nl = "\r\n" if "\r\n" in existing else "\n"
    block = section.replace("\n", nl)
    begin = existing.find(MARK_BEGIN)
    end = existing.find(MARK_END, begin) if begin != -1 else existing.find(MARK_END)
    if begin == -1 and end == -1:
        if existing.endswith(nl + nl):
            sep = ""
        elif existing.endswith(nl):
            sep = nl
        else:
            sep = nl + nl
        return existing + sep + block + nl
    if begin == -1 or end == -1:
        raise ValueError(
            f"the file has an unpaired checkpoint marker ({MARK_BEGIN} / "
            f"{MARK_END}). Remove or pair the markers by hand, then rerun."
        )
    return existing[:begin] + block + existing[end + len(MARK_END) :]


def is_well_formed(section):
    """A section the command line accepts: the begin marker first, the end
    marker last, so a stray paste can never eat the rest of the file."""
    return section.startswith(MARK_BEGIN) and section.endswith(MARK_END)


def outcome(existing, updated):
    """One word for what the rewrite did, for the line the command prints."""
    if existing == updated:
        return "unchanged"
    if existing and MARK_BEGIN in existing and MARK_END in existing:
        return "replaced"
    return "appended"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: marked_section.py FILE < section.md", file=sys.stderr)
        return 2
    path = Path(argv[0])
    # The section arrives as text; its own line endings are normalised so the
    # file's ending, not the terminal's, decides what is written.
    section = sys.stdin.read().replace("\r\n", "\n").rstrip("\n")
    if not is_well_formed(section):
        print(
            f"{path}: the section on stdin must start with {MARK_BEGIN} "
            f"and end with {MARK_END}",
            file=sys.stderr,
        )
        return 2
    # open() with newline="" keeps the file's own line endings on every
    # Python this project supports; Path.read_text() takes newline only from
    # 3.13, and GitHub's runners carry 3.12.
    existing = None
    if path.is_file():
        with open(path, encoding="utf-8", newline="") as handle:
            existing = handle.read()
    try:
        updated = upsert_marked_section(existing, section)
    except ValueError as problem:
        print(f"{path}: {problem}", file=sys.stderr)
        return 1
    if updated != existing:
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
    print(f"{path}: section {outcome(existing, updated)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
