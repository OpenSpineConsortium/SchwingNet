"""Check one chapter file against the brief: ASCII and LF, the title and label
lines, the four closing sections, the length, the Markdown the site renders,
links that resolve, and the privacy shapes. Prints each problem; exits 1 if any.

    python3 -I -B lint.py $W/docs/textbook/NN-slug.md
"""
import json
import re
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[5]
SYN = WT / "artifacts" / "_synthesis"
PLAN = json.loads((SYN / "work" / "out" / "toc-hand.json").read_text())
INV = json.loads((SYN / "inventory.json").read_text())
LINKS = {r["link"] for r in INV["artifacts"]}
ST_FOLDERS = {r["folder"] for r in INV["artifacts"] if r["repo"] == "symphony-template"}
CHAPTERS = {c["number"]: c for p in PLAN["parts"] for c in p["chapters"]}
SECTIONS = ["What we know", "What we do not know", "What would change our mind", "Provenance"]
LINK = re.compile(r"(!?)\[([^\]]+)\]\(([^)\s]+)\)")
# A figure, as the figure spec places it: an image line of its own under figures/NN/, then an italic
# caption line. The site renders that pair; nothing else may use an image or italics.
FIGURE = re.compile(r"^!\[[^\]]+\]\(figures/\d\d/[\w.-]+\.(svg|png)\)$")
CAPTION = re.compile(r"^\*Figure \d+\.\d+\. [^*]+\*$")
PRIVACY = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "an e-mail address"),
    (re.compile(r"\(?\b\d{3}\)?[ .-]\d{3}[ .-]\d{4}\b"), "a phone number"),
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "a network address"),
    (re.compile(r"\bgo2432\b|gregoryamdg|\bgschwing\b|Gregory-Schwing", re.I), "a login"),
    (re.compile(r"\bGreg(ory)?\b"), "the owner's name (use the owner)"),
    (re.compile(r"\bDr\.? [A-Z][a-z]+"), "a person's name (use their role)"),
    (re.compile(r"\b(Chou|Schwiebert|Zhizhong|Schehr|Tekumulla)\b"), "a person's name (use their role)"),
    (re.compile(r"(^|[\s(`])(/rs/|/wsu/|/home/|~/|/scratch/|/mnt/)"), "a grid or machine path"),
    (re.compile(r"forms\.(office|gle)|docs\.google\.com/forms|forms\.microsoft"), "a form's link"),
    (re.compile(r"(sk-ant-|ghp_|github_pat_|xox[bp]-|AKIA[0-9A-Z]{12})"), "a credential's shape"),
]


def problems(path):
    out = []
    raw = path.read_bytes()
    if b"\r" in raw:
        out.append("CR characters: use LF line ends")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", "replace")
        bad = sorted({ch for ch in text if ord(ch) > 127})
        out.append("non-ASCII characters: " + " ".join(f"U+{ord(c):04X}" for c in bad[:20]))
    lines = text.splitlines()
    number = path.name[:2]
    plan = CHAPTERS.get(number)
    if not plan:
        return out + [f"no chapter {number} in the plan"]
    if path.as_posix() != (WT / plan["file"]).as_posix():
        out.append(f"file should be {plan['file']}")
    want = f"# {number} {plan['title']}"
    if not lines or lines[0] != want:
        out.append(f"first line should be exactly: {want}")
    if len(lines) < 3 or not lines[2].startswith("Label: " + plan["confidentiality"]):
        out.append(f"third line should start: Label: {plan['confidentiality']}")
    heads = [l[3:].strip() for l in lines if l.startswith("## ")]
    for s in SECTIONS:
        if s not in heads:
            out.append(f"missing section: ## {s}")
    if [h for h in heads if h in SECTIONS] != SECTIONS:
        out.append("the four closing sections should come last, in the order: " + ", ".join(SECTIONS))
    prose = []
    in_table = False
    for l in lines:
        if l.startswith("## Provenance"):
            in_table = True
        if not in_table and not l.lstrip().startswith("|"):
            prose.append(l)
    words = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'.,%-]*", "\n".join(prose)))
    floor, ceiling = (1800, 6500) if number != "26" else (1500, 3500)
    if not floor <= words <= ceiling:
        out.append(f"{words} words of prose before the provenance table; aim for 2,000 to 6,000")
    fenced = False
    for i, l in enumerate(lines, 1):
        if l.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue
        bare = re.sub(r"`[^`]*`", "", l)
        figure = FIGURE.match(l) or (CAPTION.match(l) and i > 1 and FIGURE.match(lines[i - 2]))
        if re.match(r"^\s*>", l):
            out.append(f"line {i}: a blockquote, which the site does not render")
        if re.match(r"^\s{2,}([-*]|\d+\.) ", l):
            out.append(f"line {i}: a nested list, which the site does not render")
        if not figure and (re.search(r"(?<![*\w])\*(?!\*)[^*\n]+\*(?!\*)", bare) or re.search(r"(?<![\w_])_[^_\n]+_(?![\w_])", bare)):
            out.append(f"line {i}: italics, which the site does not render")
        if re.search(r"<[A-Za-z/!][^>]*>", bare):
            out.append(f"line {i}: raw HTML or an angle bracket tag")
        if re.match(r"^#{4,} ", l) or re.match(r"^# ", l) and i != 1:
            out.append(f"line {i}: use ## and ### headings only below the title")
        for rx, what in PRIVACY:
            if rx.search(l):
                out.append(f"line {i}: {what}: {rx.search(l).group(0)!r}")
        for bang, label, target in LINK.findall(l):
            if bang and not figure:
                out.append(f"line {i}: an image, which the brief does not use")
            out.extend(f"line {i}: {p}" for p in link_problems(path, target))
    return out


def link_problems(path, target):
    if target.startswith("https://claude.ai/"):
        return [] if target in LINKS else [f"a claude.ai link no record carries: {target}"]
    if target.startswith("https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/"):
        folder = target.rstrip("/").rsplit("/", 1)[1]
        return [] if folder in ST_FOLDERS else [f"no symphony-template artifact {folder}"]
    if re.match(r"^[a-z]+:", target):
        return [] if target.startswith("https://") else [f"a link that is not https: {target}"]
    if target.startswith("#"):
        return []
    rel = target.split("#", 1)[0]
    resolved = (path.parent / rel).resolve()
    if not resolved.exists():
        if resolved.parent == (WT / "docs" / "textbook").resolve() and re.match(r"\d\d-", resolved.name):
            names = {Path(c["file"]).name for c in CHAPTERS.values()}
            return [] if resolved.name in names else [f"no chapter file {resolved.name} in the plan"]
        return [f"a link to a file that does not exist: {target}"]
    try:
        resolved.relative_to(WT)
    except ValueError:
        return [f"a link outside the repository: {target}"]
    return []


def main(argv):
    path = Path(argv[0]).resolve()
    found = problems(path)
    for p in found:
        print(p)
    print("ok" if not found else f"{len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
