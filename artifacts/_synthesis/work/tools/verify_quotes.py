"""Match every candidate's quotes and values against the artifacts' plain texts, so a
candidate the book carries is one whose words are in the source, not only in a reader's
memory of it. Matching is by normalised substring: a quote is found when its whole
normalised text, or its longest 48-character window, is in the normalised text."""
import json
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
REPOS = {"SchwingNet": "/home/user/SchwingNet/artifacts", "symphony-template": "/home/user/symphony-template/artifacts"}


def text_of(text_dir, aid):
    """The plain text extracted from the page, then every text-like file of the artifact's
    folder (the page's own scripts and data hold numbers the extraction dropped)."""
    if aid not in TEXTS:
        try:
            TEXTS[aid] = norm(open(f"{text_dir}/{aid}.txt", encoding="utf-8").read())
        except OSError:
            TEXTS[aid] = None
        import html
        import os
        repo, folder = aid.split("/", 1)
        chunks = []
        for root, _dirs, files in os.walk(f"{REPOS[repo]}/{folder}"):
            for f in sorted(files):
                if f.rsplit(".", 1)[-1].lower() in ("html", "htm", "js", "json", "md", "css", "txt", "svg", "csv"):
                    try:
                        chunks.append(open(os.path.join(root, f), encoding="utf-8", errors="replace").read())
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


def found_in(quote, text):
    if text is None:
        return "no-text"
    q = norm(quote)
    if not q:
        return "no-quote"
    if q in text:
        return "whole"
    parts = [p.strip() for p in re.split(r"\.\.\.|\u2026", quote) if len(norm(p)) >= 12]
    if parts and all(norm(p) in text for p in parts):
        return "parts"
    if len(q) > 48:
        for i in range(0, len(q) - 48 + 1, 8):
            if q[i:i + 48] in text:
                return "window"
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
