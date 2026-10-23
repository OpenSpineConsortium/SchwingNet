"""Read again, for #155, every number collision a skeptic put on the confirmed list
(confirmed-contradiction or updated-later) that #137's review did not read: 55 in the record as
#137 merged it. The review drew two such verdicts at random and overturned both, so the rest
were read again whole rather than sampled.

inputs writes the re-checkers' input files. Each item is the one sample_review.py writes for
the review, so the re-checkers read the same fields under the same brief; an artifact whose
page changed after the inventory read it says so under changed_since_inventory, since its text
and folder are the page as it is now. The items go to five re-checkers by row, every fifth to
each, and args.json is the input of the workflow, workflows/reread-confirmed-numbers.js, which
holds the re-checkers' and the judges' briefs. The record has moved since, so the selection is
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
keeps them), and OUT/args.json is the input of workflows/regroup-confirmed-numbers.js, which
holds the judges' brief; regroup joins the judges' answers to the reading, which record must
have written first:

  reread_numbers.py regroup-inputs READING merged.json out/numbers-partial.json ../inventory.json GROUPS IN OUT
  reread_numbers.py regroup JOURNAL GROUPS READING DATE

A second review then found rows of three groups still at odds with the texts, and cluster rows
giving the groups' figures that no judge had set beside the findings. second-inputs writes the
second round's input from the reading, which regroup must have written first (one that holds
the second round too is read as the first re-rule left it), the record at fde5b06, the
follow-up's input folder and GROUPS2 (a file of the second round's groups, or the reading,
which keeps them): for each group ruled a second time, one judge's file, with the rows as the
first group re-rule left them; and for every group, the cluster rows the page's rule
marks for it (render_contradictions2.py), each to be set beside the group's finding as it then
stands, by the group's judge or by readers given that finding. OUT/args.json is the input of
workflows/second-regroup-confirmed-numbers.js, which holds the brief; second joins the
answers to the reading:

  reread_numbers.py second-inputs READING merged.json out/numbers-partial.json ../inventory.json GROUPS2 IN OUT
  reread_numbers.py second JOURNAL GROUPS2 OUT/args.json READING DATE

The second round marked the cluster rows by a narrow rule, which second-inputs keeps so that
the round's input can be written again: each of a row's pages read by the group's judge, or two
of the group's figures and one of those pages. A third review found rows it missed that plainly
bear on a finding, so the page's rule now also counts as read the pages of the cluster rows the
second round read beside a group, and needs one figure on one page read for the group.
notes3-inputs writes, for each group, the rows the rule now marks that the second round did not
note, in one reader's file with the group's finding as it now stands (one that holds the third
pass too is read without it); OUT/args.json is the input of
workflows/more-cluster-rows-confirmed-numbers.js, and notes3 joins the readers' notes to the
reading, which second must have written first:

  reread_numbers.py notes3-inputs READING merged.json out/numbers-partial.json ../inventory.json IN OUT
  reread_numbers.py notes3 JOURNAL OUT/args.json READING DATE

A fourth review found that the rule read a row's figures in its quotes alone, so a confirmed
row whose verdict's explanation and hint give a group's figures went unmarked, and that it took
any two digits as a figure, so rows were marked on the 12 of T12. The page's rule now also
reads each verdict's explanation and hint, takes a figure only where it stands alone, and needs
two where each a row shares is a whole number under 100 (render_contradictions2.siblings_of
keeps the three earlier rules, so each round's input can be written again). notes4-inputs
writes the readers' files for the rows it adds, and in OUT/args.json the rows an earlier round
noted that it no longer marks, whose notes the page then leaves out; the readers run
workflows/fourth-cluster-rows-confirmed-numbers.js, and notes4 joins their notes, which notes3
must have written first. correct then puts the editor's words on hints and notes, kept in
work/editor-corrections.json, in the reading, where apply_review.py --followup carries them to
the record and the page shows each in square brackets:

  reread_numbers.py notes4-inputs READING merged.json out/numbers-partial.json ../inventory.json IN OUT
  reread_numbers.py notes4 JOURNAL OUT/args.json READING DATE
  reread_numbers.py correct READING editor-corrections.json DATE

SYNTH_TEXT, SYNTH_SCHWINGNET and SYNTH_SYMPHONY name the texts and the clones, as for
render_contradictions2.py. With --against, inputs stops unless it selects exactly the rows the
reading holds."""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import re

import verify_quotes as vq
from apply_review import standing
from merge_skeptics import FIRST_FIELDS, require, results_of
from prep_verify import where
from render_contradictions2 import BEARS, artifact, bears_words, final_groups, siblings_of
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
# The four sentences the group judges' scale added to the re-checkers', word for word as both
# group workflows give them, and the two rules the second round's brief added to the first's.
# The judges' scale also glossed cannot-tell for a number collision as the re-checkers' scale
# glosses it for a cluster candidate.
GLOSS = "(the texts do not settle it)"
SCALE_ADDED = (
    "Apply it exactly.",
    "A scope-or-unit-differs needs the pages themselves to state the scope, subset, denominator, unit, interval, version or date that sets the two apart; "
    "a scope that you or an earlier reader only computed or inferred from other figures is not enough, and such a row is a confirmed-contradiction or a cannot-tell, "
    "with the inference given in the hint as what a record would have to confirm.",
    "An updated-later needs the later page to be later by its date or to plainly follow the other; "
    "a page of the same date that still gives the earlier figure bears on whether the figure was replaced.",
    "A cannot-tell is right when the texts do not settle the question; never choose a figure the texts do not choose.")
RULES_ADDED = (
    "Never copy a login or a grid path.",
    "The project's owner has settled which data the project may use and which sets may enter training: "
    "do not raise either in a hint, a note or an explanation, and never propose dropping or qualifying a result on that account.")
# The sentence the third pass's account of the work added to the second round's, word for word,
# and the parts of the second round's brief its readers were given unchanged.
HISTORY_ADDED = ("A second review then had three of the groups ruled a second time, and the cluster rows that give a group's figures "
                 "on the pages its judges read set beside its finding; a third review found more cluster rows that give a group's figures, "
                 "on pages read beside the group or with one of its figures on a page its judge read, that nobody had set beside the finding.")
SHARED = ("PAGE", "HISTORY", "READING", "SCALE", "RULES", "SIBLING_TASK")
# The sentence the fourth pass's account of the work added to the third's, word for word.
HISTORY4_ADDED = ("A fourth review then found a cluster row whose verdict's explanation and hint give a group's figures that its quotes do not, "
                  "and rows marked on digits that are not a group's figures, so the rule now also reads each verdict's explanation and hint, "
                  "takes a figure only where it stands alone, and needs two where each it shares is a whole number under 100.")
CORRECTION_KEYS = {"hint": ("to", "kind", "index", "words", "why"), "note": ("to", "kind", "group", "cluster", "index", "words", "why")}
WORKFLOWS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "workflows")


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
    """A row's verdict and words as the follow-up's re-check left it: its ruling's, where it was
    ruled, else the skeptic's. A ruling that sided with the skeptic in other words reads as the
    ruling has it, as apply_review.standing reads it; no row of a group was ruled so, so the
    first group re-rule's input is the same either way. The group re-rules come after, in
    standing_entry and the passes of notes."""
    r = it and it["ruling"]
    src = r if r else x["skeptic"]
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


def given_word_for_word(workflow, sentences):
    """The sentences a brief added, refused unless the workflow still gives each word for word,
    so the page never quotes a brief the judges were not given."""
    text = open(os.path.join(WORKFLOWS, workflow)).read()
    missing = [s[:60] for s in sentences if s not in text]
    require(not missing, f"{workflow} does not give these word for word: {missing}")
    return sentences


def quoted(sentences):
    return " ".join(f'"{s}"' for s in sentences)


def constant(workflow, name):
    """A text a workflow script gives as a constant, so a later script can be held to it."""
    found = re.findall(rf"^const {name} = `([^`]*)`$", open(os.path.join(WORKFLOWS, workflow)).read(), re.M)
    require(len(found) == 1, f"{workflow} gives {name} {len(found)} times, not once")
    return found[0]


def regroup_about(groups, ruled, date):
    kept = sum(1 for r in ruled.values() if r["keep"])
    names = "; ".join(f"{g['title']} (rows {listed(g['rows'])})" for g in groups)
    shown = sorted({i for g in groups for i in g["context"]})
    added = given_word_for_word("regroup-confirmed-numbers.js", SCALE_ADDED)
    given_word_for_word("regroup-confirmed-numbers.js", [f"cannot-tell {GLOSS}. Apply it exactly."])
    given_word_for_word("reread-confirmed-numbers.js", [f"cannot-tell {GLOSS}. For a number collision:", "(not the same thing), cannot-tell.`"])
    return (f"On {date} a review of the follow-up found that rows reading the same figures or the same pages, ruled one at a time, "
            f"did not agree with one another, and that two rulings rested on scopes the pages do not state. "
            f"They were ruled again in {small(len(groups))} groups: {names}. One judge for each group read all of its rows together, "
            f"each with both readings, its ruling and its verdict as the follow-up left it, and every source, the artifacts the review cited among them, "
            f"with the review's points given as claims to check against the texts and never to take as true; the judge kept each row's verdict and hint or ruled it again. "
            f"The judges' scale was the re-checkers', with cannot-tell glossed \"{GLOSS}\" for a number collision as the re-checkers' scale glosses it for a cluster candidate, "
            f"and {small(len(added))} sentences added, which the re-checkers did not have: {quoted(added)} "
            f"Of the {len(ruled)} rows, {kept} kept their verdict and hint and {len(ruled) - kept} were ruled again"
            + (f"; rows {listed(shown)}, shown to the judges beside them, stand as they were in that round." if shown else ".")
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


def sibling_key(c, i):
    return f"{c}|{i}"


def second_groups_of(path):
    d = json.load(open(path))
    return d["regroup2"]["groups"] if "regroup2" in d else d["groups"]


def after_first(x, it):
    """A row's verdict and words as the page carries them after the first group re-rule: the
    skeptic's, then its ruling's where it was ruled, then the first group judge's where that did
    not keep them. x is the row as the re-checkers were given it, it the reading's item."""
    out = {f: x["skeptic"].get(f) for f in FIRST_FIELDS}
    if it.get("ruling"):
        out.update({f: it["ruling"][f] for f in FIRST_FIELDS})
    r = it.get("regroup")
    if r and not r["keep"]:
        out.update({f: r[f] for f in FIRST_FIELDS})
    return out


def as_groups(first, plan):
    """The groups as the second round defines them: a group ruled a second time takes its rows,
    the rows set beside them and its sources from the plan, so the page's rule marks the cluster
    rows of the groups as they will stand."""
    by = {g["name"]: g for g in plan}
    return [{**g, **{k: by[g["name"]][k] for k in ("rows", "context", "extra")}} if by.get(g["name"], {}).get("rule") else g
            for g in first]


def cluster_row(M, place, c, i):
    """A cluster row as a judge or reader is given it: what the reader found, both artifacts,
    and the verdict it carries with the words it rests on."""
    cl = next(x for x in M["clusters"] if x["cluster"] == c)
    x, v = cl["candidates"][i], cl["verdicts"][i]
    b = x.get("artifact_b")
    return {"cluster": c, "index": i, "kind": x["kind"], "topic": x["topic"],
            "a": place(x["artifact_a"]), "statement_a": x.get("statement_a"), "quote_a": x.get("quote_a"),
            "b": place(b) if artifact(b) else None, "statement_b": x.get("statement_b"), "quote_b": x.get("quote_b"),
            "why_it_matters": x.get("why_it_matters"), "verdict": {f: v.get(f) for f in FIRST_FIELDS},
            "read_by": "a cluster skeptic and #137's review" if v.get("review") else "a cluster skeptic"}


def by_clusters(keys, parts):
    """Rows split into parts with each cluster's rows kept together, the parts as even as whole
    clusters allow, so a reader sees every row of a page it reads."""
    clusters = {}
    for c, i in keys:
        clusters.setdefault(c, []).append((c, i))
    out = [[] for _ in range(parts)]
    for rows in sorted(clusters.values(), key=len, reverse=True):
        min(out, key=len).extend(rows)
    return [sorted(p, key=keys.index) for p in out]


def standing_entry(g, rows, by_key, others, place):
    """A group's file as its judge or reader is given it, with the verdict and words of each
    row, and of each row set beside them that the follow-up read, as the page carries them
    after the first group re-rule."""
    entry = group_entry(g, rows, by_key, others, place)
    for r in entry["rows"] + entry["context"]:
        it = by_key.get(key(r))
        if it:
            r["now"] = after_first(rows[key(r)], it)
            r["first_regroup"] = it.get("regroup")
    return entry


def second_inputs(reading, merged, numbers, inventory, groups2, inputs_dir, out):
    """The second round's files: one per group ruled again, for its judge, with each row as the
    first group re-rule left it, that judge's ruling of it and finding, the rows and cluster rows
    set beside them and the sources; and the cluster rows the page's rule marks for each group,
    in the judge's file where the judge notes them, else in files of their own for readers, a
    reader of a group not ruled again given its finding as the first re-rule left it, and a
    reader of a group ruled again pointed to the judge's file, whose rows give the standing
    words of each row the judge keeps. A reading that holds the second round already is read as
    the first group re-rule left it, so the files can be written again from the reading as it
    now stands and set beside the ones the round was given."""
    place = placer(inventory)
    R = json.load(open(reading))
    require("regroup" in R, "the reading must hold the first group re-rule")
    M, N = json.load(open(merged)), json.load(open(numbers))
    rows, _ = rows_in(inputs_dir)
    by_key = {key(x): x for x in R["items"]}
    others = {key(x): x for x in verdicts(M, N, place)}
    plan = second_groups_of(groups2)
    first = {g["name"]: g for g in R["regroup"]["groups"]}
    require(sorted(first) == sorted(g["name"] for g in plan), "the second round's plan names other groups than the first re-rule")
    marked = {g["name"]: [(c, i) for c, i, _ in mine] for g, mine in siblings_of(as_groups(R["regroup"]["groups"], plan), M, N, "narrow")}
    os.makedirs(out, exist_ok=True)
    units = []
    for g in plan:
        f, sib = first[g["name"]], marked.get(g["name"], [])
        require(g["rule"] or g["readers"], f"group {g['name']} is neither ruled again nor read for its cluster rows")
        unit = {"name": g["name"], "title": f["title"], "rule": g["rule"], "file": None, "rows": [], "context": [],
                "siblings": [], "readers": []}
        if g["rule"]:
            require(all(number_key_of(i) in by_key for i in g["rows"]), f"group {g['name']} re-rules a row the follow-up did not read")
            entry = standing_entry({**f, **g}, rows, by_key, others, place)
            entry["first_finding"] = {"group_note": f["note"], "context_notes": f.get("context_notes", [])}
            entry["cluster_context"] = [cluster_row(M, place, c, i) for c, i in g.get("cluster_context", [])]
            if not g["readers"]:
                entry["siblings"] = [cluster_row(M, place, c, i) for c, i in sib]
                unit["siblings"] = [sibling_key(c, i) for c, i in sib]
            unit.update(file=f"{out}/group2-{g['name']}.json", rows=[key(r) for r in entry["rows"]],
                        context=[key(r) for r in entry["context"]])
            json.dump(entry, open(unit["file"], "w"), indent=1)
        else:
            entry = standing_entry(f, rows, by_key, others, place)
            entry["finding"] = {"group_note": f["note"], "context_notes": f.get("context_notes", [])}
        for k, part in enumerate(by_clusters(sib, g["readers"]) if g["readers"] else []):
            path = f"{out}/notes2-{g['name']}-{k}.json"
            body = {"group": g["name"], "title": f["title"], "siblings": [cluster_row(M, place, c, i) for c, i in part]}
            if g["rule"]:
                body["group_file"] = unit["file"]
            else:
                body.update(finding=entry["finding"], rows=entry["rows"], context=entry["context"], extra=entry["extra"])
            json.dump(body, open(path, "w"), indent=1)
            unit["readers"].append({"file": path, "siblings": [sibling_key(c, i) for c, i in part]})
        units.append(unit)
        print(g["name"], "ruled again" if g["rule"] else "notes only", "rows", *g.get("rows", []), "siblings", len(sib),
              "readers", [len(r["siblings"]) for r in unit["readers"]])
    json.dump(units, open(f"{out}/args.json", "w"), indent=1)


def check_notes(name, notes, given):
    got = [sibling_key(n["cluster"], n["index"]) for n in notes]
    require(sorted(got) == sorted(given) and len(set(got)) == len(got), f"group {name} noted rows {sorted(got)}, not {sorted(given)}")
    require(all(n["bears"] in BEARS for n in notes), f"a note on group {name} is not one of {BEARS}")


def check_second(g, unit, answer):
    now = {key(r): r["now"] for r in json.load(open(unit["file"]))["rows"]}
    require(sorted(key(r) for r in answer["rows"]) == sorted(unit["rows"]), f"group {g['name']} answered other rows")
    require(sorted(number_key_of(c["index"]) for c in answer["context"]) == sorted(unit["context"]), f"group {g['name']} answered other context rows")
    for r in answer["rows"]:
        require(r["verdict"] in NUMBER_SCALE, f"row {r['index']} has no number verdict: {r['verdict']}")
        require(not r["keep"] or r["verdict"] == now[key(r)]["verdict"], f"row {r['index']} keeps its verdict and gives another")


def second_about(plan, units, ruled, notes, date):
    again = [g for g in plan if g["rule"]]
    kept = sum(1 for r in ruled.values() if r["keep"])
    titles = {u["name"]: u["title"] for u in units}
    names = "; ".join(f"{titles[g['name']]} (rows {listed(g['rows'])})" for g in again)
    by_judge = [f'"{titles[u["name"]]}"' for u in units if u["rule"] and not u["readers"]]
    by_readers = [f'"{titles[u["name"]]}"' for u in units if u["readers"]]
    who = " and ".join(w for w in (by_judge and f"by the group's judge for {listed(by_judge)}",
                                   by_readers and f"by readers given the finding for {listed(by_readers)}") if w)
    bears = Counter(n["bears"] for n in notes)
    added = given_word_for_word("second-regroup-confirmed-numbers.js", SCALE_ADDED + RULES_ADDED)[len(SCALE_ADDED):]
    return (f"On {date} a second review of the follow-up found rows of {small(len(again))} groups still at odds with the texts or with one another, "
            f"the rules added to the judges' scale not stated on this page, and the cluster rows that give the groups' figures marked to be read beside the findings "
            f"with nothing said of whether they agree. The {small(len(again))} groups were ruled a second time: {names}. One judge for each read its rows together "
            f"as the first group re-rule left them, with that judge's ruling of each and its finding, the rows and cluster rows set beside them and every source, "
            f"the second review's points given as claims to check against the texts and never to take as true, under the same scale; "
            f"of the {len(ruled)} rows, {kept} kept their verdict and hint and {len(ruled) - kept} were ruled again. "
            f"Then each cluster row the rule then marked, narrower than the one below, was set beside its group's finding as it then stood, {who}, "
            f"who said whether its instruction agrees with the finding, differs from it or is about another quantity: "
            f"{bears['agrees']} agree, {bears['differs']} differ and {bears['other']} are about another quantity. "
            f"The brief added {small(len(added))} rules to the first round's: {quoted(added)} "
            "work/tools/reread_numbers.py writes the second round's input again from the reading and the follow-up's input.")


def second(journal, groups2, args, reading_path, date):
    reading = json.load(open(reading_path))
    require("regroup" in reading and "regroup2" not in reading, "the reading must hold the first group re-rule and not a second")
    plan, units = second_groups_of(groups2), json.load(open(args))
    require([g["name"] for g in plan] == [u["name"] for u in units], "the plan and the input name other groups")
    found = {r["label"]: r["result"] for r in results_of(journal)}
    expected = ({f"regroup2:{u['name']}" for u in units if u["rule"]}
                | {f"notes2:{u['name']}:{k}" for u in units for k in range(len(u["readers"]))})
    require(set(found) == expected, f"no answer from {sorted(expected - set(found))}, or one from {sorted(set(found) - expected)}")
    by_key = {key(x): x for x in reading["items"]}
    ruled, groups, every_note = {}, [], []
    for g, u in zip(plan, units):
        entry = {"name": g["name"], "rule": g["rule"], "readers": g["readers"]}
        answer = found.get(f"regroup2:{g['name']}")
        if g["rule"]:
            check_second(g, u, answer)
            for r in answer["rows"]:
                ruled[key(r)] = {"group": g["name"], "keep": r["keep"], **{f: r[f] for f in FIRST_FIELDS}}
            entry.update({k: g[k] for k in ("rows", "context", "extra", "points")}, cluster_context=g.get("cluster_context", []),
                         note=answer["group_note"], context_notes=sorted(answer["context"], key=lambda c: c["index"]))
        notes = list(answer["siblings"]) if u["siblings"] else []
        check_notes(g["name"], notes, u["siblings"])
        for k, reader in enumerate(u["readers"]):
            part = found[f"notes2:{g['name']}:{k}"]["siblings"]
            check_notes(f"{g['name']} (reader {k})", part, reader["siblings"])
            notes += part
        entry["siblings"] = sorted(({f: n[f] for f in ("cluster", "index", "bears", "note")} for n in notes),
                                   key=lambda n: (n["cluster"], n["index"]))
        every_note += entry["siblings"]
        groups.append(entry)
    for k, r in ruled.items():
        by_key[k]["regroup2"] = r
    reading["regroup2"] = {"date": date, "about": second_about(plan, units, ruled, every_note, date), "groups": groups}
    json.dump(reading, open(reading_path, "w"), indent=1)
    print(len(ruled), "rows ruled a second time;", Counter("kept" if r["keep"] else f"ruled {r['verdict']}" for r in ruled.values()),
          "; notes", Counter(n["bears"] for n in every_note))


def unnoted(reading, M, N, rule):
    """For each group, the cluster rows the rule marks that no round of notes set beside its
    finding, with the group as it now stands."""
    out = []
    for g, mine in siblings_of(final_groups(reading), M, N, rule):
        noted = {(n["cluster"], n["index"]) for n in g["notes"] or []}
        new = [(c, i) for c, i, _ in mine if (c, i) not in noted]
        if new:
            out.append((g, new))
    return out


def notes3_inputs(reading, merged, numbers, inventory, inputs_dir, out):
    """The third pass's files, one reader's for each group the third rule marks new cluster
    rows for: the rows, with the group's finding as it now stands (the second judge's where the
    group was ruled a second time), the group's rows and the rows set beside them, each with
    its verdict and words as the page carries them after both group re-rules, the cluster rows
    its judge read beside it and its sources. A reading that holds the third pass already, or
    what came after it, is read without them, so the files can be written again from the
    reading as it now stands and set beside the ones the readers were given."""
    R = json.load(open(reading))
    require("regroup2" in R, "the reading must hold the second group re-rule")
    for k in ("notes3", "notes4", "corrections"):
        R.pop(k, None)
    M, N = json.load(open(merged)), json.load(open(numbers))
    units = reader_files(R, M, N, inventory, inputs_dir, out, "notes3", unnoted(R, M, N, "third"))
    json.dump(units, open(f"{out}/args.json", "w"), indent=1)


def notes4_inputs(reading, merged, numbers, inventory, inputs_dir, out):
    """The fourth pass's files, as the third pass's are written, for the rows the fourth rule
    marks that no round noted; args.json holds, beside the readers' files, the rows an earlier
    round noted that the fourth rule no longer marks, whose notes the page leaves out. A reading
    that holds the fourth pass already, or the editor's words, is read without them."""
    R = json.load(open(reading))
    require("notes3" in R, "the reading must hold the third pass")
    for k in ("notes4", "corrections"):
        R.pop(k, None)
    M, N = json.load(open(merged)), json.load(open(numbers))
    units = reader_files(R, M, N, inventory, inputs_dir, out, "notes4", unnoted(R, M, N, "fourth"))
    gone = unmarked_by(R, M, N, "fourth")
    json.dump({"units": units, "unmarked": gone}, open(f"{out}/args.json", "w"), indent=1)
    print("unmarked", len(gone), Counter(u["bears"] for u in gone))


def unmarked_by(reading, M, N, rule):
    """The rows a round of notes set beside a group's finding that the rule no longer marks,
    each with its group, the round that noted it and its note's word."""
    out = []
    for g in final_groups(reading):
        marked = {(c, i) for _, mine in siblings_of([g], M, N, rule) for c, i, _ in mine}
        out += [{"group": g["name"], "cluster": n["cluster"], "index": n["index"], "round": n["round"], "bears": n["bears"]}
                for n in g["notes"] or [] if (n["cluster"], n["index"]) not in marked]
    return sorted(out, key=lambda u: (u["group"], u["cluster"], u["index"]))


def reader_files(R, M, N, inventory, inputs_dir, out, round_name, new_rows):
    """One reader's file for each group with rows to note, and the units that name them."""
    place = placer(inventory)
    rows, _ = rows_in(inputs_dir)
    by_key = {key(x): x for x in R["items"]}
    others = {key(x): x for x in verdicts(M, N, place)}
    second = {g["name"]: g for g in R["regroup2"]["groups"]}
    os.makedirs(out, exist_ok=True)
    units = []
    for g, new in new_rows:
        entry = group_entry(g, rows, by_key, others, place)
        for r in entry["rows"] + entry["context"]:
            it = by_key.get(key(r))
            if it:
                r["now"] = standing({f: rows[key(r)]["skeptic"].get(f) for f in FIRST_FIELDS}, it)
        path = f"{out}/{round_name}-{g['name']}-0.json"
        body = {"group": g["name"], "title": g["title"], "siblings": [cluster_row(M, place, c, i) for c, i in new],
                "finding": {"group_note": g["note"], "context_notes": g.get("context_notes", [])},
                "rows": entry["rows"], "context": entry["context"],
                "cluster_context": [cluster_row(M, place, c, i) for c, i in second.get(g["name"], {}).get("cluster_context", [])],
                "extra": entry["extra"]}
        json.dump(body, open(path, "w"), indent=1)
        units.append({"name": g["name"], "title": g["title"], "readers": [{"file": path, "siblings": [sibling_key(c, i) for c, i in new]}]})
        print(g["name"], "new cluster rows", len(new), " ".join(sibling_key(c, i) for c, i in new))
    return units


def notes3_about(units, notes, date):
    second = "second-regroup-confirmed-numbers.js"
    given_word_for_word("more-cluster-rows-confirmed-numbers.js", [constant(second, k) for k in SHARED])
    added = given_word_for_word("more-cluster-rows-confirmed-numbers.js", [HISTORY_ADDED])
    bears = Counter(n["bears"] for n in notes)
    titles = listed([f"{sum(len(r['siblings']) for r in u['readers'])} for {u['title']}" for u in units])
    return (f"On {date} a third review of the follow-up found cluster rows that give a group's figures on pages read for the group, "
            "two of them at odds with a finding, which the rule did not mark, so that nobody had set them beside the findings. "
            "The rule now also counts as read the pages of the cluster rows the second re-rule's judges or readers read beside a group, "
            "and marks a row that gives one of the group's figures on one page read for the group, where it needed each of the row's pages read, or two of the figures. "
            f"Each of the {len(notes)} rows this adds, {titles}, was set beside its group's finding as it now stands by one reader for the group, "
            "given the finding, the group's rows and the rows set beside them with the words they now carry, the cluster rows its judge read beside it and its sources, "
            "under the second re-rule's account of the page, reading instructions, scale, rules and task for the cluster rows, word for word, "
            f"with one sentence added to its account of the work: {quoted(added)} "
            f"Of the {len(notes)}, {bears_words(bears)}. "
            "work/tools/reread_numbers.py writes the readers' input again from the reading and the follow-up's input.")


def notes3(journal, args, reading_path, date):
    reading = json.load(open(reading_path))
    require("regroup2" in reading and "notes3" not in reading, "the reading must hold the second group re-rule and not the third pass")
    units = json.load(open(args))
    found = {r["label"]: r["result"] for r in results_of(journal)}
    expected = {f"notes3:{u['name']}:{k}" for u in units for k in range(len(u["readers"]))}
    require(set(found) == expected, f"no answer from {sorted(expected - set(found))}, or one from {sorted(set(found) - expected)}")
    groups, every_note = [], []
    for u in units:
        notes = []
        for k, reader in enumerate(u["readers"]):
            part = found[f"notes3:{u['name']}:{k}"]["siblings"]
            check_notes(f"{u['name']} (reader {k})", part, reader["siblings"])
            notes += part
        siblings = sorted(({f: n[f] for f in ("cluster", "index", "bears", "note")} for n in notes), key=lambda n: (n["cluster"], n["index"]))
        groups.append({"name": u["name"], "readers": len(u["readers"]), "siblings": siblings})
        every_note += siblings
    reading["notes3"] = {"date": date, "about": notes3_about(units, every_note, date), "groups": groups}
    json.dump(reading, open(reading_path, "w"), indent=1)
    print(len(every_note), "cluster rows noted;", Counter(n["bears"] for n in every_note))


NOTED = {"agrees": "agreeing with their finding", "differs": "differing from their finding", "other": "about another quantity"}


def unmarked_words(unmarked):
    """What the fourth rule takes off the page: the rows marked before that it no longer marks,
    by what their notes said."""
    if not unmarked:
        return "This unmarks no row marked before, and "
    gone = Counter(u["bears"] for u in unmarked)
    noted = ("all of them noted as about another quantity" if set(gone) == {"other"}
             else "noted " + listed([f"{k} as {NOTED[b]}" for b, k in sorted(gone.items())]))
    rows = "row" if len(unmarked) == 1 else "rows"
    return f"This unmarks {len(unmarked)} {rows} marked before, {noted}, whose notes stay in the follow-up's reading and leave the page, and "


def notes4_about(units, notes, unmarked, date):
    third = "more-cluster-rows-confirmed-numbers.js"
    given_word_for_word("fourth-cluster-rows-confirmed-numbers.js", [constant(third, k) for k in SHARED])
    added = given_word_for_word("fourth-cluster-rows-confirmed-numbers.js", [HISTORY4_ADDED])
    bears = Counter(n["bears"] for n in notes)
    titles = listed([f"{sum(len(r['siblings']) for r in u['readers'])} for {u['title']}" for u in units])
    return (f"On {date} a fourth review of the follow-up re-ran every step and found them reproduced. It found that the rule read a cluster row's figures "
            "in its quotes alone, so a confirmed row whose verdict's explanation and hint give a group's figures, and tell a planner which to carry, was not marked, "
            "and that the rule took any run of two digits or more as a figure, so rows were marked on the 12 of T12, the 42 of a time of day or the 20 of a price. "
            "The rule now also reads each verdict's explanation and hint, takes a figure only where it stands alone, not joined to a letter, a colon or a date, "
            "and needs two of a group's figures where each a row shares is a whole number under 100. "
            + unmarked_words(unmarked)
            + f"adds {len(notes)}, {titles}, each set beside its group's finding as it now stands by one reader for the group under the third pass's brief, "
            f"word for word, with one sentence added to its account of the work: {quoted(added)} "
            f"Of the {len(notes)}, {bears_words(bears)}. "
            "work/tools/reread_numbers.py writes the readers' input again from the reading and the follow-up's input.")


def notes4(journal, args, reading_path, date):
    reading = json.load(open(reading_path))
    require("notes3" in reading and "notes4" not in reading, "the reading must hold the third pass and not the fourth")
    a = json.load(open(args))
    units, unmarked = a["units"], a["unmarked"]
    found = {r["label"]: r["result"] for r in results_of(journal)}
    expected = {f"notes4:{u['name']}:{k}" for u in units for k in range(len(u["readers"]))}
    require(set(found) == expected, f"no answer from {sorted(expected - set(found))}, or one from {sorted(set(found) - expected)}")
    groups, every_note = [], []
    for u in units:
        notes = []
        for k, reader in enumerate(u["readers"]):
            part = found[f"notes4:{u['name']}:{k}"]["siblings"]
            check_notes(f"{u['name']} (reader {k})", part, reader["siblings"])
            notes += part
        siblings = sorted(({f: n[f] for f in ("cluster", "index", "bears", "note")} for n in notes), key=lambda n: (n["cluster"], n["index"]))
        groups.append({"name": u["name"], "readers": len(u["readers"]), "siblings": siblings})
        every_note += siblings
    reading["notes4"] = {"date": date, "about": notes4_about(units, every_note, unmarked, date), "groups": groups, "unmarked": unmarked}
    json.dump(reading, open(reading_path, "w"), indent=1)
    print(len(every_note), "cluster rows noted;", Counter(n["bears"] for n in every_note), "; unmarked", len(unmarked))


def correct(reading_path, corrections, date):
    """The editor's words on hints and notes the follow-up's readers wrote, from a file kept in
    the repository, put in the reading under corrections; the page shows each in square brackets
    after what it is on, and stops where one lands on nothing."""
    reading = json.load(open(reading_path))
    require("corrections" not in reading, "the reading holds the editor's words already")
    C = json.load(open(corrections))
    for c in C["items"]:
        require(c.get("to") in CORRECTION_KEYS and sorted(c) == sorted(CORRECTION_KEYS[c["to"]]),
                f"an editor's word must give exactly {CORRECTION_KEYS.get(c.get('to'))}: {sorted(c)}")
        require(c["words"].isascii() and c["why"].isascii(), f"the editor's words on row {c['index']} are not ASCII")
    reading["corrections"] = {"date": date, "about": C["about"], "items": [{**c, "date": date} for c in C["items"]]}
    json.dump(reading, open(reading_path, "w"), indent=1)
    print(len(C["items"]), "editor's words")


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
    elif argv[0] == "second-inputs":
        second_inputs(*argv[1:])
    elif argv[0] == "second":
        second(*argv[1:])
    elif argv[0] == "notes3-inputs":
        notes3_inputs(*argv[1:])
    elif argv[0] == "notes3":
        notes3(*argv[1:])
    elif argv[0] == "notes4-inputs":
        notes4_inputs(*argv[1:])
    elif argv[0] == "notes4":
        notes4(*argv[1:])
    elif argv[0] == "correct":
        correct(*argv[1:])
    else:
        raise SystemExit(f"unknown mode {argv[0]!r}; inputs, record, regroup-inputs, regroup, second-inputs, second, notes3-inputs, notes3, "
                         "notes4-inputs, notes4 or correct")
