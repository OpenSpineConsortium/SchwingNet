"""Write one input file per skeptic: the cluster candidates no skeptic has read, each with its
index, both artifacts' dates and titles, where their texts and folders are, and whether the
quote script found each quote; and the number collisions of the batches, in the order the
skeptic's indices count. This made the ten inputs of #136's skeptic run, the numbers' kept as
out/in-numbers.json.

Usage: prep_verify.py MERGED BATCHES INVENTORY OUT_DIR
  MERGED is the record before the run (out/contradictions-merged.json as 40beb51 holds it),
  BATCHES out/numbers-verify-batches.json and INVENTORY artifacts/_synthesis/inventory.json.
  SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
  render_contradictions2.py; the input files carry those paths for the skeptics to read."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq

UNITS = [["Symphony: the protocol, its evidence and its place", "Symphony's origins: cswap, the primitives and the two Claude surfaces"],
         ["Verification benches, overnight audits and OR readiness"],
         ["The case for the OR study: proposal, seed grant and IRB protocols", "Outreach events and student funding"],
         ["Level naming and counting"],
         ["Grid, workstation and Claude worker operations", "Beethoven: the research engine and its repositories"],
         ["Detectors, architecture and the training plan"],
         ["Programme direction, handoffs and onboarding"],
         ["Datasets, holdings and licences"],
         ["Renders, physics and the sim-to-real gap"]]


def where(text_dir, roots, meta, aid):
    if not aid or "/" not in aid:
        return None
    repo, folder = aid.split("/", 1)
    d, t = meta.get(aid, (None, None))
    return {"id": aid, "title": t, "date": d, "text": f"{text_dir}/{repo}/{folder}.txt", "folder": f"{roots[repo]}/{folder}"}


def status(text_dir, aid, quote):
    if not aid or "/" not in aid:
        return "-"
    return vq.found(quote or "", vq.text_of(text_dir, aid), vq.raw_of(aid))


def cluster_rows(c, at, text_dir):
    rows = []
    for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
        if v:
            continue
        rows.append({"index": i, "kind": x["kind"], "topic": x.get("topic"),
                     "a": at(x["artifact_a"]), "statement_a": x.get("statement_a"), "quote_a": x.get("quote_a"),
                     "quote_a_found": status(text_dir, x["artifact_a"], x.get("quote_a")),
                     "b": at(x.get("artifact_b")), "statement_b": x.get("statement_b"), "quote_b": x.get("quote_b"),
                     "quote_b_found": status(text_dir, x.get("artifact_b"), x.get("quote_b")),
                     "why_it_matters": x.get("why_it_matters")})
    return rows


def number_rows(batches, at, text_dir):
    rows = []
    for b in batches:
        for g in b:
            for x in g["candidates"]:
                rows.append({"index": len(rows), "kind": x["kind"], "quantity": x["quantity"],
                             "a": at(x["artifact_a"]), "value_a": x["value_a"], "quote_a": x["quote_a"],
                             "quote_a_found": status(text_dir, x["artifact_a"], x["quote_a"]),
                             "b": at(x["artifact_b"]), "value_b": x["value_b"], "quote_b": x["quote_b"],
                             "quote_b_found": status(text_dir, x["artifact_b"], x["quote_b"]), "why": x.get("why")})
    return rows


def main(merged, batches, inventory, out_dir):
    text_dir, roots = vq.required_dir("SYNTH_TEXT"), vq.repos()
    inv = json.load(open(inventory))
    meta = {f"{r['repo']}/{r['folder']}": (r.get("date"), r.get("title")) for r in inv["artifacts"]}
    at = lambda aid: where(text_dir, roots, meta, aid)
    by = {c["cluster"]: c for c in json.load(open(merged))["clusters"]}
    os.makedirs(out_dir, exist_ok=True)
    units = []
    for n, names in enumerate(UNITS):
        out = {"clusters": [{"cluster": name, "candidates": cluster_rows(by[name], at, text_dir)} for name in names]}
        p = f"{out_dir}/in-{n}.json"
        json.dump(out, open(p, "w"), indent=1)
        units.append({"kind": "clusters", "file": p, "clusters": names, "count": sum(len(c["candidates"]) for c in out["clusters"])})
    p = f"{out_dir}/in-numbers.json"
    rows = number_rows(json.load(open(batches)), at, text_dir)
    json.dump({"candidates": rows}, open(p, "w"), indent=1)
    units.insert(3, {"kind": "numbers", "file": p, "clusters": ["Number collisions"], "count": len(rows)})
    json.dump(units, open(f"{out_dir}/units.json", "w"), indent=1)
    for u in units:
        print(u["count"], u["clusters"], os.path.getsize(u["file"]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
