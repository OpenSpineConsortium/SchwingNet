"""Read again, for #155, every number collision a skeptic put on the confirmed list
(confirmed-contradiction or updated-later) that #137's review did not read: 55 in the record as
#137 merged it. The review drew two such verdicts at random and overturned both, so the rest
were read again whole rather than sampled.

inputs writes the re-checkers' input files. Each item is the one sample_review.py writes for
the review, so the re-checkers read the same fields under the same brief; an artifact whose
page changed after the inventory read it says so under changed_since_inventory, since its text
and folder are the page as it is now. The items go to five re-checkers by row, every fifth to
each, and args.json is the workflow's input. The record has moved since, so the selection is
repeated from the record at commit fde5b06:

  git show fde5b06:artifacts/_synthesis/work/out/contradictions-merged.json > merged.json
  reread_numbers.py inputs merged.json out/numbers-partial.json ../inventory.json OUT \\
      [ID=WHAT CHANGED...] [--against out/reread-confirmed-numbers.json]

record joins the re-checkers' and the judges' answers, kept in the workflow's journal, to the
items in the folder inputs wrote, and writes the reading in the form apply_review.py --followup
applies, NOTE closing the account of how it was read:

  reread_numbers.py record JOURNAL OUT READING DATE [NOTE]

SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
render_contradictions2.py. With --against, inputs stops unless it selects exactly the rows the
reading holds."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq
from merge_skeptics import require, results_of
from prep_verify import where
from sample_review import NUMBERS, verdicts

CHECKERS = 5
EXPECTED = 55
RECHECK_FIELDS = ("holds", "hint_ok", "verdict", "quote_a", "quote_b", "explanation", "resolution_hint")
RULING_FIELDS = ("sided_with", "verdict", "quote_a", "quote_b", "explanation", "resolution_hint")
SMALL = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")


def key(x):
    return f"{x['stratum']}|{x['index']}"


def unread_confirmed(items, review):
    """The number verdicts on the confirmed list that the review's sample left out."""
    read = {(x["stratum"], x["index"]) for x in review["items"]}
    return [x for x in items if x["stratum"] == NUMBERS and x["side"] == "confirmed" and (NUMBERS, x["index"]) not in read]


def mark_changed(items, changed):
    for x in items:
        for side in ("a", "b"):
            if x[side] and x[side]["id"] in changed:
                x[side]["changed_since_inventory"] = changed[x[side]["id"]]


def write_inputs(items, out):
    os.makedirs(out, exist_ok=True)
    units = []
    for k in range(CHECKERS):
        part = items[k::CHECKERS]
        path = f"{out}/confirmed-{k}.json"
        json.dump({"side": "confirmed", "items": part}, open(path, "w"), indent=1)
        units.append({"file": path, "side": "confirmed", "count": len(part), "keys": [key(x) for x in part]})
    json.dump(units, open(f"{out}/args.json", "w"), indent=1)
    return units


def inputs(merged, numbers, inventory, out, *changed, against=None):
    text_dir, roots = vq.required_dir("SYNTH_TEXT"), vq.repos()
    meta = {f"{r['repo']}/{r['folder']}": (r.get("date"), r.get("title")) for r in json.load(open(inventory))["artifacts"]}
    M = json.load(open(merged))
    items = list(verdicts(M, json.load(open(numbers)), lambda aid: where(text_dir, roots, meta, aid)))
    chosen = unread_confirmed(items, M["review"])
    require(len(chosen) == EXPECTED, f"{len(chosen)} unread confirmed number verdicts, not the {EXPECTED} #155 reads")
    if against:
        theirs = {key(x) for x in json.load(open(against))["items"]}
        require({key(x) for x in chosen} == theirs, "the selection differs from the reading's rows")
        print(f"the selection is the reading's: {len(theirs)} verdicts")
    mark_changed(chosen, dict(c.split("=", 1) for c in changed))
    for u in write_inputs(chosen, out):
        print(u["file"], u["count"], " ".join(k.split("|")[1] for k in u["keys"]))


def answers(journal, rows):
    """Each re-checker's reading and each judge's ruling, by row; a row read twice, or a reading
    of a row nobody was given, stops the run."""
    rechecks, rulings = {}, {}
    for r in results_of(journal):
        role, found = (("recheck", r["result"]["items"]) if r["label"].startswith("recheck:")
                       else ("judge", r["result"]["rulings"]) if r["label"].startswith("judge:") else (None, []))
        into = rechecks if role == "recheck" else rulings
        for it in found:
            k = key(it)
            require(k in rows and k not in into, f"a {role} answer for {k}, which is not one row given once")
            into[k] = it
    return rechecks, rulings


def about(items, judges, date, note):
    sides = Counter(x["first"] for x in items)
    sided = Counter(x["ruling"]["sided_with"] for x in items if x["ruling"])
    ruled = ", ".join(f"{n} with the {w}" if w != "neither" else f"{n} with neither" for w, n in sided.most_common())
    return (f"On {date} every number collision on the confirmed list that the review's sample left out, {len(items)} in all "
            f"({', '.join(f'{n} {w}' for w, n in sorted(sides.items()))}), was read again by the review's own method and briefs (issue #155). "
            f"Five re-checkers, each given every fifth row and told to overturn every verdict in its share and its hint, read both sources of each and gave their own verdict, "
            f"whether the hint was right and the words they rest on. Where a re-checker overturned a verdict or its hint, one of {SMALL[judges] if judges < len(SMALL) else judges} judges read both readings and the sources and ruled; "
            f"of the {sum(sided.values())} rulings, {ruled or 'none'}. work/tools/reread_numbers.py writes the re-checkers' input again from the record as #137 merged it (commit fde5b06), "
            f"and out/reread-confirmed-numbers.json holds each reading and ruling. {note}").strip()


def record(journal, inputs_dir, out, date, note=""):
    rows = {}
    for u in json.load(open(f"{inputs_dir}/args.json")):
        for x in json.load(open(u["file"]))["items"]:
            rows[key(x)] = x
    rechecks, rulings = answers(journal, rows)
    require(set(rechecks) == set(rows), f"rows no re-checker read: {sorted(set(rows) - set(rechecks))}")
    disputed = {k for k, it in rechecks.items() if not (it["holds"] and it["hint_ok"])}
    require(set(rulings) == disputed, f"disputes with no ruling {sorted(disputed - set(rulings))}, rulings with no dispute {sorted(set(rulings) - disputed)}")
    items = []
    for k, x in sorted(rows.items(), key=lambda kv: kv[1]["index"]):
        r = rulings.get(k)
        items.append({"stratum": x["stratum"], "index": x["index"], "side": "confirmed", "drawn": "all", "first": x["skeptic"]["verdict"],
                      "recheck": {f: rechecks[k][f] for f in RECHECK_FIELDS}, "ruling": {f: r[f] for f in RULING_FIELDS} if r else None})
    judges = len({r["label"] for r in results_of(journal) if r["label"].startswith("judge:")})
    json.dump({"date": date, "about": about(items, judges, date, note), "items": items}, open(out, "w"), indent=1)
    print(len(items), "rows;", len(disputed), "disputes;", Counter(r["sided_with"] for r in rulings.values()))


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[0] == "inputs":
        rest, against = argv[1:], None
        if "--against" in rest:
            k = rest.index("--against")
            against, rest = rest[k + 1], rest[:k] + rest[k + 2:]
        inputs(*rest, against=against)
    elif argv[0] == "record":
        record(*argv[1:])
    else:
        raise SystemExit(f"unknown mode {argv[0]!r}; inputs or record")
