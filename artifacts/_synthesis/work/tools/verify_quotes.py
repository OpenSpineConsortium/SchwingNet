"""Match every candidate's quotes and values against the artifacts' plain texts, so a
candidate the book carries is one whose words are in the source, not only in a reader's
memory of it. Matching is by normalised substring: a quote is found when its whole
normalised text, its parts around an ellipsis or an editor's bracketed words, or one of its
48-character windows is in the normalised text, and last when its parts are there once
spacing is ignored, since some pages are extracted one character to a line."""
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, __import__("os").path.dirname(__file__))
from render_inventory import ASCII_MAP


def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    for k, v in ASCII_MAP.items():
        s = s.replace(k, v)
    s = s.lower()
    s = re.sub(r"[|*_`#>\[\]()\"']", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


TEXTS = {}
RAW = {}
# An editor's words in square brackets, such as "[the owner]" where a quote named a person,
# stand for words the source has, so a quote is matched around them as around an ellipsis.
# A bracket that holds a digit is the source's own, such as an interval, and is matched.
GAP = re.compile(r"\.\.\.|\u2026|\[[A-Za-z][^\]\d]*\]")


def required_dir(var, below=""):
    """A folder the caller must name: with another session's default path every quote reads
    "no text" and the page looks clean, so a missing one stops the run instead."""
    path = os.environ.get(var, "")
    if not path or not os.path.isdir(path + below):
        raise SystemExit(f"{var} must name an existing folder{' holding ' + below.strip('/') if below else ''}; it is {path!r}")
    return path


def repos():
    """The two checkouts' artifacts/ folders, named by SYNTH_SCHWINGNET and SYNTH_SYMPHONY."""
    return {"SchwingNet": required_dir("SYNTH_SCHWINGNET", "/artifacts") + "/artifacts",
            "symphony-template": required_dir("SYNTH_SYMPHONY", "/artifacts") + "/artifacts"}


def text_of(text_dir, aid):
    """The plain text extracted from the page, then every text-like file of the artifact's
    folder (the page's own scripts and data hold numbers the extraction dropped)."""
    if aid not in TEXTS:
        try:
            with open(f"{text_dir}/{aid}.txt", encoding="utf-8") as handle:
                TEXTS[aid] = norm(handle.read())
        except OSError:
            TEXTS[aid] = None
        import html
        repo, folder = aid.split("/", 1)
        chunks = []
        for root, _dirs, files in os.walk(f"{repos()[repo]}/{folder}"):
            for f in sorted(files):
                if f.rsplit(".", 1)[-1].lower() in ("html", "htm", "js", "json", "md", "css", "txt", "svg", "csv"):
                    try:
                        with open(os.path.join(root, f), encoding="utf-8", errors="replace") as handle:
                            chunks.append(handle.read())
                    except OSError:
                        pass
        raw = html.unescape(re.sub(r"<[^>]+>", " ", "\n".join(chunks)))
        RAW[aid] = norm(raw) if chunks else None
    return TEXTS[aid]


def raw_of(aid):
    return RAW.get(aid)


def found(quote, text, raw=None):
    """Whole quote, else an ellipsis-split part, else the longest 48-char window; in the
    extracted text first, then in the artifact's raw files (reported with a raw- prefix)."""
    r = found_in(quote, text)
    if r in ("absent", "no-text") and raw is not None:
        r2 = found_in(quote, raw)
        if r2 not in ("absent", "no-text", "no-quote"):
            return "raw-" + r2
    return r


# The answers of found() that put a quote in the text it was looked for in.
HIT = ("whole", "parts", "window", "spacing", "raw-whole", "raw-parts", "raw-window", "raw-spacing")


def artifact_ids(text_dir):
    """Every artifact that has an extracted text, as repo/folder."""
    return sorted(f"{repo}/{name[:-4]}" for repo in os.listdir(text_dir) if os.path.isdir(f"{text_dir}/{repo}")
                  for name in os.listdir(f"{text_dir}/{repo}") if name.endswith(".txt"))


def place(text_dir, quote, own, other):
    """Where a skeptic's quote is: in its own artifact, only in the other one, only in a third
    ("elsewhere:" and its id, as when a verdict quotes the later page that makes a statement
    stale), or nowhere. A verdict merged at the wrong index would quote some other candidate's
    artifacts, so every answer but own and empty is for a person to read."""
    if not (quote or "").strip():
        return "empty"
    if own and found(quote, text_of(text_dir, own), raw_of(own)) in HIT:
        return "own"
    if other and found(quote, text_of(text_dir, other), raw_of(other)) in HIT:
        return "other"
    for aid in artifact_ids(text_dir):
        if aid not in (own, other) and found(quote, text_of(text_dir, aid), raw_of(aid)) in HIT:
            return "elsewhere:" + aid
    return "absent"


def found_in(quote, text):
    if text is None:
        return "no-text"
    q = norm(quote)
    if not q:
        return "no-quote"
    if q in text:
        return "whole"
    parts = [n for n in (norm(p) for p in GAP.split(quote)) if len(n) >= 12]
    if parts and all(p in text for p in parts):
        return "parts"
    if len(q) > 48:
        for i in range(0, len(q) - 48 + 1, 8):
            if q[i:i + 48] in text:
                return "window"
    flat = text.replace(" ", "")
    if all(p.replace(" ", "") in flat for p in parts or [q]):
        return "spacing"
    return "absent"


def value_found(value, text, raw=None):
    nums = re.findall(r"\d[\d,]*\.?\d*", value or "")
    if not nums:
        return "no-number"
    def count(t):
        return 0 if t is None else len([n for n in nums if n.lower() in t or n.replace(",", "") in t])
    h = count(text)
    if h == len(nums):
        return "all"
    hr = count(raw)
    if hr == len(nums):
        return "raw-all"
    return "some" if max(h, hr) else "none"


def main(text_dir, numbers, contradictions, dst):
    N = json.load(open(numbers))
    C = json.load(open(contradictions))
    out = {"numbers": [], "clusters": []}
    for c in N["candidates"]:
        ta, tb = text_of(text_dir, c["artifact_a"]), text_of(text_dir, c["artifact_b"])
        ra, rb = raw_of(c["artifact_a"]), raw_of(c["artifact_b"])
        out["numbers"].append({"quote_a": found(c["quote_a"], ta, ra), "quote_b": found(c["quote_b"], tb, rb),
                               "value_a": value_found(c["value_a"], ta, ra), "value_b": value_found(c["value_b"], tb, rb)})
    for cl in C:
        rows = []
        for c in cl["found"]["candidates"]:
            ta = text_of(text_dir, c["artifact_a"])
            tb = text_of(text_dir, c["artifact_b"]) if c.get("artifact_b") else None
            rows.append({"quote_a": found(c["quote_a"], ta, raw_of(c["artifact_a"])),
                         "quote_b": found(c["quote_b"], tb, raw_of(c["artifact_b"])) if c.get("artifact_b") else "none-named"})
        out["clusters"].append({"cluster": cl["cluster"], "rows": rows})
    json.dump(out, open(dst, "w"), indent=1)
    from collections import Counter
    print("numbers quote_a", Counter(r["quote_a"] for r in out["numbers"]))
    print("numbers quote_b", Counter(r["quote_b"] for r in out["numbers"]))
    print("numbers value_a", Counter(r["value_a"] for r in out["numbers"]))
    print("numbers value_b", Counter(r["value_b"] for r in out["numbers"]))
    for cl in out["clusters"]:
        print(cl["cluster"], "quote_a", Counter(r["quote_a"] for r in cl["rows"]), "quote_b", Counter(r["quote_b"] for r in cl["rows"]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
