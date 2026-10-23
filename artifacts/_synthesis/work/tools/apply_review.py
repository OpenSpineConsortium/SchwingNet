"""Apply the adversarial review of the skeptics' verdicts to the merged record. Every verdict
the review read again gets its outcome under review: held, hint corrected or verdict
overturned. A judge's ruling replaces the skeptic's verdict, words, explanation and hint,
which are kept under first, so the page can show both. The sample and its outcomes go into
the record's review, from which the page counts how far the verdicts held.

Usage: apply_review.py REVIEW NUMBERS MERGED_IN MERGED_OUT
  REVIEW is out/review-137.json: the date, how the sample was drawn and, for each verdict
  read again, its cluster (or "Number collisions") and row, the side and reason it was drawn,
  the verdict the review read, the re-checker's reading and, where they disagreed, the ruling.
  A number's row is its collision's index in NUMBERS, out/numbers-partial.json."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from merge_skeptics import FIRST_FIELDS, require
from render_contradictions2 import number_key


def verdict_at(M, N, stratum, index):
    """The verdict the record holds for a row. A number verdict from before the second run
    lives in NUMBERS; it is copied into numbers_extra, whose verdicts the page prefers, so the
    review's outcome can be written beside it without changing the earlier file."""
    if stratum != "Number collisions":
        c = next(c for c in M["clusters"] if c["cluster"] == stratum)
        return c["verdicts"][index]
    key = number_key(N["candidates"][index])
    extra = M.setdefault("numbers_extra", [])
    for v in extra:
        if number_key(v) == key:
            return v
    earlier = next(v for v in N["verdicts"] if number_key(v) == key)
    extra.append(dict(earlier))
    return extra[-1]


def apply(review, N, M):
    summary = []
    for it in review["items"]:
        v = verdict_at(M, N, it["stratum"], it["index"])
        require(v is not None and v["verdict"] == it["first"],
                f"{it['stratum']} row {it['index']} does not hold the verdict the review read")
        ruling = it.get("ruling")
        if ruling:
            v["first"] = {f: v.get(f) for f in FIRST_FIELDS}
            v.update({f: ruling[f] for f in FIRST_FIELDS})
            outcome = "verdict overturned" if ruling["verdict"] != it["first"] else "hint corrected"
        else:
            require(it["recheck"]["holds"] and it["recheck"]["hint_ok"], f"{it['stratum']} row {it['index']} is disputed with no ruling")
            outcome = "held"
        v["review"] = outcome
        summary.append({"stratum": it["stratum"], "index": it["index"], "side": it["side"], "drawn": it["drawn"],
                        "first": it["first"], "final": v["verdict"], "outcome": outcome})
    M["review"] = {"date": review["date"], "about": review["about"], "items": summary}
    return M


def main(review, numbers, merged_in, merged_out):
    M = apply(json.load(open(review)), json.load(open(numbers)), json.load(open(merged_in)))
    json.dump(M, open(merged_out, "w"), indent=1)
    from collections import Counter
    print(Counter(x["outcome"] for x in M["review"]["items"]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
