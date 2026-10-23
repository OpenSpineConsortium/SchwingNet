"""Apply the adversarial review of the skeptics' verdicts to the merged record, or a later
reading of verdicts the review left out. Every verdict the review read again gets its outcome
under review: held, hint corrected or verdict overturned. A judge's ruling that sides with the
re-checker, or with neither reader, replaces the skeptic's verdict, words, explanation and
hint, which are kept under first, so the page can show both; one that sides with the skeptic
leaves the verdict as it was, held. The sample and its outcomes go into the record's review,
from which the page counts how far the verdicts held.

Usage: apply_review.py REVIEW NUMBERS MERGED_IN MERGED_OUT
       apply_review.py --followup READING NUMBERS MERGED_IN MERGED_OUT
  REVIEW is out/review-137.json: the date, how the sample was drawn and, for each verdict
  read again, its cluster (or "Number collisions") and row, the side and reason it was drawn,
  the verdict the review read, the re-checker's reading and, where they disagreed, the ruling.
  A number's row is its collision's index in NUMBERS, out/numbers-partial.json.
  READING is a later reading in the same form, out/reread-confirmed-numbers.json (#155, every
  confirmed number collision the review left out). Each verdict it read gets its outcome under
  followup, with the fields a ruling replaced kept there under before, so a verdict that was
  already overturned or read again keeps its first as well; the reading goes into the record's
  followup and the review's own items stay as they were. Where the reading holds a group
  re-rule, a row's group judge, when it does not keep the verdict, has the last word, and the
  outcome is set against the verdict the follow-up read."""
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


def read_verdict(M, N, it):
    """The verdict an item was read for, refused unless it is still the one the reader read."""
    v = verdict_at(M, N, it["stratum"], it["index"])
    require(v is not None and v["verdict"] == it["first"],
            f"{it['stratum']} row {it['index']} does not hold the verdict the review read")
    return v


def ruled(v, it):
    """One verdict's outcome. A ruling that does not side with the skeptic is put in its place,
    and then a group re-rule that does not keep it, so the verdict reads as the last reader to
    change it has it. The outcome is set against the verdict the reading read: another verdict
    is overturned, the same verdict in other words a corrected hint. Returns the outcome and the
    fields replaced, or None when nothing was replaced."""
    ruling, regroup = it.get("ruling"), it.get("regroup")
    if not ruling:
        require(it["recheck"]["holds"] and it["recheck"]["hint_ok"], f"{it['stratum']} row {it['index']} is disputed with no ruling")
    elif ruling["sided_with"] == "skeptic":
        require(ruling["verdict"] == it["first"], f"{it['stratum']} row {it['index']} sides with the skeptic on another verdict")
    before = {f: v.get(f) for f in FIRST_FIELDS}
    if ruling and ruling["sided_with"] != "skeptic":
        v.update({f: ruling[f] for f in FIRST_FIELDS})
    if regroup and not regroup["keep"]:
        v.update({f: regroup[f] for f in FIRST_FIELDS})
    if all(v.get(f) == before[f] for f in FIRST_FIELDS):
        return "held", None
    return ("verdict overturned" if v["verdict"] != it["first"] else "hint corrected"), before


def outcome_row(it, v, outcome):
    row = {"stratum": it["stratum"], "index": it["index"], "side": it["side"], "drawn": it["drawn"],
           "first": it["first"], "final": v["verdict"], "outcome": outcome}
    if it.get("regroup"):
        row["regroup"] = {"group": it["regroup"]["group"], "keep": it["regroup"]["keep"]}
    return row


def apply(review, N, M):
    summary = []
    for it in review["items"]:
        v = read_verdict(M, N, it)
        outcome, before = ruled(v, it)
        if before:
            require("first" not in v, f"{it['stratum']} row {it['index']} holds a first verdict already, which this would replace")
            v["first"] = before
        v["review"] = outcome
        summary.append(outcome_row(it, v, outcome))
    M["review"] = {"date": review["date"], "about": review["about"], "items": summary}
    return M


def apply_followup(reading, N, M):
    require("followup" not in M, "the record holds a follow-up already, which a second would replace")
    summary = []
    for it in reading["items"]:
        v = read_verdict(M, N, it)
        require("followup" not in v, f"{it['stratum']} row {it['index']} was read in a follow-up already")
        outcome, before = ruled(v, it)
        regrouped = it.get("regroup") and not it["regroup"]["keep"]
        v["followup"] = {"outcome": outcome, **({"before": before} if before else {}),
                         **({"regroup": it["regroup"]["group"]} if regrouped else {})}
        summary.append(outcome_row(it, v, outcome))
    M["followup"] = {"date": reading["date"], "about": reading["about"], "items": summary}
    if reading.get("regroup"):
        M["followup"]["regroup"] = reading["regroup"]
    return M


def main(argv):
    followup = argv[0] == "--followup"
    review, numbers, merged_in, merged_out = argv[1:5] if followup else argv[0:4]
    step = apply_followup if followup else apply
    M = step(json.load(open(review)), json.load(open(numbers)), json.load(open(merged_in)))
    json.dump(M, open(merged_out, "w"), indent=1)
    from collections import Counter
    print(Counter(x["outcome"] for x in M["followup" if followup else "review"]["items"]))


if __name__ == "__main__":
    main(sys.argv[1:])
