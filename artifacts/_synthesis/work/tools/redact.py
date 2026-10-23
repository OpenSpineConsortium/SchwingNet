"""Replace, in the synthesis records and pages, what the folder's rule keeps out of them: a
person's name where a role will do, a grid login, a grid volume's path, a network range, a
form's link, a staff member's title at a named employer, a settings page's address and another
group's folder name. Each is replaced by an editor's words in square brackets, which the quote
check matches around (verify_quotes.GAP), so a quote that loses a name is still found in its
source.

Usage: redact.py FILE...
  Rewrites each .json file in place with the layout the tools write (indent 1, its own final
  newline kept) and each .md file as text, and prints how many replacements each rule made."""
import json
import re
import sys
from collections import Counter

# A login is two lowercase letters and four digits, as the university gives them. Two letters and
# a year (ai2024) are a name's, not a login, and a token after a hyphen is the random end of an
# artifact's folder name, which an id holds and a redaction must never change.
LOGIN = r"[a-z]{2}(?!(?:19|20)\d\d\b)\d{4}"

RULES = [
    ("the owner's first name", re.compile(r"\b[Gg]reg(?=_|\b)"), "[the owner]"),
    ("a grid data root that names a login", re.compile(r"/rs/[A-Za-z0-9_]+/[a-z]{2}\d{4}/data/"),
     "[the lab volume's data root]/"),
    # At most 32 folders before the login, more than any grid path holds, so a long run of path
    # parts with no login in it is passed in linear time, not tried again from each slash.
    ("a grid folder that names a login", re.compile(r"(?:/[A-Za-z0-9_.-]+){1,32}/" + LOGIN + r"(?=/|\b)"),
     "[a grid folder named by a login]"),
    ("a login at the university's mail name", re.compile(r"\b" + LOGIN + r"@wayne(?:\.edu)?\b"), "[the owner's login]"),
    ("a login", re.compile(r"(?<![-/._])\b" + LOGIN + r"\b"), "[the owner's login]"),
    ("the university's network range", re.compile(r"\b\d{1,3}\.\d{1,3}\.x\.x\b"), "[the university's network range]"),
    ("a form's short link", re.compile(r"(?:https?://)?forms\.gle/[A-Za-z0-9]+"), "[the registration form's link]"),
    ("a form's long link", re.compile(r"(?:https?://)?docs\.google\.com/forms/[^\s\"'<>)\]]+"), "[a form's link]"),
    # The research storage's group volumes, named or not by a login: the rules above take a path
    # that names one, and this one the volume of any other, since no grid path is kept.
    ("a grid volume", re.compile(r"/rs/rs_grp_[A-Za-z0-9_]+"), "[the lab volume]"),
    ("a staff title beside its employer", re.compile(r"\bOperations Assistant\b"), "[a club staff contact]"),
    ("an Actions secrets settings page", re.compile(r"https?://github\.com/[^\s\"')]+/settings/secrets/actions/?"),
     "[a repository's Actions secrets page]"),
    ("another group's study folder", re.compile(r"\bu\d{3}-[A-Za-z]+(?:-[A-Za-z]+)*-study\b"),
     "[another group's study folder]"),
]


def scrub(text, counts):
    for name, pattern, words in RULES:
        text, n = pattern.subn(words, text)
        if n:
            counts[name] += n
    return text


def walk(value, counts):
    """Every string of a JSON value, keys included, since a field name can carry a name."""
    if isinstance(value, str):
        return scrub(value, counts)
    if isinstance(value, list):
        return [walk(v, counts) for v in value]
    if isinstance(value, dict):
        return {scrub(k, counts): walk(v, counts) for k, v in value.items()}
    return value


def redact(path):
    counts = Counter()
    raw = open(path, encoding="utf-8").read()
    if path.endswith(".json"):
        text = json.dumps(walk(json.loads(raw), counts), indent=1) + ("\n" if raw.endswith("\n") else "")
    else:
        text = scrub(raw, counts)
    if text != raw:
        open(path, "w", encoding="utf-8", newline="\n").write(text)
    return counts


def main(paths):
    total = Counter()
    for path in paths:
        counts = redact(path)
        total += counts
        if counts:
            print(path, dict(counts))
    print("in all", dict(total))


if __name__ == "__main__":
    main(sys.argv[1:])
