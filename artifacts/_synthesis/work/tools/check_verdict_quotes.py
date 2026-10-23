"""Check that every skeptic verdict in the merged record sits on the candidate it was given
for: the skeptic's quote from artifact a should be in a's text and its quote from b in b's.
A verdict merged at the wrong index would quote some other candidate's artifacts, so a quote
found only in the other artifact, or in neither, is listed for a person to read. A candidate
whose two sides are one artifact says nothing about alignment, so it is counted apart.

Usage: check_verdict_quotes.py MERGED NUMBERS OUT
  NUMBERS is numbers-partial.json, whose candidates the number verdicts are keyed to; a
  number verdict is listed by its collision's index there, as the page and the review count.
  (SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
  render_contradictions2.py.)"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq
from render_contradictions2 import number_key, number_verdicts


def artifact(aid):
    return aid if aid and "/" in aid else None


def rows_of(M, N):
    for c in M["clusters"]:
        for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
            if v:
                yield c["cluster"], i, artifact(x["artifact_a"]), artifact(x.get("artifact_b")), v
    nv = number_verdicts(N, M.get("numbers_extra", []))
    for j, x in enumerate(N["candidates"]):
        v = nv.get(number_key(x))
        if v:
            yield "Number collisions", j, artifact(x["artifact_a"]), artifact(x["artifact_b"]), v


def main(merged, numbers, out):
    text_dir = vq.required_dir("SYNTH_TEXT")
    M, N = json.load(open(merged)), json.load(open(numbers))
    tally, odd = Counter(), []
    for cluster, i, a, b, v in rows_of(M, N):
        pa, pb = vq.place(text_dir, v.get("quote_a"), a, b), vq.place(text_dir, v.get("quote_b"), b, a)
        tally[(pa.partition(":")[0], pb.partition(":")[0], "one artifact" if a == b else "two artifacts")] += 1
        if {pa, pb} - {"own", "empty"}:
            odd.append({"cluster": cluster, "index": i, "verdict": v["verdict"], "quote_a": pa, "quote_b": pb})
    json.dump({"tally": {f"{k[0]}/{k[1]} ({k[2]})": n for k, n in sorted(tally.items())}, "listed": odd},
              open(out, "w"), indent=1)
    for k, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"{k[0]:>6} / {k[1]:<6} {k[2]:<14} {n}")
    print("verdicts", sum(tally.values()), "listed", len(odd), Counter(o["cluster"] for o in odd).most_common(5))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
