"""Check that every skeptic verdict in the merged record sits on the candidate it was given
for: the skeptic's quote from artifact a should be in a's text and its quote from b in b's.
A verdict merged at the wrong index would quote some other candidate's artifacts, so a quote
found only in the other artifact, or in neither, is listed for a person to read.

Usage: check_verdict_quotes.py MERGED OUT
  (SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
  render_contradictions2.py.)"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq

TEXT_DIR = os.environ.get("SYNTH_TEXT", "")
HIT = ("whole", "parts", "window", "raw-whole", "raw-parts", "raw-window")


def place(quote, own, other):
    """Where a skeptic's quote is: in its own artifact, only in the other one, or nowhere."""
    if not (quote or "").strip():
        return "empty"
    if own and vq.found(quote, vq.text_of(TEXT_DIR, own), vq.raw_of(own)) in HIT:
        return "own"
    if other and vq.found(quote, vq.text_of(TEXT_DIR, other), vq.raw_of(other)) in HIT:
        return "other"
    return "absent"


def artifact(aid):
    return aid if aid and "/" in aid else None


def rows_of(M):
    for c in M["clusters"]:
        for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
            if v:
                yield c["cluster"], i, artifact(x["artifact_a"]), artifact(x.get("artifact_b")), v
    for j, v in enumerate(M.get("numbers_extra", [])):
        yield "Number collisions", j, artifact(v["artifact_a"]), artifact(v["artifact_b"]), v


def main(merged, out):
    M = json.load(open(merged))
    tally, odd = Counter(), []
    for cluster, i, a, b, v in rows_of(M):
        pa, pb = place(v.get("quote_a"), a, b), place(v.get("quote_b"), b, a)
        tally[(pa, pb)] += 1
        if "other" in (pa, pb) or "absent" in (pa, pb):
            odd.append({"cluster": cluster, "index": i, "verdict": v["verdict"], "quote_a": pa, "quote_b": pb})
    json.dump({"tally": {f"{k[0]}/{k[1]}": n for k, n in sorted(tally.items())}, "listed": odd},
              open(out, "w"), indent=1)
    for k, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"{k[0]:>6} / {k[1]:<6} {n}")
    print("listed", len(odd), Counter(o["cluster"] for o in odd).most_common(5))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
