"""Add the Outreach sweep and the two verifier results the journal holds to the merged record."""
import json, sys
W = sys.argv[1]
M = json.load(open(f"{W}/out/contradictions-all.json"))
J = json.load(open(f"{W}/out/journal-results.json"))
res = [r for w in J.values() for r in w["results"]]
by = {c["cluster"]: c for c in M["clusters"]}
for r in res:
    lab, x = r["label"], r["result"]
    if lab.startswith("find:") and x["cluster"].startswith("Outreach"):
        name = "Outreach events and student funding"
        c = by[name]
        c.update({"swept": True, "candidates": x["candidates"], "verdicts": [None] * len(x["candidates"]),
                  "canonical_check": x.get("canonical_check", []), "unsourced_summary": x.get("unsourced_summary", ""),
                  "stale_summary": x.get("stale_summary", ""), "notes": x.get("notes", "")})
    if lab.startswith("verify"):
        c = by[x["cluster"]]
        v = x["verdicts"]
        assert len(v) == len(c["candidates"]), (x["cluster"], len(v), len(c["candidates"]))
        for a, b in zip(v, c["candidates"]):
            assert a["artifact_a"] == b["artifact_a"], x["cluster"]
        c["verdicts"] = v
json.dump(M, open(sys.argv[2], "w"), indent=1)
for c in M["clusters"]:
    print(c["cluster"][:45], len(c.get("candidates", [])), sum(1 for v in c.get("verdicts", []) if v))
