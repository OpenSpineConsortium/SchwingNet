"""Add the skeptic runs' verdicts to the merged record: each cluster verdict at its candidate's
index, each number verdict into numbers_extra, keyed as the renderer keys them. Every merge
checks what it is given first, since a wrong index or an unknown word would put a verdict on
another candidate or drop it from every column without a word.

Usage:
  merge_skeptics.py extract JOURNAL RESULTS_OUT
      keeps a workflow's results, read from its journal.jsonl, beside the record;
  merge_skeptics.py merge IN_NUMBERS NUMBERS MERGED_IN MERGED_OUT RESULTS...
      merges the kept results into the record. IN_NUMBERS is the list of number candidates
      the verifier read, in the order its indices count (out/in-numbers.json), and NUMBERS
      the collisions they are keyed to (out/numbers-partial.json);
  merge_skeptics.py reread IN_REREAD NUMBERS MERGED_IN MERGED_OUT RESULT
      puts a second reading of earlier number verdicts in their place, the earlier verdict
      kept under first. IN_REREAD lists the collisions read again, each with its index in
      NUMBERS, and RESULT holds {"verdicts": [...]} keyed by those indices."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from render_contradictions2 import number_key

CLUSTER_VERDICTS = ("confirmed", "superseded-by-later", "refuted", "cannot-tell")
NUMBER_VERDICTS = ("confirmed-contradiction", "updated-later", "same-number-restated", "scope-or-unit-differs",
                   "different-quantities", "cannot-tell")
FIRST_FIELDS = ("verdict", "quote_a", "quote_b", "explanation", "resolution_hint")


def require(ok, why):
    if not ok:
        raise SystemExit("merge refused: " + why)


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


def row_key(row):
    return number_key({"artifact_a": row["a"]["id"], "artifact_b": row["b"]["id"], "quantity": row["quantity"]})


def parts_of(result):
    """A verifier's clusters, whether the result is one agent's or a verify-and-fill pair."""
    if "clusters" in result:
        return result["clusters"]
    out = []
    for r in result.get("results", []):
        for step in (r.get("first"), r.get("fill")):
            out.extend((step or {}).get("clusters", []))
    return out


def check_numbers(verdicts, rows, N):
    """Each input row read once, each by a word of the scale, and each a collision of NUMBERS."""
    require(sorted(v["index"] for v in verdicts) == list(range(len(rows))),
            f"the number verdicts' indices are not each of 0 to {len(rows) - 1} once")
    for v in verdicts:
        require(v["verdict"] in NUMBER_VERDICTS, f"unknown number verdict {v['verdict']!r}")
    keys = {number_key(c) for c in N["candidates"]}
    for row in rows:
        require(row_key(row) in keys, f"an input row matches no collision: {row['quantity']!r}")


def merge(results, rows, N, M):
    by = {c["cluster"]: c for c in M["clusters"]}
    extra = M.setdefault("numbers_extra", [])
    numbers = []
    for r in results:
        for part in parts_of(r["result"]):
            if part["cluster"] == "Number collisions":
                numbers.extend(part["verdicts"])
                continue
            c = by[part["cluster"]]
            for v in part["verdicts"]:
                i = v["index"]
                require(0 <= i < len(c["candidates"]), f"{part['cluster']} has no candidate {i}")
                require(v["verdict"] in CLUSTER_VERDICTS, f"unknown cluster verdict {v['verdict']!r}")
                require(c["verdicts"][i] is None, f"{part['cluster']} candidate {i} is filled twice")
                c["verdicts"][i] = cluster_verdict(c["candidates"][i], v)
    if numbers:
        check_numbers(numbers, rows, N)
        extra.extend(number_verdict(rows[v["index"]], v) for v in numbers)
    return M


def reread(rows, N, M, verdicts):
    """Each new reading replaces the earlier verdict on its collision, which it keeps under
    first, and is marked read again, so the page shows both."""
    by_index = {r["index"]: r for r in rows}
    require(sorted(v["index"] for v in verdicts) == sorted(by_index), "the re-read verdicts do not cover each row once")
    earlier = {number_key(v): v for v in N["verdicts"]}
    extra = M.setdefault("numbers_extra", [])
    taken = {number_key(v) for v in extra}
    for v in verdicts:
        require(v["verdict"] in NUMBER_VERDICTS, f"unknown number verdict {v['verdict']!r}")
        row = by_index[v["index"]]
        require(number_key(N["candidates"][v["index"]]) == row_key(row), f"row {v['index']} is not the collision it names")
        new = number_verdict(row, v)
        k = number_key(new)
        require(k in earlier and k not in taken, f"collision {v['index']} has no earlier verdict, or one already replaced")
        new["first"] = {f: earlier[k].get(f) for f in FIRST_FIELDS}
        new["review"] = "read again"
        extra.append(new)
        taken.add(k)
    return M


def main(argv):
    if argv[0] == "extract":
        json.dump({"results": results_of(argv[1])}, open(argv[2], "w"), indent=1)
        return
    rows = json.load(open(argv[1]))["candidates"]
    N, M = json.load(open(argv[2])), json.load(open(argv[3]))
    if argv[0] == "merge":
        results = [r for path in argv[5:] for r in json.load(open(path))["results"]]
        M = merge(results, rows, N, M)
    elif argv[0] == "reread":
        M = reread(rows, N, M, json.load(open(argv[5]))["verdicts"])
    else:
        raise SystemExit(f"unknown mode {argv[0]!r}")
    json.dump(M, open(argv[4], "w"), indent=1)
    for c in M["clusters"]:
        print(c["cluster"][:45], len(c.get("candidates", [])), sum(1 for v in c.get("verdicts", []) if v))
    print("numbers_extra", len(M["numbers_extra"]))


if __name__ == "__main__":
    main(sys.argv[1:])
