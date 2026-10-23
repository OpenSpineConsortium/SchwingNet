"""Draw the sample of skeptic verdicts that #137's review read again, and write one input file
per re-checker with everything it needs to read both sources.

The draw is by stratum, one per cluster and one, Number collisions, for the numbers, and within
each by the SHA-1 of the UTF-8 string "stratum|row", rows counted from 0, lowest first: from
every stratum the two verdicts that put a candidate on the confirmed list and the one that
dismissed it (refuted, or a number's agreement), then the 5 dismissals and the 4 cannot-tell
verdicts with the lowest hashes left across all strata, 54 in all; and every verdict one of
whose own quotes check_verdict_quotes.py could not place. The review's rulings and the second
reading of ten later moved verdicts between sides, so the draw is repeated from the record as it
stood when it was made, at commit 1c656d4:

  git show 1c656d4:artifacts/_synthesis/work/out/contradictions-merged.json > merged.json
  git show 1c656d4:artifacts/_synthesis/work/out/numbers-partial.json > numbers.json
  git show 1c656d4:artifacts/_synthesis/work/out/verdict-quotes.json > quotes.json
  sample_review.py merged.json numbers.json ../inventory.json quotes.json OUT --against out/review-137.json

Usage: sample_review.py MERGED NUMBERS INVENTORY QUOTES OUT [--against REVIEW]
  SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
  render_contradictions2.py; the input files carry those paths for the re-checkers to read.
  With --against, the run stops unless it draws exactly the verdicts REVIEW records."""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq
from prep_verify import where
from render_contradictions2 import CONFIRMED_C, CONFIRMED_N, number_key, number_verdicts

NUMBERS = "Number collisions"
PER_STRATUM = {"confirmed": 2, "dismissed": 1, "cannot-tell": 0}
ACROSS_STRATA = {"confirmed": 0, "dismissed": 5, "cannot-tell": 4}
CHECKERS = {"confirmed": 3, "dismissed": 2}


def rank(stratum, row):
    return hashlib.sha1(f"{stratum}|{row}".encode("utf-8")).hexdigest()


def cluster_side(verdict):
    return "confirmed" if verdict in CONFIRMED_C else "dismissed" if verdict == "refuted" else "cannot-tell"


def number_side(verdict):
    return "confirmed" if verdict in CONFIRMED_N else "cannot-tell" if verdict == "cannot-tell" else "dismissed"


def verdicts(M, N, place):
    """Every verdict of the record, with what a re-checker needs to read both sources."""
    for c in M["clusters"]:
        for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
            if v:
                yield {"stratum": c["cluster"], "cluster": c["cluster"], "index": i, "kind": x["kind"], "topic": x.get("topic"),
                       "a": place(x["artifact_a"]), "statement_a": x.get("statement_a"), "quote_a": x.get("quote_a"),
                       "b": place(x.get("artifact_b")), "statement_b": x.get("statement_b"), "quote_b": x.get("quote_b"),
                       "reader_why": x.get("why_it_matters"), "skeptic": v, "side": cluster_side(v["verdict"])}
    nv = number_verdicts(N, M.get("numbers_extra", []))
    for j, x in enumerate(N["candidates"]):
        v = nv.get(number_key(x))
        if v:
            yield {"stratum": NUMBERS, "cluster": NUMBERS, "index": j, "kind": x["kind"], "quantity": x["quantity"],
                   "a": place(x["artifact_a"]), "value_a": x["value_a"], "quote_a": x["quote_a"],
                   "b": place(x["artifact_b"]), "value_b": x["value_b"], "quote_b": x["quote_b"],
                   "reader_why": x.get("why"), "skeptic": v, "side": number_side(v["verdict"])}


def draw(items, side):
    """One side's share: the lowest hashes of every stratum, then the lowest left across all."""
    pool = sorted((x for x in items if x["side"] == side), key=lambda x: rank(x["stratum"], x["index"]))
    chosen = []
    for stratum in sorted({x["stratum"] for x in items}):
        chosen += [x for x in pool if x["stratum"] == stratum][:PER_STRATUM[side]]
    return chosen + [x for x in pool if x not in chosen][:ACROSS_STRATA[side]]


def add_unplaced(items, groups, quotes):
    """The verdicts whose own quotes the script could not place are read again whatever the
    draw, each with the re-checkers of its side."""
    for o in quotes["listed"]:
        x = next(x for x in items if x["stratum"] == o["cluster"] and x["index"] == o["index"])
        group = groups["confirmed"] if x["side"] == "confirmed" else groups["dismissed"]
        if x not in group:
            x["why_drawn"] = "the script could not place one of the skeptic's own quotes"
            group.append(x)


def same_as(groups, review):
    """Stop unless the draw is the one REVIEW records, verdict for verdict."""
    mine = {(x["stratum"], x["index"], "unplaced quote" if x.get("why_drawn") else "random")
            for group in groups.values() for x in group}
    theirs = {(x["stratum"], x["index"], x["drawn"]) for x in review["items"]}
    if mine != theirs:
        raise SystemExit(f"the draw differs from the review's: only here {sorted(mine - theirs)}, only there {sorted(theirs - mine)}")
    print(f"the draw is the review's: {len(mine)} verdicts")


def write_inputs(groups, out):
    os.makedirs(out, exist_ok=True)
    files = []
    for side, group in groups.items():
        for k in range(CHECKERS[side]):
            path = f"{out}/{side}-{k}.json"
            part = group[k::CHECKERS[side]]
            json.dump({"side": side, "items": part}, open(path, "w"), indent=1)
            files.append({"file": path, "side": side, "count": len(part)})
    json.dump(files, open(f"{out}/files.json", "w"), indent=1)
    return files


def main(merged, numbers, inventory, quotes, out, against=None):
    text_dir, roots = vq.required_dir("SYNTH_TEXT"), vq.repos()
    meta = {f"{r['repo']}/{r['folder']}": (r.get("date"), r.get("title")) for r in json.load(open(inventory))["artifacts"]}
    items = list(verdicts(json.load(open(merged)), json.load(open(numbers)), lambda aid: where(text_dir, roots, meta, aid)))
    groups = {"confirmed": draw(items, "confirmed"), "dismissed": draw(items, "dismissed") + draw(items, "cannot-tell")}
    add_unplaced(items, groups, json.load(open(quotes)))
    if against:
        same_as(groups, json.load(open(against)))
    for f in write_inputs(groups, out):
        print(f)


if __name__ == "__main__":
    args = sys.argv[1:]
    review = None
    if "--against" in args:
        k = args.index("--against")
        review, args = args[k + 1], args[:k] + args[k + 2:]
    main(*args, against=review)
