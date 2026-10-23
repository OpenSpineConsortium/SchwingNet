"""Render artifacts/_synthesis/contradictions.md from the merged sweeps and verdicts, with one
page per cluster under contradictions/. The main page says how the verdicts are read and how
far they held when they were read again, then lists what a planner must not take from one
artifact alone, the disagreements apart from the duplicated texts and unsourced claims, then
every number collision; a cluster's page holds every candidate. Each row gives the reader's
kind, whether a script found the reader's quotes and the skeptic's in the sources, and the
skeptic's verdict with the value the book should carry. Rows count from 0, as the record and
the skeptics' explanations do.

Usage: render_contradictions2.py MERGED NUMBERS INVENTORY DST DATE
  SYNTH_TEXT names the folder of extracted texts, SYNTH_SCHWINGNET and SYNTH_SYMPHONY the two
  clones. The run stops when one is missing, since without them every quote would read "no
  text" and the page would look clean."""
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from render_inventory import to_ascii, cell, short
from render_clusters import link, short_id
import verify_quotes as vq

STATUS = {"whole": "yes", "parts": "yes", "window": "partly", "spacing": "yes, spacing aside",
          "raw-whole": "yes, page data", "raw-parts": "yes, page data", "raw-window": "partly, page data",
          "raw-spacing": "yes, page data, spacing aside", "absent": "not found", "no-text": "no text",
          "no-quote": "no quote", "none-named": "-"}
PLACE = {"own": "found in its own artifact", "other": "found only in the other artifact", "absent": "not found",
         "empty": "none given", "elsewhere": "found only in {}, which the candidate does not name"}
NUMBER_KINDS = [("contradiction", "Same quantity, same scope, different values"),
                ("updated-later", "Revised later: the later artifact gives a new figure or date"),
                ("unit-or-scope-mismatch", "Same quantity, another unit, denominator, subset or interval"),
                ("probably-different-quantities", "Alike in name, probably not the same thing")]
CONFIRMED_C = ("confirmed", "superseded-by-later")
CONFIRMED_N = ("confirmed-contradiction", "updated-later")
AGREE_N = ("same-number-restated", "different-quantities", "scope-or-unit-differs")
# Kinds whose confirmed verdict is no disagreement: one claim carried twice, or a claim with no
# source; a planner must still not count it twice or take it as sourced.
NOT_DISAGREEMENTS = ("duplicate-text", "unsourced-shared-claim")
NUMBER_STRATUM = "Number collisions"
REVIEW = {"held": "review: held", "hint corrected": "review: held, hint corrected", "verdict overturned": "review: overturned, was {}",
          "read again": "read again, was {}"}
FOLLOWUP = {"held": "held", "hint corrected": "held, hint corrected", "verdict overturned": "overturned, was {}"}


def require(ok, why):
    if not ok:
        raise SystemExit("render refused: " + why)


def number_key(v):
    """A number collision's identity: its two artifacts and its whole quantity. The first 30
    characters alone gave two pairs of candidates one key, so one verdict of each pair was
    lost and the other shown on both."""
    return (tuple(sorted([v["artifact_a"], v["artifact_b"]])), v["quantity"].strip().lower())


def number_verdicts(N, extra):
    """Each number verdict by its collision's key. A later verdict replaces an earlier one only
    where it says it was reviewed, read again, read in a follow-up or read by a later run of the
    workflow; two on one key otherwise, or one that matches no collision, stop the run, since
    either would drop a verdict from the page without a word."""
    keys = {number_key(c) for c in N["candidates"]}
    by = {}
    for v in N["verdicts"]:
        require(number_key(v) not in by, f"two earlier number verdicts on {number_key(v)}")
        by[number_key(v)] = v
    seen = set()
    for v in extra:
        k = number_key(v)
        require(k not in seen, f"two number verdicts on {k}")
        require(k not in by or v.get("review") or v.get("followup") or v.get("delta"),
                f"a verdict on {k} replaces an earlier one without saying why")
        seen.add(k)
        by[k] = v
    stray = sorted(k for k in by if k not in keys)
    require(not stray, f"number verdicts that match no collision: {stray}")
    return by


def wilson(k, n, z=1.96):
    p, d = k / n, 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5 / d
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k, n):
    if not n:
        return "none drawn"
    lo, hi = wilson(k, n)
    return f"{k} of {n} held ({100 * k / n:.0f} %, Wilson 95 % interval {100 * lo:.0f} to {100 * hi:.0f} %)"


def was(n):
    return "was" if n == 1 else "were"


def small(n):
    return ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")[n] if n < 10 else str(n)


def listed(numbers):
    words = [str(n) for n in numbers]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def artifact(aid):
    return aid if aid and "/" in aid else None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("'", "")).strip("-")[:60]


def quote_status(text_dir, aid, quote):
    if not artifact(aid):
        return "-"
    return STATUS.get(vq.found(quote or "", vq.text_of(text_dir, aid), vq.raw_of(aid)), "?")


def unfound(text_dir, x):
    return "not found" in (quote_status(text_dir, x["artifact_a"], x.get("quote_a")),
                           quote_status(text_dir, x.get("artifact_b"), x.get("quote_b")))


def replaced(v):
    """Whether a ruling's words stand in place of the skeptic's, the review's, the follow-up's,
    a group judge's or, in a later run of the workflow, a judge's."""
    return (v.get("review") in ("hint corrected", "verdict overturned") or bool((v.get("followup") or {}).get("before"))
            or "judge" in ((v.get("delta") or {}).get("read") or []))


def skeptic_words(text_dir, a, b, v):
    """The words a verdict rests on, each with where the script found it, named as the
    ruling's where a ruling replaced the skeptic's."""
    if not v:
        return ""
    who = "ruling" if replaced(v) else "skeptic"
    words = []
    for side, own, other, q in (("A", a, b, v.get("quote_a")), ("B", b, a, v.get("quote_b"))):
        if (q or "").strip():
            where, _, third = vq.place(text_dir, q, artifact(own), artifact(other)).partition(":")
            words.append(f"{side} \"{short(q, 300)}\" ({PLACE[where].format(short_id(third))})")
    return f" The {who}'s words: " + "; ".join(words) + "." if words else f" The {who} quoted neither source."


ROUNDS = {(): "follow-up", ("regroup",): "follow-up, group re-rule", ("regroup2",): "follow-up, second group re-rule",
          ("regroup", "regroup2"): "follow-up, both group re-rules"}


def later_words(v, x):
    """What a later run of the workflow made of a row: a verdict read again because a page it
    rests on changed, with the verdict it replaced; a row found and read; or a row found that
    no skeptic has read yet. A judge's ruling is named, since it stands in the skeptic's place."""
    d, found = (v or {}).get("delta"), (x or {}).get("delta")
    if not d:
        return f"found on {found['date']}, not read yet" if found else ""
    judge = ", ruled by a judge" if "judge" in (d.get("read") or []) else ""
    if d.get("earlier"):
        return f"read again on {d['date']}, was {d['earlier'].get('verdict')}{judge}"
    if found and found.get("date") != d["date"]:
        return f"found on {found['date']}, read on {d['date']}{judge}"
    return f"found on {d['date']}{judge}"


def review_cell(v, x=None):
    """What the review, and then the follow-up, made of a verdict, each with the verdict it read;
    the follow-up's outcome names the group re-rules that changed the row, if any did. A verdict
    a later run gave stands in place of the one the review and the follow-up read, so its cell
    says what that run made of the row instead."""
    later = later_words(v, x)
    if later:
        return later
    v = v or {}
    words = []
    if v.get("review"):
        words.append(REVIEW[v["review"]].format((v.get("first") or {}).get("verdict")))
    if v.get("followup"):
        f = v["followup"]
        words.append(f"{ROUNDS[tuple(f.get('rounds', []))]}: " + FOLLOWUP[f["outcome"]].format((f.get("before") or {}).get("verdict")))
    return "; ".join(words)


def review_tag(v, x=None):
    r = review_cell(v, x)
    return f" ({r})" if r else ""


def where_of(x):
    """A verdict's place on the main page: a number collision by its row, a cluster's row by its page."""
    return (f"number collision {x['index']}" if x["stratum"] == "Number collisions"
            else f"[{cell(x['stratum'])}](contradictions/{slug(x['stratum'])}.md), row {x['index']}")


def link_or(aid, titles, up="../"):
    return link(aid, titles, up) if artifact(aid) else cell(aid or "-")


def pair(x):
    b = f" and {short_id(x['artifact_b'])}" if artifact(x.get("artifact_b")) else ""
    return f"{short_id(x['artifact_a'])}{b}"


FIGURE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
# The fourth rule's figures stand alone: not joined to a letter, a colon or another figure's
# point or comma, and not part of a date, so the 12 of T12, the 42 of 00:42 and the 10 of
# 2026-10-13 are no figures of a group.
STANDING = re.compile(r"(?<![\w.,:])\d+(?:,\d{3})*(?:\.\d+)?(?![\w:]|[.,]\d)")
DATE = re.compile(r"(?<!\d)(?:19|20)\d{2}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?(?!\d)")
RULES = ("narrow", "third", "fourth")


def figures(text):
    """The figures a text gives as written, numbers of two digits or more with their thousands
    commas and decimal point, so a figure rounded or written another way is another figure."""
    return {f for f in FIGURE.findall(text or "") if sum(ch.isdigit() for ch in f) >= 2}


def standing_figures(text):
    """The figures a text gives as written that stand alone, as figures() takes them, less
    any joined to a letter, a colon or a date."""
    return {f for f in STANDING.findall(DATE.sub(" ", text or "")) if sum(ch.isdigit() for ch in f) >= 2}


NOTE_ROUNDS = ("regroup2", "notes3", "notes4")


def final_groups(F):
    """The follow-up's groups as they stand: each group of the first re-rule, with its rows,
    the rows set beside them, its sources and its judge's finding taken from the second re-rule
    where that ruled the group again; the cluster rows its judge or readers read beside it in
    the second re-rule, under beside; and the notes on the cluster rows that give the group's
    figures, the second re-rule's, the third pass's and the fourth's, each with the round that
    gave it and the editor's words on it, if any, where any were given; a note on a row the
    fourth pass found the rule no longer marks is left out, and stays in the reading."""
    F = F or {}
    first = (F.get("regroup") or {}).get("groups", [])
    later = {k: {g["name"]: g for g in (F.get(k) or {}).get("groups", [])} for k in NOTE_ROUNDS}
    for k, groups in later.items():
        unknown = set(groups) - {g["name"] for g in first}
        require(not unknown, f"{k} names groups the first re-rule has not: {sorted(unknown)}")
    unmarked = {(u["group"], u["cluster"], u["index"]) for u in (F.get("notes4") or {}).get("unmarked", [])}
    editor = {(c["group"], c["cluster"], c["index"]): c for c in corrections_of(F) if c["to"] == "note"}
    out = []
    for g in first:
        s = later["regroup2"].get(g["name"], {})
        again = {k: s[k] for k in ("rows", "context", "extra", "note", "context_notes")} if s.get("rule") else {}
        given = [(k, later[k][g["name"]]["siblings"]) for k in NOTE_ROUNDS if "siblings" in later[k].get(g["name"], {})]
        notes = [{**n, "round": k, **editor_field(editor.get((g["name"], n["cluster"], n["index"])))} for k, ns in given for n in ns
                 if (g["name"], n["cluster"], n["index"]) not in unmarked] if given else None
        beside = [(n["cluster"], n["index"]) for n in s.get("siblings", [])] + [tuple(c) for c in s.get("cluster_context", [])]
        out.append({**g, **again, "second": bool(again), "notes": notes, "beside": beside})
    return out


def pages_of(x):
    return {a for a in (x["artifact_a"], x.get("artifact_b")) if artifact(a)}


def siblings_of(groups, M, N, rule="fourth"):
    """The cluster rows that give figures a group of the follow-up's re-rule read together, on
    pages read for the group: by the fourth rule, the page's, a row whose quotes, or whose
    verdict's explanation or hint, give one of the figures that the group's rows, or the rows
    set beside them, give in their values or quantities, written the same way and standing
    alone, two of them where each it shares is a whole number under 100, and one of whose pages
    is a page of those rows, a source the judge was given, or a page of a cluster row the judge
    or readers read beside the group in the second re-rule. The earlier rules are kept so that
    each round's input can be written again: the third, which wrote the third pass's, read the
    quotes alone, took any run of two digits or more as a figure and needed one; the narrow
    rule, which wrote the second re-rule's, read no page beside the group either and needed
    each of a row's pages read, or two of the figures and one of its pages. Returns, for each
    group that has any, the group and its rows as (cluster, row, verdict)."""
    require(rule in RULES, f"no marking rule {rule!r}; {RULES}")
    read = standing_figures if rule == "fourth" else figures
    clusters = {c["cluster"]: c for c in M["clusters"]}
    later = {(c["cluster"], i) for c in M["clusters"] for i, v in enumerate(c["verdicts"]) if (v or {}).get("delta")}
    found = []
    for g in groups:
        rows = [N["candidates"][r] for r in g["rows"] + g.get("context", [])]
        pages = set(g.get("extra", [])).union(*({x["artifact_a"], x["artifact_b"]} for x in rows))
        if rule != "narrow":
            pages = pages.union(*(pages_of(clusters[c]["candidates"][i]) for c, i in g.get("beside", [])))
        figs = set().union(*(read(x["value_a"]) | read(x["value_b"]) | read(x["quantity"]) for x in rows))
        mine = []
        for c in M["clusters"]:
            for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
                own = pages_of(x)
                if v and own & pages and enough(given_figures(x, v, rule, read) & figs, own <= pages, rule):
                    mine.append((c["cluster"], i, v))
        if mine:
            found.append(({**g, "later": later}, mine))
    return found


def given_figures(x, v, rule, read):
    """The figures a cluster row gives: in the reader's and the skeptic's quotes, and by the
    fourth rule in the skeptic's explanation and hint too, which can carry a group's figure
    that neither quote holds."""
    texts = [x.get("quote_a"), x.get("quote_b"), v.get("quote_a"), v.get("quote_b")]
    if rule == "fourth":
        texts += [v.get("explanation"), v.get("resolution_hint")]
    return set().union(*(read(t) for t in texts))


def enough(shared, every_page_read, rule):
    """Whether the figures a row shares with a group mark it, by the rule."""
    if rule == "narrow":
        return len(shared) >= (1 if every_page_read else 2)
    if rule == "fourth" and shared and all(f.isdigit() and int(f) < 100 for f in shared):
        return len(shared) >= 2
    return len(shared) >= 1


def corrections_of(F):
    """The editor's words on the follow-up's hints and notes, each naming what it is on."""
    return ((F or {}).get("corrections") or {}).get("items", [])


def editor_field(c):
    return {"editor": f"[Editor's {c['kind']}, {c['date']}: {c['words']}]"} if c else {}


def with_editor(text, editor):
    """A hint or a note with the editor's words after it, where there are any."""
    return f"{text} {editor}" if editor else text


def bears_words(bears):
    """How many notes agree with a finding, differ from it or are about another quantity, each
    verb agreeing with its count."""
    def count(n, one, many):
        return f"none {one}" if n == 0 else f"{n} {one if n == 1 else many}"
    return (f"{count(bears['agrees'], 'agrees with the finding', 'agree with the finding')}, "
            f"{count(bears['differs'], 'differs from it', 'differ from it')} and "
            f"{count(bears['other'], 'is about another quantity', 'are about another quantity')}")


def hint_editor(F, later=()):
    """The editor's words on number collision hints, by row, but for a row a later run of the
    workflow read again, whose hint is no longer the one the words were on."""
    return {c["index"]: editor_field(c)["editor"] for c in corrections_of(F)
            if c["to"] == "hint" and (NUMBER_STRATUM, c["index"]) not in later}


def check_corrections(F, N, nv, later=()):
    """Every editor's word lands: a hint's on a number collision with a verdict, a note's on a
    note the page shows; one that lands on nothing stops the run, since it would be lost. A word
    on a row a later run of the workflow read is left aside, since the hint or the note it was
    on is no longer the row's."""
    shown = {(g["name"], n["cluster"], n["index"]) for g in final_groups(F) for n in g["notes"] or []}
    for c in corrections_of(F):
        require(c["kind"] in ("correction", "note"), f"an editor's word is neither a correction nor a note: {c['kind']!r}")
        if (NUMBER_STRATUM if c["to"] == "hint" else c.get("cluster"), c["index"]) in later:
            continue
        if c["to"] == "hint":
            x = N["candidates"][c["index"]]
            require(number_key(x) in nv and nv[number_key(x)].get("resolution_hint"), f"the editor's {c['kind']} on collision {c['index']} lands on no hint")
        else:
            require(c["to"] == "note" and (c["group"], c["cluster"], c["index"]) in shown,
                    f"the editor's {c['kind']} on {c['cluster']} row {c['index']} lands on no note of group {c.get('group')!r}")


def group_siblings(M, N):
    return siblings_of(final_groups(M.get("followup")), M, N, "fourth")


def later_rows(M, N, nv):
    """The rows a later run of the workflow read again or found, as (stratum, row): their
    verdicts, where they have one, are not the ones the review, the follow-up and its notes
    read."""
    rows = {(c["cluster"], i) for c in M["clusters"] for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"]))
            if x.get("delta") or (v or {}).get("delta")}
    return rows | {(NUMBER_STRATUM, j) for j, x in enumerate(N["candidates"])
                   if x.get("delta") or (nv.get(number_key(x)) or {}).get("delta")}


BEARS = ("agrees", "differs", "other")


def notes_by_row(g, mine):
    """A group's notes on its marked rows, by (cluster, row), or None where no round gave any;
    the notes must name exactly the rows the rule marks, so a changed rule or record cannot
    leave a marked row unread or keep a note on a row no longer marked. A row whose verdict a
    later run of the workflow gave is left out on both sides: its note, if it had one, was on
    the verdict that run replaced."""
    if g.get("notes") is None:
        return None
    later = g.get("later", set())
    kept = [n for n in g["notes"] if (n["cluster"], n["index"]) not in later]
    notes = {(n["cluster"], n["index"]): n for n in kept}
    marked = {(c, i) for c, i, _ in mine} - later
    require(set(notes) == marked and len(notes) == len(kept), f"the notes on group {g['name']} name other rows than the rule marks")
    require(all(n["bears"] in BEARS for n in kept), f"a note on group {g['name']} is not one of {BEARS}")
    return notes


def marks_of(siblings):
    """Each marked cluster row's groups, by (cluster, row), each with its note where one was
    given and, for a row whose verdict a later run of the workflow gave, the day that run read
    it, in place of a note."""
    marks = {}
    for g, rows in siblings:
        notes = notes_by_row(g, rows)
        for c, i, v in rows:
            later = (v.get("delta") or {}).get("date")
            marks.setdefault((c, i), []).append((g["title"], None if later or notes is None else notes[(c, i)], later))
    return marks


BEARS_WORDS = {"agrees": "this row's instruction agrees with it", "differs": "this row's instruction differs from it",
               "other": "this row is about another quantity than the group's"}


def beside(entries, where):
    """The words that send a planner from a marked row to its groups' findings: how the note
    finds the row's instruction stands beside each finding, with the note's own words, where one
    was given, else that the finding is to be read beside it."""
    words = []
    for title, note, later in entries:
        if later:
            words.append(f" This row's verdict was read on {later}, after the follow-up's group judge on \"{title}\" ruled, so read its finding ({where}) beside it.")
        elif note is None:
            words.append(f" The follow-up's group judge on \"{title}\" read figures this row gives but not this row, so read its finding ({where}) beside it.")
        else:
            words.append(f" Set beside the follow-up's finding on \"{title}\" ({where}), {BEARS_WORDS[note['bears']]}: {with_editor(cell(note['note']), cell(note.get('editor', '')))}")
    return "".join(words)


def intro(N, nv, inv, date, followup, whole):
    regrouped = bool((followup or {}).get("regroup"))
    nums = sum(len(a.get("numbers") or []) for a in inv["artifacts"])
    besides = sum(1 for x in N["candidates"] if nv.get(number_key(x)) and x["kind"] not in ("contradiction", "updated-later"))
    parts = [int(m.replace(",", "")) for f in N.get("finders", []) for m in re.findall(r"Read all ([\d,]+) rows", f)]
    read = " and ".join(f"{n:,}" for n in parts)
    return ["# Contradictions and collisions\n",
            f"What the inventoried artifacts give differently, found and checked for the Artifact Textbook (issue #120, finished under #136), rendered on {date}. "
            "Readers went over the inventory's numbers table for every quantity two artifacts give with different values, and over each topic cluster's full records for disagreements, revised figures, stale statements, duplicated texts and shared unsourced claims. "
            f"The table holds {nums:,} numbers from {len(inv['artifacts'])} artifacts. The number readers' notes record reading two parts of it, {read} rows, {sum(parts):,} in all; "
            "the parts and the rule that split them are not kept in this repository, so which numbers went unread is not known here.\n",
            "A script then looked for every reader's quote in the artifact's extracted text and, failing that, in the page's own files. "
            "It ignores case and spacing, quotation marks, square and round brackets and the marks of tables and Markdown (the bar, asterisk, underscore, backtick, hash and greater-than sign), "
            "and reads typographic characters and a few accented letters as their plain ones; every other mark, braces and the less-than sign among them, must match. "
            "It matches around an ellipsis or an editor's words in square brackets, leaving unchecked any part shorter than 12 characters, "
            "and a quote longer than 48 characters that it finds neither whole nor in parts counts as partly found when one of its 48-character stretches, those that start at every eighth character, is in the text; "
            "the columns \"Reader's quote A\" and \"B\" say what it found. "
            "Then a skeptic read both sources of every cluster candidate, and of every number collision a reader classed as a contradiction or a later revision "
            f"and {besides} others #136's first run took, and gave a verdict with the exact words it rests on, copied from each source. "
            "Those words are on the cluster pages and under the number tables beside the reader's, with where the script found them. "
            "Last, a sample of the verdicts was read again by agents told to overturn them"
            + ((", and then every number collision on the confirmed list that the sample left out" if whole else ", and then, in a follow-up, more of them") if followup else "")
            + (", with the rows that read the same figures ruled again together" if regrouped else "")
            + " (How far the verdicts hold, below).\n",
            "Rows count from 0, as the record and the skeptics' explanations do, so \"candidate 4\" in an explanation is row 4 of its cluster's page. "
            "Nothing here is copied from memory. People other than published authors are named by role, and no e-mail address, phone number, or home or street address is reproduced; "
            "where a quote named a person or carried such a detail, an editor's words in square brackets stand in its place.\n"]


def definitions():
    return ["## How the verdicts are read\n",
            "For a cluster candidate:\n",
            "- confirmed: both sources say what the candidate says, which depends on the reader's kind. For a contradiction they disagree. "
            "For a duplicated text the same text or figure is carried by both, so it is one claim and not two confirmations. "
            "For a shared unsourced claim the claim is in each source and no source for it is given on those pages. "
            "For a stale statement a later source, or the artifact's own later section, shows it no longer holds.",
            "- superseded: one source is later, by its date or because it plainly follows the other, and revises the earlier one.",
            "- refuted: they agree once read in context, over a different scope, subset, unit, interval or date that the pages state, or a statement or quote is not in its source.",
            "- cannot tell: the texts do not settle it; the hint says what would.\n",
            "For a number collision:\n",
            "- confirmed-contradiction: the same quantity over the same scope, with different values.",
            "- updated-later: the later source, by its date or because it plainly follows the other, gives a new figure for the same quantity.",
            "- same-number-restated: the values agree once read, by rounding or another way of writing the figure.",
            "- scope-or-unit-differs: the same name over a different subset, denominator, unit, interval, version or date, as the pages state.",
            "- different-quantities: not the same thing at all.",
            "- cannot-tell: the texts do not settle it; the hint says what would.\n",
            "A blank verdict means no skeptic read that candidate, and the reader's kind is then all there is.\n"]


def column(x, v):
    """The summary column a cluster candidate's verdict counts under."""
    w = (v or {}).get("verdict", "not read")
    if w == "confirmed":
        return "duplicated or unsourced" if x["kind"] in NOT_DISAGREEMENTS else "disagreement or stale"
    return w


def summary(text_dir, clusters, N, nv):
    out = ["## Where it stands\n",
           "| Cluster | Candidates | Disagreements or stale, confirmed | Duplicated or unsourced, confirmed | Superseded | Refuted | Cannot tell | Not read | Reader's quote not found |",
           "|---|---|---|---|---|---|---|---|---|"]
    for c in clusters:
        if not c["swept"]:
            out.append(f"| {cell(c['cluster'])} | not swept | | | | | | | |")
            continue
        vc = Counter(column(x, v) for x, v in zip(c["candidates"], c["verdicts"]))
        nf = sum(1 for x in c["candidates"] if unfound(text_dir, x))
        out.append(f"| [{cell(c['cluster'])}](contradictions/{slug(c['cluster'])}.md) | {len(c['candidates'])} | {vc['disagreement or stale']} | {vc['duplicated or unsourced']} | "
                   f"{vc['superseded-by-later']} | {vc['refuted']} | {vc['cannot-tell']} | {vc['not read']} | {nf} |")
    nvc = Counter((nv.get(number_key(x)) or {}).get("verdict", "not read") for x in N["candidates"])
    nf = sum(1 for x in N["candidates"] if unfound(text_dir, x))
    out.append(f"| Number collisions (the numbers table) | {len(N['candidates'])} | {nvc['confirmed-contradiction']} | - | {nvc['updated-later']} | "
               f"{sum(nvc[w] for w in AGREE_N)} | {nvc['cannot-tell']} | {nvc['not read']} | {nf} |")
    swept = [c for c in clusters if c["swept"]]
    read = sum(1 for c in swept for v in c["verdicts"] if v)
    out.append("")
    out.append(f"{sum(len(c['candidates']) for c in swept)} cluster candidates in {len(swept)} of {len(clusters)} clusters, {read} read by a skeptic. "
               "For the numbers, Refuted counts the three verdicts that find no disagreement (same-number-restated, scope-or-unit-differs and different-quantities), most of which still say to carry both values, each with its scope; "
               "Not read counts the collisions a reader classed as another scope or another quantity, which no skeptic read, by design.\n")
    return out


def held(items):
    return sum(1 for x in items if x["outcome"] != "verdict overturned")


def side_of(verdict, confirmed):
    return "confirmed" if verdict in confirmed else "cannot-tell" if verdict == "cannot-tell" else "dismissed"


def drawn_side(x):
    """A drawn verdict's side; the review's files put cannot-tell with the dismissals."""
    return "confirmed" if x["side"] == "confirmed" else side_of(x["first"], ())


def unreviewed_by_stratum(M, N, nv, reviewed):
    """How many of the verdicts the review did not read each stratum holds, on each side. A
    verdict a later run of the workflow gave was read twice over already, by its skeptic and a
    re-checker told to overturn it, so it is not counted."""
    pop = {}
    for c in M["clusters"]:
        for i, v in enumerate(c["verdicts"]):
            if v and not v.get("delta") and (c["cluster"], i) not in reviewed:
                pop.setdefault(c["cluster"], Counter())[side_of(v["verdict"], CONFIRMED_C)] += 1
    for j, x in enumerate(N["candidates"]):
        v = nv.get(number_key(x))
        if v and not v.get("delta") and ("Number collisions", j) not in reviewed:
            pop.setdefault("Number collisions", Counter())[side_of(v["verdict"], CONFIRMED_N)] += 1
    return pop


def reads_every_confirmed_number(M, N, nv):
    """Whether a follow-up and the review between them read every number collision on the
    confirmed list, which the page then says in so many words."""
    F, R = M.get("followup"), M.get("review")
    if not (F and R):
        return False
    read = {(x["stratum"], x["index"]) for x in R["items"] + F["items"]}
    return not unreviewed_by_stratum(M, N, nv, read).get("Number collisions", Counter())["confirmed"]


def weighted(drawn, pop, side, by_stratum=True):
    """Expected verdicts that hold among one side's unreviewed ones: each stratum's held rate
    times the unreviewed verdicts it holds. Every stratum gave the review the same number of verdicts
    whatever its size, so the plain rate counts a small stratum as much as a large one. A
    stratum with none drawn on the side takes the side's pooled rate, and cannot-tell, drawn
    across all strata, is pooled."""
    pool = [x for x in drawn if drawn_side(x) == side]
    require(pool, f"no verdict drawn on the side {side}")
    pooled = held(pool) / len(pool)
    if not by_stratum:
        return {s: p[side] * pooled for s, p in pop.items()}
    expect = {}
    for s, p in pop.items():
        mine = [x for x in pool if x["stratum"] == s]
        expect[s] = p[side] * (held(mine) / len(mine) if mine else pooled)
    return expect


def weighted_words(drawn, pop, followup):
    """The weighted rates, and the stratum where the most unreviewed confirmed verdicts may be wrong.
    Verdicts the follow-up read are known, so they leave the unreviewed count."""
    count = {side: sum(p[side] for p in pop.values()) for side in ("confirmed", "dismissed", "cannot-tell")}
    on = weighted(drawn, pop, "confirmed")
    off = sum(weighted(drawn, pop, "dismissed").values()) + sum(weighted(drawn, pop, "cannot-tell", by_stratum=False).values())
    others = count["dismissed"] + count["cannot-tell"]
    worst = max(pop, key=lambda s: pop[s]["confirmed"] - on[s])
    mine = [x for x in drawn if x["stratum"] == worst and drawn_side(x) == "confirmed"]
    name = "the number collisions" if worst == "Number collisions" else cell(worst)
    why = (f"{len(mine) - held(mine)} of its {len(mine)} drawn {was(len(mine) - held(mine))} overturned" if mine
           else "none of its confirmed verdicts was drawn")
    return (f"These rates are unweighted: every stratum gave the same number of verdicts whatever its size. "
            f"Weighted by how many of the {count['confirmed'] + others} verdicts {'neither the review nor the follow-up' if followup else 'the review did not'} read each stratum holds, "
            f"about {100 * sum(on.values()) / count['confirmed']:.0f} % of the {count['confirmed']} on the confirmed list and {100 * off / others:.0f} % of the {others} others are expected to hold, "
            f"with wider intervals than the counts above, since a few drawn verdicts stand for each stratum. "
            f"Most of the unreviewed confirmed verdicts that may be wrong are in {name}: {why}, "
            f"and it holds {pop[worst]['confirmed']} of the {count['confirmed']}, so read those first.\n")


def review_section(M, N, nv):
    R = M.get("review")
    if not R:
        return []
    items = R["items"]
    drawn = [x for x in items if x["drawn"] == "random"]
    forced = [x for x in items if x["drawn"] != "random"]
    on_list = [x for x in drawn if x["side"] == "confirmed"]
    off_list = [x for x in drawn if x["side"] != "confirmed"]
    over = [x for x in items if x["outcome"] == "verdict overturned"]
    hinted = [x for x in items if x["outcome"] == "hint corrected"]
    F = M.get("followup")
    read = {(x["stratum"], x["index"]) for x in items + (F["items"] if F else [])}
    pop = unreviewed_by_stratum(M, N, nv, read)
    # The plain rates of the strata that still hold unread verdicts on the side, since a stratum
    # read whole no longer needs its draws to stand for it.
    rest_on = [x for x in on_list if pop.get(x["stratum"], Counter())["confirmed"]]
    rest_off = [x for x in off_list if pop.get(x["stratum"], Counter())[drawn_side(x)]]
    lo_on, hi_on = wilson(held(rest_on), len(rest_on))
    lo_off, hi_off = wilson(held(rest_off), len(rest_off))
    whole = reads_every_confirmed_number(M, N, nv)
    unread_on = ("The rest were not read again, but for the confirmed number collisions, which the follow-up below read whole" if whole
                 else "The rest were not read again, but for the verdicts the follow-up below read" if F else "The rest were not read again")
    out = ["## How far the verdicts hold\n", cell(R["about"]) + "\n",
           f"- Verdicts that put a candidate on the confirmed list, drawn at random: {rate(held(on_list), len(on_list))}.",
           f"- Verdicts that kept a candidate off it, drawn at random: {rate(held(off_list), len(off_list))}.",
           f"- Verdicts drawn because the script could not place one of their own quotes: {len(forced) - held(forced)} of {len(forced)} overturned.\n",
           f"In all {len(over)} verdicts were overturned and {len(hinted)} held with a corrected hint. Each now reads as the ruling has it, with the verdict it replaced in the Review column of its row. "
           f"{unread_on}: by the rates of the draws from the strata that still hold them ({held(rest_on)} of {len(rest_on)} and {held(rest_off)} of {len(rest_off)} held), between {100 * (1 - hi_on):.0f} and {100 * (1 - lo_on):.0f} % of the other confirmed verdicts may be wrong, "
           f"and between {100 * (1 - hi_off):.0f} and {100 * (1 - lo_off):.0f} % of the others, so read a row before relying on it.\n",
           weighted_words(drawn, pop, F),
           "The rows the review changed:\n"]
    for x in sorted(over + hinted, key=lambda x: (x["stratum"], x["index"])):
        what = f"{x['first']} became {x['final']}" if x["outcome"] == "verdict overturned" else f"{x['final']} held, with a corrected hint"
        out.append(f"- {where_of(x)}: {what}.")
    out.append("")
    again = []
    for j, x in enumerate(N["candidates"]):
        v = nv.get(number_key(x))
        if v and v.get("review") == "read again":
            again.append((j, v))
    if again:
        got = Counter(v["verdict"] for _, v in again)
        out.append(f"{len(again)} number verdicts of #136's first run were cannot-tell because their values were missing from the plain text, which cuts each line of a page's script data at 600 characters. "
                   "A skeptic read them again in the artifacts' own files: " + ", ".join(f"{n} {w}" for w, n in got.most_common())
                   + f" (collisions {', '.join(str(j) for j, _ in again)}). Each says read again in its Review column, with the verdict it replaced.\n")
    later = later_rows(M, N, nv)
    return out + followup_section(F, whole, group_siblings(M, N), bool(later)) + later_section(M, N, nv)


def by_cluster(keys):
    """Cluster rows as words with links, each cluster once with its rows."""
    by = {}
    for c, i in keys:
        by.setdefault(c, []).append(i)
    return "; ".join(f"[{cell(c)}](contradictions/{slug(c)}.md) {'row' if len(ix) == 1 else 'rows'} {listed(ix)}" for c, ix in by.items())


def capital(text):
    return text[:1].upper() + text[1:]


def round_counts(F):
    """How many cluster rows each round of notes set beside a finding, as the reading keeps them."""
    return {k: sum(len(g.get("siblings", [])) for g in ((F or {}).get(k) or {}).get("groups", [])) for k in NOTE_ROUNDS}


def history_words(F):
    """How the marked rows were set beside the findings, round by round, each round's rule with it."""
    n = round_counts(F)
    words = (f": in the second re-rule, by the group's judge or by a reader given the finding, the {n['regroup2']} the rule then marked, "
             "which counted no page read beside the group and needed each of a row's pages read, or two of the figures and one of those pages")
    if n["notes3"]:
        words += (f"; in a third pass, after a third review found rows that rule missed which plainly bear on a finding, by a reader for each group, "
                  f"the {n['notes3']} a wider rule added, which counted the pages read beside the group and needed one figure, "
                  "but read the quotes alone and took any two digits or more as a figure")
    unmarked = ((F or {}).get("notes4") or {}).get("unmarked", [])
    if n["notes4"] or unmarked:
        bears = Counter(u["bears"] for u in unmarked)
        how = ("all of them noted as about another quantity" if set(bears) == {"other"}
               else ", ".join(f"{k} {b}" for b, k in sorted(bears.items())))
        words += (f"; and in a fourth pass, after a fourth review found a confirmed row whose figures only its verdict's explanation and hint give, "
                  f"and rows marked on digits that are not a group's figures, by a reader for each group, the {n['notes4']} the rule's present form adds, "
                  f"which also unmarks {len(unmarked)} rows marked before, {how}, whose notes stay in the follow-up's reading")
    return words


def siblings_words(siblings, F=None):
    """The cluster rows that give a group's figures on pages read for it, by group. The cluster
    skeptics read them; where notes were given, each row's instruction was set beside its
    group's finding as it then stood, in the second re-rule the rows the narrow rule marked, in
    a third pass the rows a wider rule added and in a fourth the rows the rule's present form
    adds, and the rows whose instruction differs from the finding are listed with what their
    notes say, so a planner knows which to correct. A row of a group with no notes is to be read
    beside the finding."""
    rows = {(c, i): v for _, mine in siblings for c, i, v in mine}
    if not rows:
        return []
    reviewed = [where_of({"stratum": c, "index": i}) for (c, i), v in sorted(rows.items()) if v.get("review")]
    also = f", the review {small(len(reviewed))} of them too ({'; '.join(reviewed)})," if reviewed else ""
    noted = [(g, mine, notes_by_row(g, mine)) for g, mine in siblings]
    bears = Counter(n["bears"] for _, _, notes in noted if notes for n in notes.values())
    marks = sum(len(mine) for _, mine, _ in noted)
    plain = [f'"{g["title"]}"' for g, _, notes in noted if notes is None]
    rule = ("Rows of the cluster pages give these groups' figures too. "
            "A row is counted for a group when its quotes, or its verdict's explanation or hint, give one of the figures that the group's rows, "
            "or the rows set beside them, give in their values or quantities, written the same way and standing alone, not joined to a letter, a colon or a date, "
            "so that the 12 of T12 and the 42 of 00:42 count for nothing, and two of those figures where each it shares is a whole number under 100; "
            "and one of its pages was read for the group: a page of those rows, a source the group's judge was given, "
            "or a page of a cluster row its judge or readers read beside the group in the second re-rule. "
            + (f"{len(rows)} rows are, {marks} times in all, since a row may give the figures of two groups." if marks > len(rows) else f"{len(rows)} rows are.")
            + f" A cluster's skeptic read each{also} and no group's judge ruled any of them.")
    if bears:
        rule += (f" Each was set beside its group's finding as that then stood"
                 + (f" (the rows of {listed(plain)} excepted, which are to be read beside it)" if plain else "")
                 + history_words(F)
                 + f". Of the {len(rows)} marked now, {bears_words(bears)} than the group's. "
                 "Each is marked on its cluster's page, and in the confirmed list below where it is on it, with what its note says; "
                 "by group, with the rows whose instruction differs from the finding:\n")
    else:
        rule += " Each is marked on its cluster's page, and in the confirmed list below where it is on it, to be read beside its group's finding:\n"
    out = [rule]
    for g, mine, notes in noted:
        where = by_cluster((c, i) for c, i, _ in mine)
        order = [(c, i) for c, i, _ in mine]
        differ = sorted(((k, n) for k, n in (notes or {}).items() if n["bears"] == "differs"), key=lambda kn: order.index(kn[0]))
        count = "one differs" if len(differ) == 1 else f"{len(differ)} differ"
        out.append(f"- {cell(capital(g['title']))}: {where}." + (f" Of these, {count}:" if differ else ""))
        out += [f"  - {by_cluster([k])}: {with_editor(cell(n['note']), cell(n.get('editor', '')))}" for k, n in differ]
    out.append("")
    return out


def how_ruled(x):
    """Which group re-rules changed a row the follow-up changed."""
    rounds = [words for k, words in (("regroup", "the group re-rule"), ("regroup2", "the second group re-rule"))
              if (x.get(k) or {}).get("keep") is False]
    return f", in {' and again in '.join(rounds)}" if rounds else ""


def skeptic_sided(items):
    """The rows whose ruling sided with the skeptic's verdict in other words, which count as a
    corrected hint and read as the ruling has it, named since the page first counted them as
    held and kept the skeptic's words; rows a group re-rule changed afterwards are its."""
    rows = [x["index"] for x in items if x.get("sided_with") == "skeptic" and x["outcome"] == "hint corrected"
            and not any((x.get(k) or {}).get("keep") is False for k in ("regroup", "regroup2"))]
    if not rows:
        return ""
    one = len(rows) == 1
    return (f" A judge who sided with the skeptic's verdict but put the hint in other words leaves a corrected hint, and the row reads as the ruling has it: "
            f"number {'collision' if one else 'collisions'} {listed(rows)}, which the page counted as held, with the skeptic's words, "
            f"until apply_review.py was changed to put such a ruling's words in place, with the second group re-rule, which ruled neither {'row' if one else 'of them'}.")


def followup_section(F, whole, siblings, later=False):
    """The follow-up's reading: how many of the verdicts it read held, by the verdict each was,
    how many stay on the confirmed list, the groups ruled again together, the cluster rows that
    give their figures, and the rows it changed. It read every verdict of one kind rather than a
    sample, so its counts say how these rows stand, and its rates how far such verdicts held.
    whole says that no number collision on the confirmed list is left that neither it nor the
    review read; later says that a later run of the workflow read some rows too.
    """
    if not F:
        return []
    items = F["items"]
    over = [x for x in items if x["outcome"] == "verdict overturned"]
    hinted = [x for x in items if x["outcome"] == "hint corrected"]
    on = [x for x in items if x["final"] in (CONFIRMED_N if x["stratum"] == "Number collisions" else CONFIRMED_C)]
    G, G2, G3, G4 = F.get("regroup"), F.get("regroup2"), F.get("notes3"), F.get("notes4")
    out = ["### Every confirmed number collision, read again\n" if whole else "### A follow-up reading\n", cell(F["about"]) + "\n"]
    if G:
        out.append(cell(G["about"]) + "\n")
        if G2:
            out.append(cell(G2["about"]) + "\n")
        if G3:
            out.append(cell(G3["about"]) + "\n")
        if G4:
            out.append(cell(G4["about"]) + "\n")
        if F.get("corrections"):
            out.append(cell(F["corrections"]["about"]) + "\n")
        out.append("What each group's judge found" + (", the second judge's finding where the group was ruled a second time" if G2 else "") + ":\n")
        for g in final_groups(F):
            beside = "".join(f" Beside them, row {c['index']} {'agrees' if c['agrees'] else 'does not agree'}: {cell(c['note'])}"
                             for c in g.get("context_notes", []))
            again = ", ruled a second time" if g["second"] else ""
            out.append(f"- {cell(capital(g['title']))}, rows {listed(g['rows'])}{again}: {cell(g['note'])}{beside}")
        out.append("")
        out += siblings_words(siblings, F)
    for first in sorted({x["first"] for x in items}):
        mine = [x for x in items if x["first"] == first]
        out.append(f"- Verdicts that were {first}: {rate(held(mine), len(mine))}, "
                   f"{sum(1 for x in mine if x['outcome'] == 'hint corrected')} of them with a corrected hint.")
    out.append(f"- All {len(items)}: {rate(held(items), len(items))}.\n")
    out.append(f"The counts are exact for these rows, since every one was read; the intervals take the {len(items)} as a sample of the verdicts such skeptics give, "
               "so they say how well that rate is known, not how many of these rows may be wrong. "
               f"Of the {len(items)}, {len(on)} stay on the confirmed list and {len(items) - len(on)} left it.\n")
    out.append(f"In all {len(over)} {'verdict' if len(over) == 1 else 'verdicts'} {was(len(over))} overturned and {len(hinted)} held with a corrected hint. "
               + ("Each now reads as its ruling has it, or its group's judge where a group re-rule ruled it again, the second judge over the first, "
                  if G2 else "Each now reads as its ruling has it, or its group's judge where the group re-rule ruled it again, "
                  if G else "Each now reads as its ruling has it, ")
               + "and its Review column gives the follow-up's outcome with the verdict it replaced."
               + skeptic_sided(items)
               + (" With these, every number collision on the confirmed list has been read by a skeptic and then again, by the review or the follow-up"
                  + (" or, since, by a later run's re-checker." if later else ".") if whole else "")
               + "\n")
    if over or hinted:
        out.append("The rows the follow-up changed:\n")
        for x in sorted(over + hinted, key=lambda x: (x["stratum"], x["index"])):
            what = f"{x['first']} became {x['final']}" if x["outcome"] == "verdict overturned" else f"{x['final']} held, with a corrected hint"
            out.append(f"- {where_of(x)}: {what}{how_ruled(x)}.")
        out.append("")
    return out


def later_section(M, N, nv):
    """What the runs of .github/workflows/synthesis.yml read after the follow-up: the verdicts
    read again because a page they rest on changed, with how many kept the verdict they had; the
    rows its finders and its concept checks found and read; how many of these a judge ruled; and
    the rows found that wait for a verdict."""
    rows = [(c["cluster"], i, x, v) for c in M["clusters"] for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"]))]
    rows += [(NUMBER_STRATUM, j, x, nv.get(number_key(x))) for j, x in enumerate(N["candidates"])]
    again = [(s, i, v) for s, i, x, v in rows if (v or {}).get("delta", {}).get("earlier")]
    found = [(s, i, v) for s, i, x, v in rows if (v or {}).get("delta") and not v["delta"].get("earlier")]
    waiting = [(s, i) for s, i, x, v in rows if x.get("delta") and not v]
    if not (again or found or waiting):
        return []
    dates = sorted({v["delta"]["date"] for _, _, v in again + found} | {x["delta"]["date"] for s, i, x, v in rows if x.get("delta")})
    when = f"on {dates[0]}" if len(dates) == 1 else f"from {dates[0]} to {dates[-1]}"
    kept = sum(1 for _, _, v in again if v["verdict"] == v["delta"]["earlier"].get("verdict"))
    judged = sum(1 for _, _, v in again + found if "judge" in (v["delta"].get("read") or []))
    out = ["### Read by the workflow since\n",
           f"After the follow-up, the runs of .github/workflows/synthesis.yml {when} read {len(again)} {'verdict' if len(again) == 1 else 'verdicts'} again "
           f"because a page {'it rests' if len(again) == 1 else 'each rests'} on had changed, {kept} of them keeping the verdict {'it' if len(again) == 1 else 'they'} had, "
           f"and read {len(found)} {'row' if len(found) == 1 else 'rows'} that their finders or the concept checks found. "
           "Each was read by a skeptic and then by a re-checker told to overturn the skeptic's verdict and its hint, "
           f"and {judged} of the {len(again) + len(found)}, where the two disagreed, by a judge who read both sources and ruled. "
           f"{len(waiting)} {'row' if len(waiting) == 1 else 'rows'} found {'waits' if len(waiting) == 1 else 'wait'} for a verdict, which the next run reads. "
           "Each such row's Review column says when it was read and, for a verdict read again, what it was before.\n"]
    changed = [(s, i, v) for s, i, v in again if v["verdict"] != v["delta"]["earlier"].get("verdict")]
    if changed:
        out.append("The verdicts read again that changed:\n")
        out += [f"- {where_of({'stratum': s, 'index': i})}: {v['delta']['earlier'].get('verdict')} became {v['verdict']}." for s, i, v in changed]
        out.append("")
    return out


def confirmed_section(text_dir, clusters, N, nv, followup, marks, later=()):
    edits = hint_editor(followup, later)
    out = ["## Confirmed: what a planner must not take from one artifact alone\n",
           "Every candidate a skeptic confirmed or found revised, by cluster. Disagreements, revisions and stale statements come first; "
           "duplicated texts and shared unsourced claims follow, confirmed in the senses above, which are not disagreements: a duplicated text is one claim and not two confirmations, and a shared unsourced claim has no source on either page. "
           "Each item gives its row on the cluster's page, its kind, its verdict and "
           + ("the outcome of the review or the follow-up where either read it" if followup else "the review's outcome where the review read it")
           + ", the two artifacts, and the value or statement the skeptic says the book should carry. "
           "The whole candidate, with both readings and both sets of quotes, is on the cluster's page.\n"]
    for c in clusters:
        if not c["swept"]:
            continue
        rows = [(i, x, v) for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])) if v and v["verdict"] in CONFIRMED_C]
        if not rows:
            continue
        out.append(f"### [{cell(c['cluster'])}](contradictions/{slug(c['cluster'])}.md)\n")
        plain = [r for r in rows if r[2]["verdict"] == "confirmed" and r[1]["kind"] in NOT_DISAGREEMENTS]
        groups = (("Disagreements, revisions and stale statements:", [r for r in rows if r not in plain]),
                  ("Duplicated texts and shared unsourced claims:", plain))
        for title, group in groups:
            if not group:
                continue
            out.append(title + "\n")
            for i, x, v in group:
                tag = f"; {review_cell(v, x)}" if review_cell(v, x) else ""
                out.append(f"- Row {i}, {x['kind']}, {v['verdict']} ({pair(x)}{tag}): {cell(x['topic'])}. {cell(v.get('resolution_hint'))}"
                           + beside(marks.get((c["cluster"], i), []), "How far the verdicts hold, above"))
            out.append("")
    rows = [(j, x, nv[number_key(x)]) for j, x in enumerate(N["candidates"])
            if number_key(x) in nv and nv[number_key(x)]["verdict"] in CONFIRMED_N]
    if rows:
        out.append("### Numbers\n")
        for j, x, v in rows:
            out.append(f"- Collision {j}, {v['verdict']}{review_tag(v, x)}, {cell(x['quantity'])}: {short_id(x['artifact_a'])} gives {cell(x['value_a'])}, "
                       f"{short_id(x['artifact_b'])} gives {cell(x['value_b'])}. {with_editor(cell(v.get('resolution_hint') or v.get('explanation')), cell(edits.get(j, '')))}")
        out.append("")
    return out


def numbers_section(text_dir, N, nv, titles, edits):
    out = ["## Number collisions\n",
           f"{len(N['candidates'])} candidates from the numbers table, by the reader's kind, each under its number in the record.\n"]
    for kind, title in NUMBER_KINDS:
        rows = [(j, x) for j, x in enumerate(N["candidates"]) if x["kind"] == kind]
        out.append(f"### {title} ({len(rows)})\n")
        out.append("| # | Quantity | A | A gives | B | B gives | Reader's quote A | Reader's quote B | Verdict | Review | Why |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for j, x in rows:
            v = nv.get(number_key(x))
            why = with_editor(short(v.get("resolution_hint") or v.get("explanation"), 260), cell(edits.get(j, ""))) if v else short(x["why"], 200)
            out.append(f"| {j} | {short(x['quantity'], 110)} | {link(x['artifact_a'], titles)} | {short(x['value_a'], 70)} | {link(x['artifact_b'], titles)} | {short(x['value_b'], 70)} | "
                       f"{quote_status(text_dir, x['artifact_a'], x['quote_a'])} | {quote_status(text_dir, x['artifact_b'], x['quote_b'])} | {(v or {}).get('verdict', '')} | {review_cell(v, x)} | {why} |")
        out.append("")
        out.append("The quotes, by collision:\n")
        for j, x in rows:
            v = nv.get(number_key(x))
            out.append(f"- {j}. The reader's: A, {short_id(x['artifact_a'])}: \"{short(x['quote_a'], 300)}\"; B, {short_id(x['artifact_b'])}: \"{short(x['quote_b'], 300)}\"."
                       + skeptic_words(text_dir, x["artifact_a"], x["artifact_b"], v))
        out.append("")
    return out


def marked_note(marked, noted):
    """What a cluster page says of its rows that give a regrouped figure: that each was set
    beside its group's finding and says how it bears on it and why, where noted, else that each
    says so and the main page gives the finding; noted lists the rows each of whose groups gave
    a note, and where only some were noted the two are named apart."""
    if not marked:
        return ""
    one = len(marked) == 1
    gives = (f"{'Row' if one else 'Rows'} {listed(marked)} {'gives' if one else 'give'} figures that a judge of the follow-up's group re-rule "
             "read in other rows, by the rule the main page gives")
    unnoted = [i for i in marked if i not in noted]
    if noted and unnoted:
        def rows(ix):
            return f"{'row' if len(ix) == 1 else 'rows'} {listed(ix)}"
        return (f"{gives}. Of these, {rows(noted)} {'was' if len(noted) == 1 else 'were each'} set beside that group's finding, and below "
                f"{'it says' if len(noted) == 1 else 'each says'} whether its instruction agrees with the finding, differs from it or is about another quantity, "
                f"with the note that says why; {rows(unnoted)} {'was' if len(unnoted) == 1 else 'were'} not, and {'says' if len(unnoted) == 1 else 'say'} so below. "
                "The main page gives the finding and how the rows were read.\n")
    if noted:
        return (f"{gives}. {'It was' if one else 'Each was'} set beside that group's finding; below, {'it says' if one else 'each says'} whether "
                "its instruction agrees with the finding, differs from it or is about another quantity, with the note that says why, "
                "and the main page gives the finding and how the rows were read.\n")
    return f"{gives}, and {'was' if one else 'were'} not read with them; {'it says' if one else 'each says'} so below, and the main page gives what the judge found.\n"


def cluster_page(text_dir, c, titles, date, marks):
    up = "../../"
    marked = [i for i in range(len(c["candidates"])) if (c["cluster"], i) in marks]
    note = marked_note(marked, [i for i in marked if all(n is not None for _, n, _ in marks[(c["cluster"], i)])])
    out = [f"# Contradictions: {c['cluster']}\n",
           f"Part of [the contradictions of the artifacts](../contradictions.md), rendered on {date}. Rows count from 0, as the record and the skeptics' explanations do. "
           "A blank verdict means no skeptic read that candidate. The Review column says whether the verdict was read again and what it was before; the main page says how the review was run.\n"
           + (f"\n{note}" if note else ""),
           f"{len(c['candidates'])} candidates.\n",
           "| # | Kind | Topic | A | B | Reader's quote A | Reader's quote B | Verdict | Review | Explanation |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
        out.append(f"| {i} | {x['kind']} | {short(x['topic'], 110)} | {link_or(x['artifact_a'], titles, up)} | {link_or(x.get('artifact_b'), titles, up)} | "
                   f"{quote_status(text_dir, x['artifact_a'], x.get('quote_a'))} | {quote_status(text_dir, x.get('artifact_b'), x.get('quote_b'))} | "
                   f"{(v or {}).get('verdict', '')} | {review_cell(v, x)} | {short((v or {}).get('explanation') or x.get('why_it_matters'), 260)} |")
    out.append("")
    out.append("What each artifact says, and the words each verdict rests on, in the same order:\n")
    for i, (x, v) in enumerate(zip(c["candidates"], c["verdicts"])):
        b = (f" B, {short_id(x['artifact_b'])}: {short(x.get('statement_b'), 240)} (\"{short(x.get('quote_b'), 240)}\")."
             if artifact(x.get("artifact_b")) else "")
        carry = f" Carry: {short(v.get('resolution_hint'), 300)}" if v and v.get("resolution_hint") else ""
        out.append(f"- Row {i}. A, {short_id(x['artifact_a'])}: {short(x['statement_a'], 240)} (\"{short(x['quote_a'], 240)}\").{b}"
                   + skeptic_words(text_dir, x["artifact_a"], x.get("artifact_b"), v) + carry
                   + beside(marks.get((c["cluster"], i), []), "the main page, How far the verdicts hold"))
    out.append("")
    if c.get("canonical_check"):
        out.append("The clustering's superseded and duplicate relations, as the reader checked them:\n")
        for y in c["canonical_check"]:
            out.append(f"- {short_id(y['id'])} {y['relation']} {short_id(y['other'])}: {'agrees' if y['agree'] else 'disagrees'}. {cell(y['why'])}")
        out.append("")
    out.append(f"Unsourced: {cell(c['unsourced_summary'])}\n")
    out.append(f"Stale: {cell(c['stale_summary'])}\n")
    if c.get("notes"):
        out.append(f"Notes: {cell(c['notes'])}\n")
    return out


def main(merged, numbers, inventory, dst, date):
    text_dir = vq.required_dir("SYNTH_TEXT")
    vq.repos()
    M, N, inv = json.load(open(merged)), json.load(open(numbers)), json.load(open(inventory))
    titles = {f"{r['repo']}/{r['folder']}": r["title"] for r in inv["artifacts"]}
    nv = number_verdicts(N, M.get("numbers_extra", []))
    clusters = M["clusters"]
    marks = marks_of(group_siblings(M, N))
    later = later_rows(M, N, nv)
    check_corrections(M.get("followup"), N, nv, later)
    page = (intro(N, nv, inv, date, M.get("followup"), reads_every_confirmed_number(M, N, nv)) + definitions() + summary(text_dir, clusters, N, nv) + review_section(M, N, nv)
            + confirmed_section(text_dir, clusters, N, nv, M.get("followup"), marks, later)
            + numbers_section(text_dir, N, nv, titles, hint_editor(M.get("followup"), later))
            + ["## Cluster by cluster\n",
               "Each swept cluster has a page of its own under contradictions/, linked from the table above: every candidate with its kind, both artifacts, whether a script found the reader's quotes, the verdict, the review's outcome and the skeptic's explanation, "
               "then what each artifact says with the words the verdict rests on, the clustering's superseded relations as the reader checked them, and what the cluster asserts without a source or holds as dated.\n"])
    sub = os.path.join(os.path.dirname(dst), "contradictions")
    os.makedirs(sub, exist_ok=True)
    for c in clusters:
        if c["swept"]:
            open(os.path.join(sub, slug(c["cluster"]) + ".md"), "w", newline="\n").write(to_ascii("\n".join(cluster_page(text_dir, c, titles, date, marks))))
    open(dst, "w", newline="\n").write(to_ascii("\n".join(page)))


if __name__ == "__main__":
    main(*sys.argv[1:6])
