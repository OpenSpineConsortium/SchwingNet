"""Add the second skeptic run's verdicts to the merged record: each cluster verdict at its
candidate's index, each number verdict into numbers_extra, keyed as the renderer keys them.

Usage:
  merge_skeptics.py extract JOURNAL RESULTS_OUT
      keeps a workflow's results, read from its journal.jsonl, beside the record;
  merge_skeptics.py merge IN_NUMBERS MERGED_IN MERGED_OUT RESULTS...
      merges the kept results into the record. IN_NUMBERS is the list of number candidates
      the verifier read, in the order its indices count."""
import json
import sys


def results_of(journal):
    labels, out = {}, []
    for line in open(journal):
        e = json.loads(line)
        if e.get("type") == "started":
            labels[e["key"]] = e["label"]
        elif e.get("type") == "result" and e.get("result"):
            out.append({"label": labels[e["key"]], "result": e["result"]})
    return out


def cluster_verdict(x, v):
    return {"kind": x["kind"], "topic": x.get("topic"), "artifact_a": x["artifact_a"],
            "artifact_b": x.get("artifact_b"), "verdict": v["verdict"], "quote_a": v.get("quote_a"),
            "quote_b": v.get("quote_b"), "explanation": v.get("explanation"),
            "resolution_hint": v.get("resolution_hint")}


def number_verdict(row, v):
    return {"quantity": row["quantity"], "artifact_a": row["a"]["id"], "artifact_b": row["b"]["id"],
            "verdict": v["verdict"], "value_a": row["value_a"], "value_b": row["value_b"],
            "quote_a": v.get("quote_a"), "quote_b": v.get("quote_b"),
            "explanation": v.get("explanation"), "resolution_hint": v.get("resolution_hint")}


def parts_of(result):
    """A verifier's clusters, whether the result is one agent's or a verify-and-fill pair."""
    if "clusters" in result:
        return result["clusters"]
    out = []
    for r in result.get("results", []):
        for step in (r.get("first"), r.get("fill")):
            out.extend((step or {}).get("clusters", []))
    return out


def merge(results, rows, M):
    by = {c["cluster"]: c for c in M["clusters"]}
    extra = M.setdefault("numbers_extra", [])
    for r in results:
        for part in parts_of(r["result"]):
            if part["cluster"] == "Number collisions":
                extra.extend(number_verdict(rows[v["index"]], v) for v in part["verdicts"])
                continue
            c = by[part["cluster"]]
            for v in part["verdicts"]:
                i = v["index"]
                assert c["verdicts"][i] is None, (part["cluster"], i)
                c["verdicts"][i] = cluster_verdict(c["candidates"][i], v)
    return M


def main(argv):
    if argv[0] == "extract":
        json.dump({"results": results_of(argv[1])}, open(argv[2], "w"), indent=1)
        return
    in_numbers, merged_in, merged_out, kept = argv[1], argv[2], argv[3], argv[4:]
    results = [r for path in kept for r in json.load(open(path))["results"]]
    rows = json.load(open(in_numbers))["candidates"]
    M = merge(results, rows, json.load(open(merged_in)))
    json.dump(M, open(merged_out, "w"), indent=1)
    for c in M["clusters"]:
        print(c["cluster"][:45], len(c.get("candidates", [])), sum(1 for v in c.get("verdicts", []) if v))
    print("numbers_extra", len(M["numbers_extra"]))


if __name__ == "__main__":
    main(sys.argv[1:])
