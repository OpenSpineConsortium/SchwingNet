"""Render artifacts/_synthesis/clusters.md from clustering.json: the settled clustering, with
each cluster's canonical, superseded and duplicate artifacts, then the three lens clusterings
it was settled from, so a reader sees the choice and what each lens contributed."""
import json
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from render_inventory import to_ascii, cell


def short_id(i):
    return i.split("/", 1)[1] if "/" in i else i


def link(i, titles, up="../"):
    """A link to an artifact's folder: up climbs from the page to artifacts/, one level from
    artifacts/_synthesis/ and two from a page in a folder below it."""
    repo, folder = i.split("/", 1)
    t = titles.get(i, folder)
    if repo == "SchwingNet":
        return f"[{cell(t)}]({up}{folder}/)"
    return f"[{cell(t)}](https://github.com/OpenSpineConsortium/symphony-template/tree/main/artifacts/{folder}/)"


def main(clustering, inventory, dst):
    C = json.load(open(clustering))
    inv = json.load(open(inventory))
    titles = {f"{r['repo']}/{r['folder']}": r["title"] for r in inv["artifacts"]}
    dates = {f"{r['repo']}/{r['folder']}": r["date"] for r in inv["artifacts"]}
    J = C["judged"]
    out = ["# Artifact clusters\n",
           "The 69 inventoried artifacts sorted into topics by three independent readings (by the question answered, by the stage of the work, by the reader and the decision) and settled by a fourth reader into one clustering, on 2026-10-22, for the Artifact Textbook (issue #120). Each artifact has one primary home and may be a secondary member elsewhere. Within a cluster the canonical artifacts are the ones to read first; a superseded artifact is replaced by a later or fuller one on the same question, with what the older one alone still holds noted where the readers found it; a duplicate is a near-copy. The part says where the cluster goes in the book: schwingnet for the spine work, symphony-beethoven for the material to be kept in a separable part, outreach-and-governance for pages with no method or data.\n",
           f"{len(J['clusters'])} clusters; every artifact placed; unplaced: {', '.join(J['unplaced']) or 'none'}.\n",
           "## Summary\n",
           "| # | Cluster | Part | Primary members | Canonical | Superseded | Duplicates |",
           "|---|---|---|---|---|---|---|"]
    for i, c in enumerate(J["clusters"], 1):
        out.append(f"| {i} | {cell(c['name'])} | {c['part']} | {len(c['members'])} | {len(c['canonical'])} | {len(c['superseded'])} | {len(c['duplicates'])} |")
    out.append("\n## Clusters\n")
    for i, c in enumerate(J["clusters"], 1):
        out.append(f"### {i}. {cell(c['name'])} ({c['part']})\n")
        out.append(cell(c["description"]) + "\n")
        out.append("Primary members, by date:\n")
        for m in sorted(c["members"], key=lambda m: dates.get(m, "")):
            tag = " (canonical)" if m in c["canonical"] else ""
            out.append(f"- {link(m, titles)}, {cell(dates.get(m, 'undated'))}, `{m}`{tag}")
        if c["superseded"]:
            out.append("\nSuperseded:\n")
            for s in c["superseded"]:
                out.append(f"- `{short_id(s['id'])}` is superseded by `{short_id(s['by'])}`: {cell(s['why'])}")
        if c["duplicates"]:
            out.append("\nDuplicates:\n")
            for s in c["duplicates"]:
                out.append(f"- `{short_id(s['id'])}` duplicates `{short_id(s['of'])}`: {cell(s['why'])}")
        if c["secondary_members"]:
            out.append("\nSecondary members: " + ", ".join(f"`{short_id(m)}`" for m in c["secondary_members"]))
        out.append("")
    out.append("## How the clustering was settled\n")
    out.append(cell(J["rationale"]) + "\n")
    out.append("| Lens | Clusters | Strengths | Weaknesses |")
    out.append("|---|---|---|---|")
    for l in J["lens_summaries"]:
        out.append(f"| {cell(l['lens'])} | {l['cluster_count']} | {cell(l['strengths'])} | {cell(l['weaknesses'])} |")
    out.append("\n## The three lens clusterings\n")
    for cl in C["clusterings"]:
        out.append(f"### Lens: {cell(cl['lens'])}\n")
        for c in cl["clusters"]:
            out.append(f"- **{cell(c['name'])}** ({c['part']}): " + ", ".join(f"`{short_id(m)}`" for m in c["members"]))
        if cl.get("notes"):
            out.append(f"\nNotes: {cell(cl['notes'])}")
        out.append("")
    text = to_ascii("\n".join(out) + "\n")
    open(dst, "w", encoding="ascii", newline="\n").write(text)
    print(dst, len(text), "bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
