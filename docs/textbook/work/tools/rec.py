"""Print inventory records as JSON.

    python3 -I -B rec.py SchwingNet/<folder> [symphony-template/<folder> ...]
    python3 -I -B rec.py --all --fields decisions,open_questions
    python3 -I -B rec.py SchwingNet/<folder> --fields numbers,key_claims
"""
import json
import sys
from pathlib import Path

INV = json.loads(Path("/home/claude/schwingnet-193/artifacts/_synthesis/inventory.json").read_text())
RECORDS = {f"{r['repo']}/{r['folder']}": r for r in INV["artifacts"]}


def main(argv):
    fields = None
    if "--fields" in argv:
        i = argv.index("--fields")
        fields = argv[i + 1].split(",")
        argv = argv[:i] + argv[i + 2:]
    ids = list(RECORDS) if argv[:1] == ["--all"] else argv
    out = []
    for aid in ids:
        r = RECORDS.get(aid)
        if r is None:
            out.append({"id": aid, "missing": True})
            continue
        r = {k: v for k, v in r.items() if k != "account"}
        if fields:
            r = {"id": aid, "title": r["title"], "date": r["date"], **{f: r.get(f) for f in fields}}
        out.append(r)
    print(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1:])
