"""Read again, for #155, every number collision a skeptic put on the confirmed list
(confirmed-contradiction or updated-later) that #137's review did not read: 55 in the record as
#137 merged it. The review drew two such verdicts at random and overturned both, so the rest
were read again whole rather than sampled.

inputs writes the re-checkers' input files. Each item is the one sample_review.py writes for
the review, so the re-checkers read the same fields under the same brief; an artifact whose
page changed after the inventory read it says so under changed_since_inventory, since its text
and folder are the page as it is now. The items go to five re-checkers by row, every fifth to
each, and args.json is the workflow's input. The record has moved since, so the selection is
repeated from the record at commit fde5b06, with the words on changed pages taken from the
reading, which keeps them:

  git show fde5b06:artifacts/_synthesis/work/out/contradictions-merged.json > merged.json
  reread_numbers.py inputs merged.json out/numbers-partial.json ../inventory.json IN \\
      [ID=WHAT CHANGED...] [--against out/reread-confirmed-numbers.json]

record joins the re-checkers' and the judges' answers, kept in the workflow's journal, to the
items in the folder inputs wrote, and writes the reading in the form apply_review.py --followup
applies, NOTE closing the account of how it was read:

  reread_numbers.py record JOURNAL IN READING DATE [NOTE]

Rows that read the same figures were ruled apart, and a review of the follow-up found their
rulings did not agree, so each group of them was ruled again by one judge who read the
group's rows together. regroup-inputs writes that judge's input from the reading, the record
at fde5b06, the follow-up's input folder and GROUPS (a file of groups, or the reading, which
keeps them); regroup joins the judges' answers to the reading, which record must have written
first:

  reread_numbers.py regroup-inputs READING merged.json out/numbers-partial.json ../inventory.json GROUPS IN OUT
  reread_numbers.py regroup JOURNAL GROUPS READING DATE

SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
render_contradictions2.py. With --against, inputs stops unless it selects exactly the rows the
reading holds."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import verify_quotes as vq
from merge_skeptics import FIRST_FIELDS, require, results_of
from prep_verify import where
from sample_review import NUMBERS, verdicts

CHECKERS = 5
EXPECTED = 55
RECHECK_FIELDS = ("holds", "hint_ok", "verdict", "quote_a", "quote_b", "explanation", "resolution_hint")
RULING_FIELDS = ("sided_with", "verdict", "quote_a", "quote_b", "explanation", "resolution_hint")
NUMBER_SCALE = ("confirmed-contradiction", "updated-later", "same-number-restated", "scope-or-unit-differs",
                "different-quantities", "cannot-tell")
SMALL = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
# The one sentence the re-checkers' brief added to the review's, word for word.
PRIOR = ("This reading is the follow-up of issue #155: an earlier review drew two of these confirmed number verdicts "
         "at random and overturned both, so every one it left out is now read again.")


def key(x):
    return f"{x['stratum']}|{x['index']}"


def number_key_of(index):
    return f"{NUMBERS}|{index}"


def small(n):
    return SMALL[n] if n < len(SMALL) else str(n)


def unread_confirmed(items, review):
    """The number verdicts on the confirmed list that the review's sample left out."""
    read = {(x["stratum"], x["index"]) for x in review["items"]}
    return [x for x in items if x["stratum"] == NUMBERS and x["side"] == "confirmed" and (NUMBERS, x["index"]) not in read]


def mark_changed(items, changed):
    for x in items:
        for side in ("a", "b"):
            if x[side] and x[side]["id"] in changed:
                x[side]["changed_since_inventory"] = changed[x[side]["id"]]


def changed_words(rows):
    """What each changed page's items told the re-checkers, by artifact."""
    return {x[s]["id"]: x[s]["changed_since_inventory"] for x in rows.values() for s in ("a", "b")
            if x[s] and x[s].get("changed_since_inventory")}


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


def placer(inventory):
    text_dir, roots = vq.required_dir("SYNTH_TEXT"), vq.repos()
    meta = {f"{r['repo']}/{r['folder']}": (r.get("date"), r.get("title")) for r in json.load(open(inventory))["artifacts"]}
    return lambda aid: where(text_dir, roots, meta, aid)


def inputs(merged, numbers, inventory, out, *changed, against=None):
    M = json.load(open(merged))
    items = list(verdicts(M, json.load(open(numbers)), placer(inventory)))
    chosen = unread_confirmed(items, M["review"])
    require(len(chosen) == EXPECTED, f"{len(chosen)} unread confirmed number verdicts, not the {EXPECTED} #155 reads")
    changed = dict(c.split("=", 1) for c in changed)
    if against:
        reading = json.load(open(against))
        require({key(x) for x in chosen} == {key(x) for x in reading["items"]}, "the selection differs from the reading's rows")
        kept = reading.get("changed_since_inventory", {})
        require(not changed or changed == kept, "the changed pages differ from the reading's")
        changed = changed or kept
        print(f"the selection is the reading's: {len(chosen)} verdicts")
    mark_changed(chosen, changed)
    for u in write_inputs(chosen, out):
        print(u["file"], u["count"], " ".join(k.split("|")[1] for k in u["keys"]))


def answers(journal, rows, units):
    """Each re-checker's reading and each judge's ruling, by row. A re-checker answers only for
    the rows its unit gave it, a judge for any row; a row read twice, or a reading of a row its
    reader was not given, stops the run."""
    rechecks, rulings = {}, {}
    for r in results_of(journal):
        label = r["label"]
        if label.startswith("recheck:"):
            role, found, into, given = "recheck", r["result"]["items"], rechecks, set(units[int(label.rsplit(":", 1)[1])]["keys"])
        elif label.startswith("judge:"):
            role, found, into, given = "judge", r["result"]["rulings"], rulings, set(rows)
        else:
            continue
        for it in found:
            k = key(it)
            require(k in given and k not in into, f"a {role} answer for {k}, which is not one row given to it once")
            into[k] = it
    return rechecks, rulings


def about(items, judges, date, note):
    sides = Counter(x["first"] for x in items)
    sided = Counter(x["ruling"]["sided_with"] for x in items if x["ruling"])
    ruled = ", ".join(f"{n} with the {w}" if w != "neither" else f"{n} with neither" for w, n in sided.most_common())
    return (f"On {date} every number collision on the confirmed list that the review's sample left out, {len(items)} in all "
            f"({', '.join(f'{n} {w}' for w, n in sorted(sides.items()))}), was read again (issue #155) as the review read its sample, with three differences. "
            f"Five re-checkers read them, each given every fifth row, where the review gave its confirmed verdicts to three; "
            f"each artifact whose page changed after the inventory read it was marked so, with what changed; "
            f"and the re-checkers' brief, otherwise the review's, added one sentence: \"{PRIOR}\" "
            f"That sentence told the re-checkers that such verdicts had failed before, which may have made them readier to overturn, "
            f"so the follow-up's rates are its own and not to be pooled with the review's. "
            f"Each re-checker, told to overturn every verdict in its share and its hint, read both sources of each row and gave its own verdict, "
            f"whether the hint was right and the words it rests on. Where a re-checker overturned a verdict or its hint, one of {small(judges)} judges read both readings and the sources and ruled; "
            f"of the {sum(sided.values())} rulings, {ruled or 'none'}. work/tools/reread_numbers.py writes the re-checkers' input again from the record as #137 merged it (commit fde5b06), "
            f"and out/reread-confirmed-numbers.json holds each reading and ruling. {note}").strip()


def rows_in(inputs_dir):
    units = json.load(open(f"{inputs_dir}/args.json"))
    rows = {}
    for u in units:
        for x in json.load(open(u["file"]))["items"]:
            rows[key(x)] = x
    return rows, units


def record(journal, inputs_dir, out, date, note=""):
    rows, units = rows_in(inputs_dir)
    rechecks, rulings = answers(journal, rows, units)
    require(set(rechecks) == set(rows), f"rows no re-checker read: {sorted(set(rows) - set(rechecks))}")
    disputed = {k for k, it in rechecks.items() if not (it["holds"] and it["hint_ok"])}
    require(set(rulings) == disputed, f"disputes with no ruling {sorted(disputed - set(rulings))}, rulings with no dispute {sorted(set(rulings) - disputed)}")
    items = []
    for k, x in sorted(rows.items(), key=lambda kv: kv[1]["index"]):
        r = rulings.get(k)
        items.append({"stratum": x["stratum"], "index": x["index"], "side": "confirmed", "drawn": "all", "first": x["skeptic"]["verdict"],
                      "recheck": {f: rechecks[k][f] for f in RECHECK_FIELDS}, "ruling": {f: r[f] for f in RULING_FIELDS} if r else None})
    judges = len({r["label"] for r in results_of(journal) if r["label"].startswith("judge:")})
    json.dump({"date": date, "about": about(items, judges, date, note), "changed_since_inventory": changed_words(rows), "items": items},
              open(out, "w"), indent=1)
    print(len(items), "rows;", len(disputed), "disputes;", Counter(r["sided_with"] for r in rulings.values()))


def now_fields(x, it):
    """A row's verdict and words as the follow-up left it: its ruling's, where the ruling did
    not side with the skeptic, else the skeptic's."""
    r = it and it["ruling"]
    src = r if r and r["sided_with"] != "skeptic" else x["skeptic"]
    return {f: src.get(f) for f in FIRST_FIELDS}


def groups_of(path):
    d = json.load(open(path))
    return d["regroup"]["groups"] if "regroup" in d else d["groups"]


def group_entry(g, rows, by_key, others, place):
    def row(index):
        k = number_key_of(index)
        it = by_key.get(k)
        if it:
            return {**rows[k], "recheck": it["recheck"], "ruling": it["ruling"], "now": now_fields(rows[k], it)}
        x = others[k]
        return {**x, "now": now_fields(x, None), "read_by": "#137's review" if x["skeptic"].get("review") else "a skeptic only"}
    return {"group": g["name"], "title": g["title"], "points": g["points"], "rows": [row(i) for i in g["rows"]],
            "context": [row(i) for i in g["context"]], "extra": [place(aid) for aid in g["extra"]]}


def regroup_inputs(reading, merged, numbers, inventory, groups, inputs_dir, out):
    """One file per group for its judge: each row as the follow-up's re-checker had it, with
    its reading, ruling and verdict as the follow-up left it; each context row with the verdict
    it carries, which the judge does not rule; and the artifacts no row names that the review
    cited."""
    place = placer(inventory)
    rows, _ = rows_in(inputs_dir)
    by_key = {key(x): x for x in json.load(open(reading))["items"]}
    others = {key(x): x for x in verdicts(json.load(open(merged)), json.load(open(numbers)), place)}
    os.makedirs(out, exist_ok=True)
    units = []
    for g in groups_of(groups):
        require(all(number_key_of(i) in by_key for i in g["rows"]), f"group {g['name']} re-rules a row the follow-up did not read")
        path = f"{out}/group-{g['name']}.json"
        json.dump(group_entry(g, rows, by_key, others, place), open(path, "w"), indent=1)
        units.append({"name": g["name"], "file": path, "rows": [number_key_of(i) for i in g["rows"]],
                      "context": [number_key_of(i) for i in g["context"]]})
        print(path, "rows", *g["rows"], "context", *g["context"])
    json.dump(units, open(f"{out}/args.json", "w"), indent=1)


def listed(numbers):
    words = [str(n) for n in numbers]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def regroup_about(groups, ruled, date):
    kept = sum(1 for r in ruled.values() if r["keep"])
    names = "; ".join(f"{g['title']} (rows {listed(g['rows'])})" for g in groups)
    shown = sorted({i for g in groups for i in g["context"]})
    return (f"On {date} a review of the follow-up found that rows reading the same figures or the same pages, ruled one at a time, "
            f"did not agree with one another, and that two rulings rested on scopes the pages do not state. "
            f"They were ruled again in {small(len(groups))} groups: {names}. One judge for each group read all of its rows together, "
            f"each with both readings, its ruling and its verdict as the follow-up left it, and every source, the artifacts the review cited among them, "
            f"with the review's points given as claims to check against the texts and never to take as true; the judge kept each row's verdict and hint or ruled it again. "
            f"Of the {len(ruled)} rows, {kept} kept their verdict and hint and {len(ruled) - kept} were ruled again"
            + (f"; rows {listed(shown)}, shown to the judges beside them, stand as they were." if shown else ".")
            + " work/tools/reread_numbers.py writes each judge's input again from the reading and the follow-up's input.")


def check_group(g, answer, by_key):
    rows = {number_key_of(i) for i in g["rows"]}
    got = [key(r) for r in answer["rows"]]
    require(sorted(got) == sorted(rows), f"group {g['name']} answered rows {sorted(got)}, not {sorted(rows)}")
    require(sorted(c["index"] for c in answer["context"]) == sorted(g["context"]), f"group {g['name']} answered other context rows")
    for r in answer["rows"]:
        require(r["verdict"] in NUMBER_SCALE, f"row {r['index']} has no number verdict: {r['verdict']}")
        it = by_key[key(r)]
        now = it["ruling"]["verdict"] if it["ruling"] and it["ruling"]["sided_with"] != "skeptic" else it["first"]
        require(not r["keep"] or r["verdict"] == now, f"row {r['index']} keeps its verdict and gives another")


def regroup(journal, groups, reading_path, date):
    reading = json.load(open(reading_path))
    require("regroup" not in reading, "the reading holds a group re-rule already; run record again first")
    gs = groups_of(groups)
    found = {r["label"].split(":", 1)[1]: r["result"] for r in results_of(journal) if r["label"].startswith("regroup:")}
    require(sorted(found) == sorted(g["name"] for g in gs), f"answers for groups {sorted(found)}, not {sorted(g['name'] for g in gs)}")
    by_key = {key(x): x for x in reading["items"]}
    ruled = {}
    for g in gs:
        answer = found[g["name"]]
        check_group(g, answer, by_key)
        for r in answer["rows"]:
            ruled[key(r)] = {"group": g["name"], "keep": r["keep"], **{f: r[f] for f in FIRST_FIELDS}}
        g.update({"note": answer["group_note"], "context_notes": sorted(answer["context"], key=lambda c: c["index"])})
    for k, r in ruled.items():
        by_key[k]["regroup"] = r
    reading["regroup"] = {"date": date, "about": regroup_about(gs, ruled, date), "groups": gs}
    json.dump(reading, open(reading_path, "w"), indent=1)
    print(len(ruled), "rows re-ruled;", Counter("kept" if r["keep"] else f"ruled {r['verdict']}" for r in ruled.values()))


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
    elif argv[0] == "regroup-inputs":
        regroup_inputs(*argv[1:])
    elif argv[0] == "regroup":
        regroup(*argv[1:])
    else:
        raise SystemExit(f"unknown mode {argv[0]!r}; inputs, record, regroup-inputs or regroup")
