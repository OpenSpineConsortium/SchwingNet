"""Render artifacts/_synthesis/contradictions.md: every quantity two artifacts give
differently and every disagreement a cluster reader found, each with its quotes and with
whether the quotes were found in the source by script, so a planner reads the status of a
candidate and not only the candidate."""
import json
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from render_inventory import to_ascii, cell, short
from render_clusters import link, short_id


KINDS = [("contradiction", "Same quantity, same scope, different values"),
         ("updated-later", "Revised later: the later artifact gives a new figure or date"),
         ("unit-or-scope-mismatch", "Same quantity, another unit, denominator, subset or interval"),
         ("probably-different-quantities", "Alike in name, probably not the same thing")]
STATUS = {"whole": "yes", "parts": "yes (in parts)", "window": "partly", "raw-whole": "yes (page data)", "raw-parts": "yes (page data, parts)",
          "raw-window": "partly (page data)", "absent": "not found", "no-text": "no text", "no-quote": "no quote", "none-named": "-"}


def status(s):
    return STATUS.get(s, s)


def main(numbers, contradictions, verification, clustering, inventory, dst, date):
    N = json.load(open(numbers)); C = json.load(open(contradictions)); V = json.load(open(verification))
    J = json.load(open(clustering))["judged"]; inv = json.load(open(inventory))
    titles = {f"{r['repo']}/{r['folder']}": r["title"] for r in inv["artifacts"]}
    verdicts = {}
    for v in N["verdicts"]:
        verdicts.setdefault((v["artifact_a"], v["artifact_b"]), []).append(v)
    out = ["# Contradictions and collisions\n",
           f"What the inventoried artifacts give differently, found on {date} for the Artifact Textbook (issue #120) and carried here with the status of each candidate. "
           "Two readers went over the inventory's numbers table (3,025 numbers from 69 artifacts; the data half and the performance half) for every quantity two artifacts give with different values; "
           "one reader per topic cluster went over the full inventory records for disagreements, revised figures, stale statements and shared unsourced claims. "
           "A script then looked for each candidate's quotes and values in the artifact's extracted text and, failing that, in the page's own files (its scripts and data), and the columns 'Quote A' and 'Quote B' below say whether they were found. "
           "A candidate is a reader's finding, not a verdict: 'yes' means the words are in the source as quoted, 'not found' that the reader paraphrased or erred, and the kind is the reader's classification until phase 2 reads both texts for each one. "
           "The reader's own classification of each number collision is given with it; the fifteen pairs a verifying reader did read before the sweep stopped carry its verdict in the 'Read' column. "
           f"Of the {len(J['clusters'])} clusters, {len(C)} were swept for disagreements in this pass; the rest are listed at the end and are swept in phase 2.\n",
           "Nothing here is copied from memory: every value and quote is from the inventory's records, which were read from the artifact files. People are named by role; no address of any kind is reproduced.\n"]
    out.append("## Quantities two artifacts give differently\n")
    out.append(f"{len(N['candidates'])} candidates from the numbers table, by the reader's kind.\n")
    for kind, title in KINDS:
        rows = [(c, v) for c, v in zip(N["candidates"], V["numbers"]) if c["kind"] == kind]
        out.append(f"### {title} ({len(rows)})\n")
        out.append("| # | Quantity | A | A gives | B | B gives | Why | Quote A | Quote B | Read |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for k, (c, v) in enumerate(rows, 1):
            vs = verdicts.get((c["artifact_a"], c["artifact_b"])) or verdicts.get((c["artifact_b"], c["artifact_a"])) or []
            read = "; ".join(f"{x['verdict']}: {short(x['explanation'], 160)}" for x in vs if x["quantity"].lower()[:30] == c["quantity"].lower()[:30]) or "-"
            out.append(f"| {k} | {short(c['quantity'], 120)} | {link(c['artifact_a'], titles)} | {short(c['value_a'], 80)} | {link(c['artifact_b'], titles)} | {short(c['value_b'], 80)} | {short(c['why'], 240)} | {status(v['quote_a'])} | {status(v['quote_b'])} | {cell(read)} |")
        out.append("")
        out.append("The quotes, in the same order:\n")
        for k, (c, v) in enumerate(rows, 1):
            out.append(f"{k}. A, {short_id(c['artifact_a'])}: \"{short(c['quote_a'], 300)}\" B, {short_id(c['artifact_b'])}: \"{short(c['quote_b'], 300)}\"")
        out.append("")
    out.append("## Disagreements found cluster by cluster\n")
    for cl, vc in zip(C, V["clusters"]):
        f = cl["found"]
        out.append(f"### {cl['cluster']}\n")
        out.append(f"{len(f['candidates'])} candidates.\n")
        out.append("| # | Kind | Topic | A | A says | B | B says | Why it matters | Quote A | Quote B |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for k, (c, v) in enumerate(zip(f["candidates"], vc["rows"]), 1):
            b = link(c["artifact_b"], titles) if c.get("artifact_b") and "/" in c["artifact_b"] else cell(c.get("artifact_b") or "-")
            out.append(f"| {k} | {c['kind']} | {short(c['topic'], 120)} | {link(c['artifact_a'], titles)} | {short(c['statement_a'], 220)} | {b} | {short(c.get('statement_b'), 220)} | {short(c['why_it_matters'], 220)} | {status(v['quote_a'])} | {status(v['quote_b'])} |")
        out.append("")
        out.append("The quotes, in the same order:\n")
        for k, c in enumerate(f["candidates"], 1):
            qb = f" B: \"{short(c['quote_b'], 300)}\"" if c.get("quote_b") else ""
            out.append(f"{k}. A: \"{short(c['quote_a'], 300)}\"{qb}")
        out.append("")
        if f.get("canonical_check"):
            out.append("Canonical relations the reader checked:\n")
            for x in f["canonical_check"]:
                out.append(f"- {short_id(x['id'])} {x['relation']} {short_id(x['other'])}: {'agrees' if x['agree'] else 'disagrees'}. {cell(x['why'])}")
            out.append("")
        out.append(f"Unsourced: {cell(f['unsourced_summary'])}\n")
        out.append(f"Stale: {cell(f['stale_summary'])}\n")
        if f.get("notes"):
            out.append(f"Notes: {cell(f['notes'])}\n")
    done = {cl["cluster"] for cl in C}
    out.append("## Clusters not yet swept\n")
    for c in J["clusters"]:
        if c["name"] not in done:
            out.append(f"- {c['name']} ({len(c['members'])} members)")
    out.append("")
    open(dst, "w", newline="\n").write(to_ascii("\n".join(out)))


if __name__ == "__main__":
    main(*sys.argv[1:8])
