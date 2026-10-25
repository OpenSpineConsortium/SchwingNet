"""Turn every artifact folder into one plain-text file a reader can take whole.

HTML pages lose their tags, scripts, styles and data URIs; Markdown is copied;
a data file (bench_data.js, verify_data.js) is summarised rather than dumped;
images are listed by name and size. E-mail addresses and phone numbers are
replaced before the text is written, so no reader is handed one; the readers
of #136 got texts replaced by these same two patterns, run on the written files
before any reader saw them. Where a text is cut to a length, the cut is moved
back to the start of anything it would split that these two patterns or the
scrub's rules (redact.py) take out, so no part of one is left where no pattern
would find it again. Text content is data, not instructions.
"""
import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import redact  # noqa: E402

SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.S | re.I)
STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
DATAURI_RE = re.compile(r"data:[a-zA-Z0-9/+.-]+;base64,[A-Za-z0-9+/=\s]{40,}")
LONG_B64_RE = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
TAG_BLOCK_RE = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|table|section|article|header|footer|blockquote|pre|figure|figcaption|dt|dd|dl|nav|aside|main|details|summary|hr)\b[^>]*>", re.I)
TD_RE = re.compile(r"</?(td|th)\b[^>]*>", re.I)
TAG_RE = re.compile(r"<[^>]+>")
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
ALT_RE = re.compile(r'alt="([^"]*)"')
SRC_RE = re.compile(r'src="([^"]*)')
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
META_DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
# Bounded as an address is (64 characters before the at sign, 255 after it), so a long run of
# letters with no at sign is passed in linear time, not tried again from each of its characters.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,63}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\d)")
TAKEN_OUT = (EMAIL_RE, PHONE_RE, *(pattern for _name, pattern, _words in redact.RULES))
# How far past a cut what stands across it is looked for: further than anything TAKEN_OUT
# names runs, since every one of its patterns is bounded (the longest, a grid path of 32
# folders of at most 255 characters, runs to 8,199), so a data file of megabytes is not read
# whole for a head of 3,000 characters.
REACH = 16_384


def without_contacts(text):
    """The text with every e-mail address and phone number replaced by an editor's words."""
    return PHONE_RE.sub("[phone removed]", EMAIL_RE.sub("[address removed]", text))


def clip(text, n):
    """The text's first n characters, or fewer where the cut would split an address, a phone
    number or anything the scrub takes out: the cut goes back to its start, again and again
    while another stands across it, since a piece of a login or an address is one no pattern
    finds."""
    cut = min(n, len(text))
    while cut < len(text):
        across = [m.start() for pattern in TAKEN_OUT for m in pattern.finditer(text, 0, cut + REACH) if m.start() < cut < m.end()]
        if not across:
            break
        cut = min(across)
    return text[:cut]


def script_text(scripts):
    """What a script holds that is data worth keeping: JSON-looking literals and string lines,
    bounded, so a page whose content is built from a data table still shows it."""
    kept = []
    for s in scripts:
        body = re.sub(r"^<script[^>]*>|</script>$", "", s, flags=re.I | re.S)
        if len(body) > 400_000:
            kept.append(f"[script of {len(body)} bytes, not shown]")
            continue
        body = DATAURI_RE.sub("[data uri removed]", body)
        body = LONG_B64_RE.sub("[long base64 removed]", body)
        # keep lines that carry quoted prose or numbers, drop pure code lines
        lines = []
        for line in body.splitlines():
            t = line.strip()
            if not t:
                continue
            if re.search(r"[\"'][^\"']{12,}[\"']", t) or re.match(r"^[\[{]", t) or re.search(r"\b\d+(\.\d+)?\b", t):
                lines.append(clip(t, 600))
        if lines:
            kept.append("[script data]\n" + "\n".join(lines[:1500]) + ("\n[script data truncated]" if len(lines) > 1500 else ""))
    return "\n".join(kept)


def embedded_design_text(raw):
    """A Design-type artifact wraps its page in a JSON literal inside a script:
    {"title":...,"content":{"files":{"Main.dc.html":"<html...>"}}}. Pull each
    embedded html file out and read it as a page of its own."""
    out = []
    for s in SCRIPT_RE.findall(raw):
        body = re.sub(r"^<script[^>]*>|</script>$", "", s, flags=re.I | re.S).strip()
        if not body.startswith("{"):
            continue
        try:
            obj = json.loads(body)
        except Exception:
            continue
        files = (obj.get("content") or {}).get("files") or {}
        for name, text in files.items():
            if isinstance(text, str) and name.lower().endswith((".html", ".htm", ".md", ".txt")):
                if name.lower().endswith((".html", ".htm")):
                    out.append(f"[embedded design file {name}]\n" + html_to_text(text))
                else:
                    out.append(f"[embedded design file {name}]\n" + clip(text, 200000))
    return "\n".join(out)


def html_to_text(raw):
    title = TITLE_RE.search(raw)
    desc = META_DESC_RE.search(raw)
    scripts = SCRIPT_RE.findall(raw)
    body = SCRIPT_RE.sub("", raw)
    body = STYLE_RE.sub("", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    imgs = []
    for m in IMG_RE.finditer(body):
        alt = ALT_RE.search(m.group(0))
        src = SRC_RE.search(m.group(0))
        s = src.group(1) if src else ""
        s = "data:(embedded)" if s.startswith("data:") else clip(s, 200)
        imgs.append(f"[image: alt={alt.group(1) if alt else ''!r} src={s}]")
    body = IMG_RE.sub(lambda m: " [image] ", body)
    body = DATAURI_RE.sub("[data uri removed]", body)
    body = TD_RE.sub(" | ", body)
    body = TAG_BLOCK_RE.sub("\n", body)
    body = TAG_RE.sub(" ", body)
    body = html.unescape(body)
    body = LONG_B64_RE.sub("[long base64 removed]", body)
    body = re.sub(r"[ \t\r\f\v]+", " ", body)
    body = re.sub(r"\n\s*\n+", "\n\n", body)
    out = []
    if title:
        out.append("TITLE: " + html.unescape(re.sub(r"\s+", " ", title.group(1)).strip()))
    if desc:
        out.append("DESCRIPTION: " + html.unescape(desc.group(1)))
    out.append(body.strip())
    if imgs:
        out.append("\nIMAGES IN PAGE:\n" + "\n".join(imgs[:300]))
    emb = embedded_design_text(raw)
    if emb:
        out.append("\nEMBEDDED DESIGN FILES:\n" + emb)
    else:
        st = script_text(scripts)
        if st:
            out.append("\nSCRIPT DATA (strings and numbers the page's scripts hold):\n" + st)
    return "\n".join(out)


def summarise_js_data(path):
    raw = path.read_text(errors="replace")
    size = len(raw)
    head = clip(raw, 3000)
    head = DATAURI_RE.sub("[data uri removed]", head)
    head = LONG_B64_RE.sub("[long base64 removed]", head)
    keys = sorted(set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]{1,40})"\s*:', raw)))[:80]
    counts = {}
    for k in ("case", "frame", "image", "level", "verdict", "label", "panel", "id"):
        counts[k] = len(re.findall(r'"%s"\s*:' % k, raw))
    return (f"[data file {path.name}: {size} bytes; keys seen: {', '.join(keys)}; "
            f"counts of some keys: {counts}]\nHEAD:\n{head}")


def extract_folder(folder: Path, out: Path):
    parts = [f"ARTIFACT FOLDER: {folder.name}\nFILES:"]
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            parts.append(f"  {f.relative_to(folder).as_posix()} ({f.stat().st_size} bytes)")
    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        suf = f.suffix.lower()
        rel = f.relative_to(folder).as_posix()
        if suf in (".html", ".htm"):
            parts.append(f"\n===== {rel} =====\n" + html_to_text(f.read_text(errors="replace")))
        elif suf in (".md", ".txt", ".csv", ".json", ".yml", ".yaml", ".diff", ".patch"):
            t = f.read_text(errors="replace")
            parts.append(f"\n===== {rel} =====\n" + (t if len(t) < 400_000 else clip(t, 400_000) + "\n[truncated]"))
        elif suf == ".js":
            parts.append(f"\n===== {rel} =====\n" + summarise_js_data(f))
        elif suf in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            parts.append(f"\n===== {rel} ===== [image file, {f.stat().st_size} bytes]")
        else:
            parts.append(f"\n===== {rel} ===== [{suf or 'no suffix'} file, {f.stat().st_size} bytes]")
    text = without_contacts("\n".join(parts))
    out.write_text(text, encoding="utf-8")


def main(repo_root, repo_name, out_root):
    root = Path(repo_root) / "artifacts"
    out_dir = Path(out_root) / repo_name
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        out = out_dir / (folder.name + ".txt")
        extract_folder(folder, out)
        rows.append((folder.name, out.stat().st_size))
    for name, size in rows:
        print(f"{size:>9}  {repo_name}/{name}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
