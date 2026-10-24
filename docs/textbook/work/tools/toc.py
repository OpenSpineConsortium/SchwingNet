"""Print one chapter's plan from the table of contents' JSON, with each
artifact's title, folder, extracted text, claude.ai link and cluster status.

    python3 -I -B toc.py NN            the chapter's plan
    python3 -I -B toc.py --preface     the preface, the owner's answers and the notes
    python3 -I -B toc.py --list        every chapter's number, title, label and file
"""
import json
import sys
from pathlib import Path

WT = Path("/home/claude/schwingnet-193")
SCRATCH = Path(__file__).resolve().parent.parent
SYN = WT / "artifacts" / "_synthesis"
PLAN = json.loads((SYN / "work" / "out" / "toc-hand.json").read_text())
INV = json.loads((SYN / "inventory.json").read_text())
CL = json.loads((SYN / "work" / "out" / "clustering.json").read_text())["judged"]
RECORDS = {f"{r['repo']}/{r['folder']}": r for r in INV["artifacts"]}


def status_of(aid):
    out = []
    for c in CL["clusters"]:
        if aid in c["members"] or aid in c.get("secondary_members", []):
            role = "canonical" if aid in c["canonical"] else "member"
            for s in c["superseded"]:
                if s["id"] == aid:
                    role = f"superseded by {s['by']}: {s['why']}"
            for d in c.get("duplicates", []):
                if isinstance(d, dict) and d.get("id") == aid:
                    role = f"duplicate of {d.get('of') or d.get('by')}: {d.get('why', '')}"
            if aid in c.get("secondary_members", []) and aid not in c["members"]:
                role = "secondary member"
            out.append(f"cluster '{c['name']}': {role}")
    return out or ["no cluster"]


def artifact_lines(aid):
    r = RECORDS.get(aid)
    repo, folder = aid.split("/", 1)
    lines = [f"- {aid}"]
    if not r:
        lines.append("    (no inventory record)")
        return lines
    copy = WT / "artifacts" / folder if repo == "SchwingNet" else SCRATCH / "st" / "artifacts" / folder
    lines += [f"    title: {r['title']}",
              f"    date: {r['date']}; kind: {r['kind']}; genre: {r['genre']}; confidentiality: {r['confidentiality']}",
              f"    claude.ai: {r['link']}",
              f"    copy: {copy}",
              f"    text: {SCRATCH / 'text' / repo / (folder + '.txt')}",
              f"    link from docs/textbook/: " + (f"../../artifacts/{folder}/" if repo == "SchwingNet" else r["link"])]
    lines += [f"    {s}" for s in status_of(aid)]
    return lines


def chapter(number):
    for part in PLAN["parts"]:
        for c in part["chapters"]:
            if c["number"] == number:
                return part, c
    raise SystemExit(f"no chapter {number}")


def main(argv):
    if argv[:1] == ["--list"]:
        for part in PLAN["parts"]:
            for c in part["chapters"]:
                print(f"{c['number']} | {part['label']} | {c['title']} | {c['confidentiality']} | {c['file']}")
        return
    if argv[:1] == ["--preface"]:
        print("PREFACE:\n" + PLAN["preface"] + "\n")
        for i, (q, a) in enumerate(zip(PLAN["owner_questions"], PLAN["owner_answers"]), 1):
            print(f"OWNER QUESTION {i}: {q}\nANSWER: {a}\n")
        print("NOTES:\n" + PLAN["notes"])
        return
    part, c = chapter(argv[0])
    print(f"{part['label']}: {part['title']}" + (f"\n{part['purpose']}" if part.get("purpose") else ""))
    print(f"\nCHAPTER {c['number']} {c['title']}\nFile: {c['file']}\nLabel: {c['confidentiality']}\n")
    print("PURPOSE:\n" + c["purpose"] + "\n")
    print("QUESTIONS IT ANSWERS:")
    print("\n".join(f"- {q}" for q in c["questions_answered"]))
    print("\nARTIFACTS READ FIRST:")
    for a in c["artifacts_primary"]:
        print("\n".join(artifact_lines(a)))
    print("\nARTIFACTS READ SECOND:")
    for a in c.get("artifacts_secondary", []):
        print("\n".join(artifact_lines(a)))
    print("\nREPOSITORY FILES BESIDE THEM (paths from the repository root, " + str(WT) + "):")
    print("\n".join(f"- {p}" for p in c.get("repository_sources", [])))
    print("\nRESEARCH PHASE 2 OWES IT:\n" + c["research_needed"])
    others = {k: v for k, v in c.items() if k not in {"number", "file", "title", "purpose", "questions_answered",
              "artifacts_primary", "artifacts_secondary", "repository_sources", "research_needed", "confidentiality"}}
    if others:
        print("\nOTHER PLAN FIELDS:\n" + json.dumps(others, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
