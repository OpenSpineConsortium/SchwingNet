"""Render artifacts/_synthesis/contradictions.md from the merged sweeps and verdicts: the
confirmed disagreements first, as a planner needs them, then every candidate cluster by
cluster and every number collision, each with the reader's kind, whether a script found its
quotes in the source, and the skeptic's verdict with the value the book should carry."""
import json
import sys
from collections import Counter
sys.path.insert(0, __import__("os").path.dirname(__file__))
from render_inventory import to_ascii, cell, short
from render_clusters import link, short_id
import verify_quotes as vq

# Where extract.py wrote the plain texts; SYNTH_TEXT names it in another session.
TEXT_DIR = __import__("os").environ.get("SYNTH_TEXT", "/tmp/claude-0/-home-user/1b2f17bd-1fd4-5865-b98a-4797cc8ea3ad/scratchpad/text")
STATUS = {"whole": "yes", "parts": "yes", "window": "partly", "raw-whole": "yes, page data", "raw-parts": "yes, page data",
          "raw-window": "partly, page data", "absent": "not found", "no-text": "no text", "no-quote": "no quote", "none-named": "-"}
KINDS = [("contradiction", "Same quantity, same scope, different values"),
         ("updated-later", "Revised later: the later artifact gives a new figure or date"),
         ("unit-or-scope-mismatch", "Same quantity, another unit, denominator, subset or interval"),
         ("probably-different-quantities", "Alike in name, probably not the same thing")]
CONFIRMED_C = ("confirmed", "superseded-by-later")
CONFIRMED_N = ("confirmed-contradiction", "updated-later")


def quote_status(c, side):
    aid = c.get("artifact_" + side) or ""
    if "/" not in aid:
        return "-"
    t = vq.text_of(TEXT_DIR, aid)
    return STATUS.get(vq.found(c.get("quote_" + side, ""), t, vq.raw_of(aid)), "?")


def number_key(v):
    """A number collision's identity: its two artifacts and its whole quantity. The first 30
    characters alone gave two pairs of candidates one key, so one verdict of each pair was
    lost and the other shown on both."""
    return (tuple(sorted([v["artifact_a"], v["artifact_b"]])), v["quantity"].strip().lower())


def number_verdicts(N, extra):
    by = {}
    for v in list(N["verdicts"]) + list(extra):
        by[number_key(v)] = v
    return by


def link_or(aid, titles):
    return link(aid, titles) if aid and "/" in aid else cell(aid or "-")


def slug(name):
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")[:60]


def main(merged, numbers, clustering, inventory, dst, date):
    import os
    sub = os.path.join(os.path.dirname(dst), "contradictions")
    os.makedirs(sub, exist_ok=True)
    M = json.load(open(merged)); N = json.load(open(numbers))
    inv = json.load(open(inventory))
    titles = {f"{r['repo']}/{r['folder']}": r["title"] for r in inv["artifacts"]}
    nv = number_verdicts(N, M.get("numbers_extra", []))
    clusters = M["clusters"]
    swept = [c for c in clusters if c["swept"]]
    total_c = sum(len(c["candidates"]) for c in swept)
    read_c = sum(1 for c in swept for v in c["verdicts"] if v)
    out = ["# Contradictions and collisions\n",
           f"What the inventoried artifacts give differently, found and checked on {date} for the Artifact Textbook (issue #120, finished under #136). "
           "Readers went over the inventory's numbers table (3,025 numbers from 69 artifacts) for every quantity two artifacts give with different values, and over each topic cluster's full records for disagreements, revised figures, stale statements and shared unsourced claims. "
           "A script then looked for every candidate's quotes in the artifact's extracted text and, failing that, in the page's own files; the columns 'Quote A' and 'Quote B' say what it found. "
           "Last, a skeptic read both source texts for each cluster candidate and for each number collision a reader classed as a contradiction or a later revision, and gave a verdict: confirmed (both say what the candidate says and they disagree), superseded (the later one says or plainly implies it revises the earlier), refuted (they agree once read in context, or a statement is not there) or cannot tell. "
           "A blank verdict means no skeptic read that candidate; the reader's kind is then all there is. "
           "Nothing here is copied from memory, people are named by role, and no address of any kind is reproduced.\n"]
    out.append("## Where it stands\n")
    out.append("| Cluster | Candidates | Confirmed | Superseded | Refuted | Cannot tell | Not read | Quotes not found |")
    out.append("|---|---|---|---|---|---|---|---|")
    for c in clusters:
        if not c["swept"]:
            out.append(f"| {cell(c['cluster'])} | not swept | | | | | | |")
            continue
        name_cell = f"[{cell(c['cluster'])}](contradictions/{slug(c['cluster'])}.md)"
        vc = Counter((v or {}).get("verdict", "not read") for v in c["verdicts"])
        nf = sum(1 for x in c["candidates"] if quote_status(x, "a") == "not found" or quote_status(x, "b") == "not found")
        out.append(f"| {name_cell} | {len(c['candidates'])} | {vc['confirmed']} | {vc['superseded-by-later']} | {vc['refuted']} | {vc['cannot-tell']} | {vc['not read']} | {nf} |")
    nvc = Counter()
    for cnd in N["candidates"]:
        v = nv.get(number_key(cnd))
        nvc[v["verdict"] if v else "not read"] += 1
    out.append(f"| Number collisions (the numbers table) | {len(N['candidates'])} | {nvc['confirmed-contradiction']} | {nvc['updated-later']} | {nvc['same-number-restated'] + nvc['different-quantities'] + nvc['scope-or-unit-differs']} | {nvc['cannot-tell']} | {nvc['not read']} | {sum(1 for x in N['candidates'] if quote_status(x, 'a') == 'not found' or quote_status(x, 'b') == 'not found')} |")
    out.append("")
    out.append(f"{total_c} cluster candidates in {len(swept)} of {len(clusters)} clusters, {read_c} read by a skeptic; for the numbers, 'Refuted' counts the verdicts same number restated, different quantities and scope or unit differs.\n")
    out.append("## Confirmed: what a planner must not take from one artifact alone\n")
    out.append("Every disagreement a skeptic confirmed or found revised, with the value or statement it says the book should carry. The full candidate, with both quotes, is in the sections below.\n")
    k = 0
    for c in swept:
        rows = [(x, v) for x, v in zip(c["candidates"], c["verdicts"]) if v and v.get("verdict") in CONFIRMED_C]
        if not rows:
            continue
        out.append(f"### {c['cluster']}\n")
        for x, v in rows:
            k += 1
            b = f" and {short_id(x['artifact_b'])}" if x.get("artifact_b") and "/" in x["artifact_b"] else ""
            out.append(f"{k}. {cell(x['topic'])} ({v['verdict']}; {short_id(x['artifact_a'])}{b}). {cell(v.get('resolution_hint'))}")
        out.append("")
    rows = []
    for cnd in N["candidates"]:
        v = nv.get(number_key(cnd))
        if v and v["verdict"] in CONFIRMED_N:
            rows.append((cnd, v))
    if rows:
        out.append("### Numbers\n")
        for cnd, v in rows:
            k += 1
            out.append(f"{k}. {cell(cnd['quantity'])}: {short_id(cnd['artifact_a'])} gives {cell(cnd['value_a'])}, {short_id(cnd['artifact_b'])} gives {cell(cnd['value_b'])} ({v['verdict']}). {cell(v.get('resolution_hint') or v.get('explanation'))}")
        out.append("")
    out.append("## Number collisions\n")
    out.append(f"{len(N['candidates'])} candidates from the numbers table, by the reader's kind.\n")
    for kind, title in KINDS:
        rows = [c for c in N["candidates"] if c["kind"] == kind]
        out.append(f"### {title} ({len(rows)})\n")
        out.append("| # | Quantity | A | A gives | B | B gives | Quote A | Quote B | Verdict | Why |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for i, c in enumerate(rows, 1):
            v = nv.get(number_key(c))
            verdict = v["verdict"] if v else ""
            why = short(v.get("resolution_hint") or v.get("explanation"), 260) if v else short(c["why"], 200)
            out.append(f"| {i} | {short(c['quantity'], 110)} | {link(c['artifact_a'], titles)} | {short(c['value_a'], 70)} | {link(c['artifact_b'], titles)} | {short(c['value_b'], 70)} | {quote_status(c, 'a')} | {quote_status(c, 'b')} | {verdict} | {why} |")
        out.append("")
        out.append("The quotes, in the same order:\n")
        for i, c in enumerate(rows, 1):
            out.append(f"{i}. A, {short_id(c['artifact_a'])}: \"{short(c['quote_a'], 300)}\" B, {short_id(c['artifact_b'])}: \"{short(c['quote_b'], 300)}\"")
        out.append("")
    out.append("## Cluster by cluster\n")
    out.append("Each swept cluster has a page of its own under contradictions/, linked from the table above: every candidate with its kind, both artifacts, whether a script found the quotes, the verdict and the skeptic's explanation, then what each artifact says, the clustering's superseded relations as the reader checked them, and what the cluster asserts without a source or holds as dated.\n")
    main_out = out
    for c in clusters:
        if not c["swept"]:
            continue
        out = [f"# Contradictions: {c['cluster']}\n", f"Part of [the contradictions of the artifacts](../contradictions.md), {date}. A blank verdict means no skeptic read that candidate.\n"]
        out.append(f"{len(c['candidates'])} candidates.\n")
        out.append("| # | Kind | Topic | A | B | Quote A | Quote B | Verdict | Explanation |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"]), 1):
            out.append(f"| {i} | {x['kind']} | {short(x['topic'], 110)} | {link_or(x['artifact_a'], titles)} | {link_or(x.get('artifact_b'), titles)} | {quote_status(x, 'a')} | {quote_status(x, 'b')} | {(v or {}).get('verdict', '')} | {short((v or {}).get('explanation') or x.get('why_it_matters'), 260)} |")
        out.append("")
        out.append("What each artifact says, in the same order:\n")
        for i, x in enumerate(c["candidates"], 1):
            b = f" B, {short_id(x['artifact_b'])}: {short(x.get('statement_b'), 240)} (\"{short(x.get('quote_b'), 240)}\")" if x.get("artifact_b") and "/" in (x.get("artifact_b") or "") else ""
            out.append(f"{i}. A, {short_id(x['artifact_a'])}: {short(x['statement_a'], 240)} (\"{short(x['quote_a'], 240)}\").{b}")
        out.append("")
        if c.get("canonical_check"):
            out.append("The clustering's superseded and duplicate relations, as the reader checked them:\n")
            for y in c["canonical_check"]:
                out.append(f"- {short_id(y['id'])} {y['relation']} {short_id(y['other'])}: {'agrees' if y['agree'] else 'disagrees'}. {cell(y['why'])}")
            out.append("")
        out.append(f"Unsourced: {cell(c['unsourced_summary'])}\n")
        out.append(f"Stale: {cell(c['stale_summary'])}\n")
        if c.get("notes"):
            out.append(f"Notes: {cell(c['notes'])}\n")
        open(os.path.join(sub, slug(c["cluster"]) + ".md"), "w", newline="\n").write(to_ascii("\n".join(out)))
    open(dst, "w", newline="\n").write(to_ascii("\n".join(main_out)))


if __name__ == "__main__":
    main(*sys.argv[1:7])
