"""Render artifacts/_synthesis/table-of-contents.md from the chapter plan, so the proposed
book can be read and argued over on the pull request before a chapter is written."""
import json
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from render_inventory import to_ascii, cell
from render_clusters import link


def main(plan, inventory, dst, date):
    P = json.load(open(plan)); inv = json.load(open(inventory))
    titles = {f"{r['repo']}/{r['folder']}": r["title"] for r in inv["artifacts"]}
    out = ["# The Artifact Textbook: proposed table of contents\n",
           f"Proposed on {date} for issue #120 from the inventory, the clusters and the contradictions beside this file; nothing of it is written yet. "
           "Each chapter below gives its file under docs/textbook/, what it is for, the questions it answers, the artifacts it reads first and second, the repository files it reads beside them, its confidentiality label and the research phase 2 owes it. "
           "Every chapter ends, when written, with 'What we know', 'What we do not know', 'What would change our mind' and a provenance table from each statement to its artifact and evidence grade (Measured, Reported, Inferred, Unverified). "
           "The labels: confidential-method marks a chapter that says what a stage does, which stays in this private repository and is copied nowhere; results-only marks one that cites results and rules and no method; symphony-beethoven-separable marks Part S, which can be split out; outreach marks a chapter that names people by role only.\n",
           cell(P["preface"]) + "\n"]
    n_ch = sum(len(p["chapters"]) for p in P["parts"])
    out.append(f"{len(P['parts'])} parts, {n_ch} chapters.\n")
    out.append("## Overview\n")
    for p in P["parts"]:
        out.append(f"- {p['label']}: {p['title']}" + (" (separable)" if p.get("separable") else ""))
        for c in p["chapters"]:
            out.append(f"  - {c['number']} {c['title']} ({c['confidentiality']})")
    out.append("")
    for p in P["parts"]:
        out.append(f"## {p['label']}: {p['title']}\n")
        if p.get("purpose"):
            out.append(cell(p["purpose"]) + "\n")
        for c in p["chapters"]:
            out.append(f"### {c['number']} {c['title']}\n")
            out.append(f"File: {c['file']}. Label: {c['confidentiality']}.\n")
            out.append(cell(c["purpose"]) + "\n")
            out.append("Questions it answers:\n")
            out.extend(f"- {cell(q)}" for q in c["questions_answered"])
            out.append("")
            out.append("Artifacts read first: " + "; ".join(link(a, titles) for a in c["artifacts_primary"]) + ".\n")
            if c.get("artifacts_secondary"):
                out.append("Artifacts read second: " + "; ".join(link(a, titles) for a in c["artifacts_secondary"]) + ".\n")
            if c.get("repository_sources"):
                out.append("Repository files beside them: " + ", ".join(c["repository_sources"]) + ".\n")
            out.append("Research phase 2 owes it: " + cell(c["research_needed"]) + "\n")
    out.append("## Coverage: every artifact and the chapters that use it\n")
    out.append("| Artifact | Repository | Chapters |")
    out.append("|---|---|---|")
    for row in P["coverage"]:
        out.append(f"| {link(row['id'], titles)} | {row['id'].split('/')[0]} | {', '.join(row['chapters'])} |")
    out.append("")
    out.append(f"Artifacts no chapter uses: {', '.join(P['uncovered']) or 'none'}.\n")
    out.append("## Questions for the owner\n")
    out.extend(f"{i}. {cell(q)}" for i, q in enumerate(P["owner_questions"], 1))
    out.append("")
    out.append("## Notes on the plan\n")
    out.append(cell(P["notes"]) + "\n")
    open(dst, "w", newline="\n").write(to_ascii("\n".join(out)))


if __name__ == "__main__":
    main(*sys.argv[1:5])
