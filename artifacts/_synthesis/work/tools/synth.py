"""Keep the synthesis of the artifacts current as artifacts, notes and dataset records change.

Usage, from anywhere, with SYNTH_SYMPHONY naming a checkout of symphony-template:
  synth.py status [--json PATH]   what changed since the stamp, and the reads it needs
  synth.py concepts               the concept ledger and its checks: out/concepts.json, ../concepts.md
  synth.py report PATH [--status F]
                                  the same as Markdown, for the issue labelled synthesis, from
                                  the JSON status --json wrote where F names it
  synth.py plan DIR               the reads' inputs and args.json, for .github/workflows/synthesis.yml
  synth.py join PLAN ANSWERS BATCHES [SUMMARY]
                                  the reads' answers into the records, and the inventory, cluster,
                                  contradictions and concept pages rendered again from them (the
                                  table of contents is written by hand and is not)
  synth.py stamp [--at REPO=REF]  record what the records were read from, and what is already
                                  known; --at names the commit a checkout is at, for the record
  synth.py stamp --checks         take every concept check the texts give now as seen
  synth.py rekey BASE             carry the stamp's word over a change that renames the concept
                                  checks' keys and not what they check, as one to what the scrub
                                  takes out does; BASE is a checkout of main, and this checkout
                                  is up to date with it and changes none of the texts and none
                                  of the records the concepts are made from
--without symphony-template lets status and report check this repository alone, where no
checkout of the other can be made (the workflow's App token is missing), keeping the stamp's
word for it and checking no concept; concepts, plan, join, stamp and rekey refuse it, since they
write what every text gives.

The SchwingNet checkout is the one this file is in. SYNTH_TEXT, if set, names where the
artifacts' texts are extracted; else a fresh temporary folder is used, so no run reads
another's texts. The state (work/out/state.json) says, for every artifact, the git tree its
inventory record was read from; a run compares today's trees with it (synth_state.py),
checks every verdict's and record's quotes against today's texts, checks every text against
the concept ledger (synth_concepts.py), and lists what a change needs read again
(synth_reads.py). status, concepts, report and stamp run anywhere, with no Claude. plan
writes the inputs of the Claude reads and join takes their answers: .github/workflows/
synthesis.yml runs both, the reads between them on this repository's Claude token, at most
the runs a day its variable allows, and adds what the join wrote to the one open synthesis
pull request, or opens it.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_verdict_quotes import rows_of  # noqa: E402
WORK = HERE.parent
SYNTH = WORK.parent
ROOT = SYNTH.parent.parent
OUT = WORK / "out"
STATE = OUT / "state.json"
LEDGER = OUT / "concepts.json"
PAGE = SYNTH / "concepts.md"
ALIASES = WORK / "aliases.json"
REPORT_ROWS = 50


def today():
    return os.environ.get("SYNTH_DATE") or datetime.date.today().isoformat()


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scrubbed(value):
    """The value with what the folder's rule keeps out of its records and pages, a login, the
    owner's first name, a form's link and the like, replaced by an editor's words in square
    brackets (redact.py), so what a run writes holds none of them even where an artifact or a
    dataset record prints one; the quote checks match around those words."""
    import redact
    return redact.walk(value, Counter()) if not isinstance(value, str) else redact.scrub(value, Counter())


def save(path, data):
    """A record in the layout the first reading wrote them in, ASCII with escapes and an indent
    of one, and with a final newline only where the file had one, so a run's diff holds only
    what it changed."""
    end = "\n"
    if os.path.exists(path):
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell():
                f.seek(-1, os.SEEK_END)
                end = "\n" if f.read(1) == b"\n" else ""
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(json.dumps(data, indent=1, ensure_ascii=True) + end)


class Run:
    """One run's checkouts, texts and records."""

    def __init__(self, without=()):
        import extract
        self.without = set(without)
        symphony = os.environ.get("SYNTH_SYMPHONY", "")
        if "symphony-template" in self.without:
            symphony = tempfile.mkdtemp(prefix="synth-empty-")
            os.makedirs(os.path.join(symphony, "artifacts"))
        elif not symphony or not os.path.isdir(os.path.join(symphony, "artifacts")):
            raise SystemExit(f"SYNTH_SYMPHONY must name a checkout of symphony-template holding artifacts/; it is {symphony!r}")
        # Whole paths, since the processes a run starts read them from the environment and may
        # start in another folder, as rekey's base does.
        symphony = os.path.abspath(symphony)
        self.clones = {"SchwingNet": str(ROOT), "symphony-template": symphony}
        self.text_dir = os.path.abspath(os.environ.get("SYNTH_TEXT") or tempfile.mkdtemp(prefix="synth-text-"))
        for repo, clone in self.clones.items():
            if repo not in self.without:
                self.extract(extract, repo, clone)
        os.makedirs(os.path.join(self.text_dir, "symphony-template"), exist_ok=True)
        os.environ.update(SYNTH_TEXT=self.text_dir, SYNTH_SCHWINGNET=self.clones["SchwingNet"], SYNTH_SYMPHONY=symphony)
        self.inventory = load(SYNTH / "inventory.json")
        self.clustering = load(OUT / "clustering.json")
        self.M = load(OUT / "contradictions-merged.json")
        self.N = load(OUT / "numbers-partial.json")

    def extract(self, extract, repo, clone):
        dst = Path(self.text_dir) / repo
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        root = Path(clone) / "artifacts"
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
            extract.extract_folder(folder, dst / (folder.name + ".txt"))

    def skipped(self, aid):
        return bool(aid) and aid.split("/", 1)[0] in self.without

    def trees(self, state, at=None):
        import synth_state as st
        out = {}
        for repo, clone in self.clones.items():
            if repo in self.without:
                out.update({a: t for a, t in state.get("artifacts", {}).items() if a.startswith(repo + "/")})
            else:
                out.update(st.folder_trees(clone, repo, (at or {}).get(repo, "HEAD")))
        return out

    def records(self):
        return {f"{r['repo']}/{r['folder']}": r for r in self.inventory["artifacts"]}


def concepts_now(run):
    import synth_concepts as sc
    overrides = sc.load_overrides(ALIASES)
    ledger = sc.build(str(ROOT), run.text_dir, run.inventory, run.M, run.N, overrides, today())
    if run.without:
        ledger["checks"] = [c for c in ledger["checks"] if not run.skipped(c["source"])]
        ledger["without"] = sorted(run.without)
    return ledger


def status(run, state):
    """What changed since the stamp, as a dict the report and plan read. Without one
    repository's checkout no concept is checked, since a check weighs each word by how rare it
    is across every text, and fewer texts would give other checks than the stamp saw."""
    import synth_state as st
    trees = run.trees(state)
    datasets = st.dataset_hashes(ROOT)
    records = run.records()
    d = st.delta(state, trees, datasets, recorded={a for a in records if not run.skipped(a)})
    changes = [{"id": a, "new": True, "hunks": None} for a in d["new"]]
    for aid in d["changed"]:
        repo, folder = aid.split("/", 1)
        try:
            old = st.text_at(run.clones[repo], state["artifacts"][aid], folder)
            with open(f"{run.text_dir}/{aid}.txt", encoding="utf-8") as f:
                new = f.read()
            hunks = st.changed_lines(old, new)
        except subprocess.CalledProcessError:  # an old tree this clone lacks: the reader takes the page whole
            hunks = None
        changes.append({"id": aid, "new": False, "hunks": hunks,
                        "added": sum(len(h["added"]) for h in hunks or []), "removed": sum(len(h["removed"]) for h in hunks or [])})
    places = st.verdict_places(run.M, run.N, run.text_dir)
    rows = {f"{s}|{i}": (a, b) for s, i, a, b, _v in rows_of(run.M, run.N)}
    places = {k: p for k, p in places.items() if not any(run.skipped(x) for x in rows.get(k, ()))}
    stale, resolved = st.stale_verdicts(state, places)
    import synth_reads as sr
    unread = sr.unread_rows(run.M, run.N)
    absent = st.absent_inventory_quotes({"artifacts": [r for a, r in records.items() if not run.skipped(a)]}, run.text_dir)
    lost = st.newly_absent(state, absent)
    ledger = concepts_now(run) if not run.without else {"checks": [], "figures": [], "datasets": []}
    seen = state.get("checks", {})
    covered = covered_checks(ledger, run.N)
    fresh = [c for c in ledger["checks"] if c["key"] not in seen and c["key"] not in covered]
    now_keys = {c["key"] for c in ledger["checks"]}
    gone = [k for k in seen if k not in now_keys] if not run.without else []
    return {"date": today(), "stamped": state.get("stamped"), "delta": d, "changes": changes, "stale": stale,
            "resolved": resolved, "unread": unread, "lost_quotes": lost, "new_checks": fresh, "gone_checks": len(gone),
            "ledger": ledger, "without": sorted(run.without),
            "heads": {repo: head(clone) for repo, clone in run.clones.items() if repo not in run.without}}


def covered_checks(ledger, N):
    """The keys of the checks a row already answers: a figure check whose verdict would be a
    number row the numbers table holds, which a read would only find there again."""
    import synth_reads as sr
    from render_contradictions2 import number_key
    rows = {number_key(x) for x in N["candidates"]}
    by_id = {c["id"]: c for c in ledger["figures"]}
    return {c["key"] for c in ledger["checks"] if c["kind"] == "figure" and c["outcome"] in ("superseded", "open")
            and c["concept"] in by_id and sr.concept_row_key(c, by_id[c["concept"]]) in rows}


def head(clone):
    import synth_state as st
    try:
        return st.git(clone, "rev-parse", "HEAD").strip()
    except Exception:
        return None


def reads_waiting(s):
    """The reads the change needs: an inventory read and a finder per new or changed artifact,
    a verdict read for each stale verdict, each new concept check of an artifact that gives a
    settled figure as superseded or open, and each row a finder found whose verdict did not
    come back."""
    artifacts = len(s["changes"])
    concept = [c for c in s["new_checks"] if c["kind"] == "figure" and c["outcome"] in ("superseded", "open")
               and not c["source"].startswith(("notes:", "registry:"))]
    verdicts = len(s["stale"]) + len(concept) + len(s.get("unread", []))
    return {"inventory": artifacts, "finders": artifacts, "verdicts": verdicts, "concept_items": concept}


def code(text, table=True):
    """Words from a text as a code span, which GitHub draws as they are: a mention in them
    notifies nobody, and a tag or an image in them draws nothing. In a table a pipe is escaped,
    since GitHub splits a table's cells before it reads their spans."""
    text = " ".join((text or "").split())
    if table:
        text = text.replace("|", "\\|")
    fence = "`" * (max((len(m) for m in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if not text or text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def report(s):
    """The issue's body: what the run found that the stamp had not seen, and the reads waiting;
    its marker, a digest of the body as it is written, scrubbed, less the run's date and heads,
    so that a run that would write the same leaves the issue as it is and any other rewrites it,
    the report's own words included, and so that the marker gives away nothing the scrub took
    out; and whether it finds anything at all, since an issue that says nothing changed is
    opened for nobody."""
    from render_inventory import cell, to_ascii
    w = reads_waiting(s)
    total = w["inventory"] + w["finders"] + w["verdicts"]
    when = f"{s['date']} at " + ", ".join(f"{r} {h[:7]}" for r, h in s["heads"].items() if h)
    out = ["This issue is kept by .github/workflows/synthesis.yml, which looks daily at 06:41 UTC, on Run workflow, and on a"
           " push to main that changes an artifact, a research note or a dataset record where a person or an App made the push;"
           " a merge GitHub's auto-merge makes starts no workflow, so the daily run takes what it landed. It lists what the"
           " texts say now that the"
           f" stamp of {s['stamped']} had not seen; artifacts/_synthesis/concepts.md and work/RESUME.md say how each check is made.\n",
           f"Written by the run on {when}; a later run that would write the same leaves this issue as it is."
           + (f" Not checked: {', '.join(s['without'])}, whose checkout the run could not make." if s["without"] else "") + "\n",
           f"## Reads waiting: {total}\n"]
    if total:
        out.append(f"- {w['inventory']} inventory read(s) and {w['finders']} finder(s), one each per new or changed artifact;"
                   f" {w['verdicts']} verdict read(s), each a skeptic, a re-checker and a judge on a dispute, for the stale"
                   " verdicts, the concept checks below and the rows a finder found that have no verdict yet"
                   f" ({len(s.get('unread', []))}), and more for whatever the finders find.")
        out.append("- They run in GitHub Actions on this repository's Claude token, a few artifacts and verdict items a run and at most"
                   " the runs a day the variable SYNTHESIS_READS_PER_DAY allows (10 unless it says otherwise, 50 at most); a run"
                   " whose sessions bring something back adds it to the one open synthesis pull request, or opens it,"
                   " and what a run leaves waits for the next. The variable SYNTHESIS_READS set to off stops them;"
                   " Run workflow on the Synthesis workflow starts one now.\n")
    else:
        out.append("None.\n")
    out.append("## Artifacts\n")
    d = s["delta"]
    out.append(f"- New: {', '.join(d['new']) or 'none'}.")
    out.append("- Changed since their record was read: " + (", ".join(
        f"{c['id']} ({c['added']} lines added, {c['removed']} removed)" if c["hunks"] is not None else f"{c['id']} (read whole)"
        for c in s["changes"] if not c["new"]) or "none") + ".")
    out.append(f"- Gone: {', '.join(d['gone']) or 'none'}." + (
        " A record stands for each of these whose folder is gone; a person takes each one's record out of inventory.json, and"
        " its name out of clustering.json's members, by pull request, and it is listed no more." if d["gone"] else "") + "\n")
    out.append("## Dataset records\n")
    out.append(f"- New: {', '.join(d['datasets_new']) or 'none'}; changed: {', '.join(d['datasets_changed']) or 'none'};"
               f" gone: {', '.join(d['datasets_gone']) or 'none'}.\n")
    out.append("## Verdicts whose quotes moved\n")
    if s["stale"] or s["resolved"]:
        out.append("| Row | Quotes found at the stamp | Found now |\n|---|---|---|")
        for r in s["stale"][:REPORT_ROWS]:
            out.append(f"| {cell(r['row'])} | {', '.join(r['was'])} | {', '.join(r['now'])} |")
        if s["resolved"]:
            out.append("\nFound in their own artifacts again: " + ", ".join(r["row"] for r in s["resolved"]) + ".")
        out.append("")
    else:
        out.append("None.\n")
    out.append("## Inventory quotes no longer found\n")
    if s["lost_quotes"]:
        for aid, quotes in sorted(s["lost_quotes"].items()):
            first = next(iter(quotes.values()))
            out.append(f"- {aid}: {len(quotes)}, the first {code(to_ascii(scrubbed(first))[:160], table=False)}")
        out.append("")
    else:
        out.append("None.\n")
    out.append("## Concept checks the stamp had not seen\n")
    if s["without"]:
        out.append(f"Not made, since {', '.join(s['without'])} is not checked out: a check weighs each word by how rare it is across"
                   " every text, so fewer texts would give other checks than the stamp saw.\n")
    counts = {o: sum(1 for c in s["new_checks"] if c["outcome"] == o) for o in ("differs", "superseded", "open", "rounded", "agrees")}
    out.append(", ".join(f"{n} {o}" for o, n in counts.items()) + f"; {s['gone_checks']} checks of the stamp the texts no longer give.\n")
    listed = [c for c in s["new_checks"] if c["outcome"] != "agrees"]
    if listed:
        out.append("| Outcome | Concept | Gives | Where | Line | Passage |\n|---|---|---|---|---|---|")
        for c in listed[:REPORT_ROWS]:
            out.append(f"| {c['outcome']} | {cell(c['concept'])} | {cell(c['value'])} | {cell(c['source'])} | {c['line']} | {code(scrubbed(c['text'])[:160])} |")
        if len(listed) > REPORT_ROWS:
            out.append(f"\n{len(listed) - REPORT_ROWS} more, which `synth.py status --json` lists in a checkout.")
        by_hand = [c for c in listed if c not in w["concept_items"]]
        if by_hand:
            out.append(f"\n{len(by_hand)} of these no read settles, since a read takes only an artifact's passage that gives a"
                       " settled figure as superseded or open: a person changes the text, adds a set's names to work/aliases.json,"
                       " or takes every check the texts give now as seen with `synth.py stamp --checks` in a pull request.")
        out.append("")
    anything = bool(total or s["changes"] or d["gone"] or d["datasets_new"] or d["datasets_changed"] or d["datasets_gone"]
                    or s["stale"] or s["resolved"] or s["lost_quotes"] or listed or s["gone_checks"])
    text = to_ascii(scrubbed("\n".join(out) + "\n"))
    marker = hashlib.sha1(text.replace(when, "", 1).encode("utf-8")).hexdigest()[:12]
    return f"<!-- synthesis-report: {marker} -->\n{text}", marker, anything


def write_report(s, path):
    body, marker, anything = report(s)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(body)
    print(f"marker={marker}")
    print(f"anything={'true' if anything else 'false'}")


def concepts_written(ledger, stamped):
    """The ledger and its page as they are written, the page rendered from the ledger as it is
    saved, so that the committed concepts.json renders the committed concepts.md again byte for
    byte. A run stops before it writes anything where either holds an e-mail address or a phone
    number, which every text is rid of before a check reads it (synth_concepts.sources), or a
    credential's shape, which no text is rid of and no record may hold."""
    import synth_concepts as sc
    import synth_reads as sr
    ledger = scrubbed(ledger)
    page = scrubbed(sc.page(ledger, stamped or "none"))
    why = sr.personal_problem([ledger, page])
    if why:
        raise SystemExit(f"concepts refused: the ledger or its page {why[3:]}, so nothing was written")
    return ledger, page


def write_concepts(ledger, state):
    ledger, page = concepts_written(ledger, state.get("stamped"))
    save(LEDGER, ledger)
    with open(PAGE, "w", encoding="ascii", newline="\n") as f:
        f.write(page)


def rekey(run, state, base):
    """Carry the stamp's word over a change to the tools that renames the concept checks' keys
    and not what they check, as a change to what the scrub takes out does, since a key is made
    from the scrubbed passage: the ledger that the tools of base, a checkout of main, give is
    set beside the one this checkout's give, and each key of the stamp's whose check pairs with
    one of this checkout's takes that check's key. This checkout is up to date with main and
    changes none of the texts the checks read and none of the records the concepts are made
    from, so a check that pairs differs from its old self only in what the tools made of its
    passage. The ledger, its page and the stamp are written again, and nothing else in the stamp
    changes, so the look counts as new only the checks no pair carries."""
    import synth_state as st
    same_texts(base)
    ledger = concepts_now(run)
    pairs = paired(ledger_of(base), ledger)
    checks, renamed = rekeyed(state.get("checks", {}), pairs)
    new = {**state, "checks": checks}
    write_concepts(ledger, new)
    st.write(STATE, new)
    print(f"rekeyed: {len(pairs)} checks paired, {renamed} of the stamp's {len(checks)} keys renamed")


def identity(check):
    return (check["concept"], check["kind"], check["source"], check["line"], check["outcome"], check["value"])


def paired(old, new):
    """Each key of the old ledger's checks with the key of the new ledger's check that is the
    same check, the same concept, kind, source, line, outcome and value, where those name one
    check on each side; a line that gives two such checks pairs neither, so a stamp never takes
    one passage's word for another's."""
    def unique(ledger):
        count = Counter(identity(c) for c in ledger["checks"])
        return {identity(c): c["key"] for c in ledger["checks"] if count[identity(c)] == 1}
    a, b = unique(old), unique(new)
    return {a[i]: b[i] for i in sorted(a.keys() & b.keys(), key=repr)}


def rekeyed(checks, pairs):
    """The stamp's checks, each key a pair names renamed, and how many were."""
    out = {pairs.get(k, k): src for k, src in checks.items()}
    if len(out) != len(checks):
        raise SystemExit("rekey refused: two of the stamp's keys would become one, so nothing was written")
    return dict(sorted(out.items())), sum(1 for k in checks if pairs.get(k, k) != k)


# What the concept checks read in this repository beside the artifacts' folders: the research
# notes and the dataset records (synth_concepts.sources).
NOTES_AND_RECORDS = ("docs/research", "data/sources")
# The records the concepts are made from (concepts_now): a figure's id is its place in the
# numbers table's list, so a check is the same check on both sides only over the same records.
CONCEPT_RECORDS = tuple(path.relative_to(ROOT).as_posix() for path in
                        (SYNTH / "inventory.json", OUT / "contradictions-merged.json", OUT / "numbers-partial.json", ALIASES))


def tools_of(base):
    """The synthesis's tools in base, which must be the top of a checkout of this repository."""
    import synth_state as st
    tools = Path(base) / "artifacts" / "_synthesis" / "work" / "tools"
    try:
        top = st.git(base, "rev-parse", "--show-toplevel").strip()
    except (OSError, subprocess.CalledProcessError):
        top = None
    if not (tools / "synth.py").is_file() or top is None or not os.path.samefile(top, base):
        raise SystemExit(f"rekey refused: {base!r} is not a checkout of this repository")
    return tools


def rekey_refused(why):
    raise SystemExit(f"rekey refused: {why}, so nothing was written")


def tree_entries(checkout, *args):
    """git ls-tree's entries at HEAD as (mode, kind, object, path), read with -z so that no path
    comes back quoted."""
    import synth_state as st
    entries = st.git(checkout, "ls-tree", "-z", *args).split("\0")
    return [(*meta.split(), path) for meta, path in (entry.split("\t", 1) for entry in entries if entry)]


def text_trees(checkout, where):
    """The git object of each text the concept checks read in a checkout, every artifact's
    folder, the research notes and the dataset records, and of each record the concepts are
    made from. A rekey stops where they hold a change that is not committed, a link or a
    submodule, or a folder no tree holds, since a tree shows none of those as the tools read
    them."""
    import synth_state as st
    texts = ("artifacts", *NOTES_AND_RECORDS)
    status = ("status", "--porcelain", "--untracked-files=all", "--ignored", "--")
    if (st.git(checkout, *status, *texts, ":(exclude)artifacts/_*") + st.git(checkout, *status, *CONCEPT_RECORDS)).strip():
        rekey_refused(f"{where} holds a change to the texts the checks read, or to the records the concepts are made from,"
                      " that is not committed, which no tree shows; commit it or take it out")
    tops = {path for _mode, kind, _sha, path in tree_entries(checkout, "HEAD", "--", *texts) if kind == "tree"}
    if tops != set(texts):
        rekey_refused(f"{where} holds no tree at {', '.join(sorted(set(texts) - tops))}, where its tools read texts")
    links = [path for mode, _kind, _sha, path in tree_entries(checkout, "-r", "HEAD", "--", *texts)
             if mode in ("120000", "160000") and not path.startswith("artifacts/_")]
    if links:
        rekey_refused(f"{where} holds {len(links)} links or submodules among the texts the checks read, whose trees do not"
                      " change when what they lead to does")
    trees = st.folder_trees(checkout, "SchwingNet")
    folders = {f"SchwingNet/{p.name}" for p in Path(checkout, "artifacts").iterdir() if p.is_dir() and not p.name.startswith("_")}
    if folders != set(trees):
        rekey_refused(f"{where} holds {len(folders ^ set(trees))} folders under artifacts/ that no tree holds as its tools"
                      " read them")
    trees.update({path: sha for _mode, _kind, sha, path in tree_entries(checkout, "HEAD", "--", *NOTES_AND_RECORDS, *CONCEPT_RECORDS)})
    return trees


def same_texts(base):
    """Stop a rekey whose base is not a checkout of this repository, or reads other texts or
    other concepts than this checkout: a check pairs by its concept, kind, source, line, outcome
    and value and not by its passage, so a passage edited in place, or a figure that another
    took the place of, would take the stamp's word unread."""
    tools_of(base)
    mine, theirs = text_trees(ROOT, "this checkout"), text_trees(base, str(base))
    differ = sorted(k for k in mine.keys() | theirs.keys() if mine.get(k) != theirs.get(k))
    if differ:
        rekey_refused(f"the texts the checks read or the records the concepts are made from differ between this checkout and"
                      f" {base} in {', '.join(differ)}; bring main in, and change neither in the pull request that runs rekey")


def ledger_of(base):
    """The concept ledger the tools of another checkout of this repository give over its own
    texts, in a process of its own, so that neither copy's modules meet the other's, and with
    its texts extracted into a folder that goes when the ledger is read."""
    tools = tools_of(base)
    code = ("import json, sys; sys.path.insert(0, sys.argv[1]); import synth; "
            "json.dump(synth.concepts_now(synth.Run()), open(sys.argv[2], 'w', encoding='utf-8'))")
    env = {k: v for k, v in os.environ.items() if k not in ("SYNTH_TEXT", "SYNTH_SCHWINGNET")}
    with tempfile.TemporaryDirectory() as folder:
        out = os.path.join(folder, "ledger.json")
        env["SYNTH_TEXT"] = os.path.join(folder, "texts")
        done = subprocess.run([sys.executable, "-I", "-B", "-c", code, str(tools), out], env=env, cwd=folder)
        if done.returncode:
            raise SystemExit(f"rekey refused: the tools of {base} gave no ledger (exit {done.returncode}), so nothing was written")
        return load(out)


def stamp(run, state, at=None, only=None, checks=None, unstamped=()):
    """Record what the records were read from and what is already known: each artifact's tree
    (only those named, when only is given, so an artifact a run did not read keeps its old tree
    and the quotes its old text lacked, and none for a folder that is gone), each dataset
    record's hash, the quotes the texts do
    not hold, the verdicts whose quotes are found elsewhere (less the rows in unstamped, stale
    verdicts a run did not read again, which so stay stale), and the concept checks seen, each
    key with the text it was found in, so a run that cannot read one repository keeps that
    repository's checks."""
    import synth_state as st
    trees = run.trees(state, at)
    absent = st.absent_inventory_quotes({"artifacts": [r for a, r in run.records().items() if not run.skipped(a)]}, run.text_dir)
    absent_ids = st.absent_ids(absent)
    if only is not None:
        unread = {a for a in trees if a not in only and trees[a] != state["artifacts"].get(a)}
        trees = {a: (trees[a] if a in only else state["artifacts"].get(a)) for a in trees}
        trees = {a: t for a, t in trees.items() if t}
        absent_ids = {a: q for a, q in absent_ids.items() if a not in unread}
        absent_ids.update({a: q for a, q in state.get("inventory_absent", {}).items() if a in unread})
    places = st.odd_places(st.verdict_places(run.M, run.N, run.text_dir))
    places = {k: p for k, p in places.items() if k not in set(unstamped)}
    new = {
        "about": "What the synthesis's records were read from and what was already known when they were stamped"
                 " (work/tools/synth_state.py). artifacts: each folder's git tree as its inventory record read it."
                 " datasets: each record under data/sources/ by the sha256 of its bytes. inventory_absent: the ids of the"
                 " quotes of each inventory record its text did not hold. verdict_places: the verdicts whose quotes were"
                 " found anywhere but in their own artifacts. checks: the keys of the concept checks seen, each with its text.",
        "stamped": today(),
        "read_from": {**state.get("read_from", {}), **{r: v for r, v in (at or {}).items()}},
        "artifacts": trees,
        "datasets": st.dataset_hashes(ROOT),
        "inventory_absent": dict(sorted(absent_ids.items())),
        "verdict_places": places,
        "checks": dict(sorted((checks if checks is not None else state.get("checks", {})).items())),
    }
    st.write(STATE, new)
    return new


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("command", choices=["status", "concepts", "report", "plan", "join", "stamp", "rekey"])
    p.add_argument("paths", nargs="*")
    p.add_argument("--json")
    p.add_argument("--at", action="append", default=[])
    p.add_argument("--checks", action="store_true")
    p.add_argument("--status")
    p.add_argument("--without", action="append", default=[], choices=["symphony-template"])
    a = p.parse_args(argv)
    import synth_state as st
    state = st.load(STATE)
    if a.command == "report" and a.status:
        write_report(load(a.status), a.paths[0])
        return
    if a.command == "rekey" and len(a.paths) != 1:
        p.error("rekey takes one path: a checkout of main, with this checkout up to date with it and changing none of the texts"
                " and none of the records the concepts are made from")
    if a.without and a.command in ("concepts", "plan", "join", "stamp", "rekey"):
        raise SystemExit(f"{a.command} refused: it writes what every text gives, and without {', '.join(a.without)}'s checkout"
                         " that repository's word in the stamp and the ledger would be lost; status and report check without it")
    run = Run(a.without)
    if a.command == "status":
        s = status(run, state)
        w = reads_waiting(s)
        print(json.dumps({"delta": s["delta"], "stale": s["stale"], "lost_quotes": {k: len(v) for k, v in s["lost_quotes"].items()},
                          "new_checks": len(s["new_checks"]), "reads": {k: v for k, v in w.items() if k != "concept_items"}}, indent=1))
        if a.json:
            save(a.json, {k: v for k, v in s.items() if k != "ledger"})
    elif a.command == "concepts":
        write_concepts(concepts_now(run), state)
        print(f"{LEDGER.relative_to(ROOT)} and {PAGE.relative_to(ROOT)} written")
    elif a.command == "report":
        write_report(status(run, state), a.paths[0])
    elif a.command == "plan":
        plan_run(run, state, a.paths[0])
    elif a.command == "join":
        summary = join_run(run, state, *a.paths[:3])
        if len(a.paths) > 3:
            save(a.paths[3], summary)
        if not came_back(summary):
            raise SystemExit("join: no record and no verdict came back, so nothing was written")
    elif a.command == "rekey":
        rekey(run, state, a.paths[0])
    elif a.command == "stamp":
        at = dict(x.split("=", 1) for x in a.at)
        at_head(run, at)
        checks = None
        if a.checks or not state.get("checks"):
            checks = {c["key"]: c["source"] for c in concepts_now(run)["checks"]}
        new = stamp(run, state, at=at, checks=checks)
        print(f"stamped {len(new['artifacts'])} artifacts, {len(new['datasets'])} dataset records, {len(new['checks'])} checks")


def at_head(run, at):
    """Stop a stamp whose --at names a commit its checkout is not at: the trees would be taken at
    that commit and the quotes and verdict places from the checkout's own texts, so what changed
    between them would be stamped as read."""
    import synth_state as st
    for repo, ref in at.items():
        if repo not in run.clones:
            raise SystemExit(f"stamp refused: --at names {repo!r}, which is not one of {sorted(run.clones)}")
        want, have = (st.git(run.clones[repo], "rev-parse", x).strip() for x in (f"{ref}^{{commit}}", "HEAD"))
        if want != have:
            raise SystemExit(f"stamp refused: --at {repo}={ref} names {want[:12]}, but its checkout is at {have[:12]}; check out"
                             " that commit and stamp again, since the quotes are read from the checkout")


def seen_after(state, ledger, read, placed, waiting):
    """The checks a join takes as seen: the stamp's that the texts still give, with every check
    of a text read again and every check a verdict was placed for, but none whose verdict item
    waits, so the next run plans it again. A check the texts no longer give is dropped, so the
    issue does not count it as gone for ever."""
    now = {c["key"]: c["source"] for c in ledger["checks"]}
    seen = {k: src for k, src in state.get("checks", {}).items() if k in now}
    seen.update({k: src for k, src in now.items() if (src in read or k in placed) and k not in waiting})
    return seen


def readme_rows(run):
    import synth_reads as sr
    return sr.readme_rows(run.clones["SchwingNet"], "SchwingNet") + \
        (sr.readme_rows(run.clones["symphony-template"], "symphony-template") if "symphony-template" not in run.without else [])


def plan_run(run, state, out):
    import synth_reads as sr
    s = status(run, state)
    w = reads_waiting(s)
    args = sr.plan(out, s["changes"], s["stale"], w["concept_items"], s["unread"], s["ledger"]["figures"], run.records(),
                   readme_rows(run), run.clustering, run.M, run.N, run.text_dir, run.clones, today())
    items = len(load(args["items"])["items"])
    print(f"{len(args['inventory'])} artifacts to read ({len(args['waiting'])} waiting for a later run), {items} verdict items"
          f" ({len(args['items_waiting'])} waiting), and the finders' candidates after them; args at {out}/args.json")


def came_back(summary):
    """Whether a run has anything to write: a record, a verdict placed, or a verdict on a row
    that was there already, whose concept check it takes as seen."""
    return bool(summary["read"] or summary["placed"] or summary["already"])


def unfound_quotes(run, items, final, keys):
    """The verdicts placed whose quotes the script does not find where their artifacts are,
    which the pull request's body lists: the pages mark them, and the stamp keeps where they
    were found, so no later run flags them again."""
    import synth_state as st
    out = []
    for key in keys:
        it, v = items[key], final[key]
        a, b = (it.get("a") or {}).get("id"), (it.get("b") or {}).get("id")
        places = {st.quote_place(run.text_dir, v.get("quote_a"), a, b), st.quote_place(run.text_dir, v.get("quote_b"), b, a)}
        if places - set(st.FINE):
            out.append(key)
    return out


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings_in(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings_in(v)


def refuse_what_the_rule_keeps_out(before, after):
    """Stop the join before it writes, where a string the records did not hold before holds an
    e-mail address, a phone number or a credential's shape: every answer is checked where it
    is taken, and this is the check on the whole, should one path have been missed."""
    import synth_reads as sr
    old = {x for value in before for x in strings_in(value)}
    new = sorted({x for value in after for x in strings_in(value)} - old)
    why = sr.personal_problem(new)
    if why:
        raise SystemExit(f"join refused: a string it would write is new and {why[3:]}, so nothing was written")


def join_run(run, state, plan_dir, answers_dir, batches_dir):
    """Every answer that came back into the records, the pages rendered again and the state
    stamped for what was read, with a summary of what was placed and what waits."""
    import render_clusters
    import render_contradictions2
    import render_inventory
    import synth_reads as sr
    args = load(os.path.join(plan_dir, "args.json"))
    found = sr.results_by_label(answers_dir)
    listed = os.path.join(batches_dir, "batches.json")
    batched = load(listed) if os.path.exists(listed) else {"batches": [], "items": {}, "dropped": []}
    rows = readme_rows(run)
    history_path = OUT / "inventory-history.json"
    history = load(history_path) if history_path.exists() else []
    read, left = sr.join_inventory(args, found, run.inventory, history, run.clustering, rows, args["date"])
    final, missing = sr.final_verdicts(batched["batches"], batched["items"], found)
    joined = sr.join_verdicts(batched["items"], final, missing, run.M, run.N, args["date"])
    kept = sr.kept_numbers(args, found, run.N, args["date"])
    summary = {"date": args["date"], "read": read, "left": left, "waiting_artifacts": args["waiting"], **joined,
               "missing": {k: missing[k] for k in joined["waiting"] + joined["unread"] if k in missing},
               "items_waiting": args["items_waiting"], "dropped": batched["dropped"], "kept_numbers": kept,
               "unfound_quotes": unfound_quotes(run, batched["items"], final, joined["placed_keys"])}
    if not came_back(summary):
        return summary
    before = (load(SYNTH / "inventory.json"), load(OUT / "clustering.json"), load(OUT / "contradictions-merged.json"),
              load(OUT / "numbers-partial.json"), load(history_path) if history_path.exists() else [])
    run.inventory, run.clustering, run.M, run.N, history = (scrubbed(x) for x in (run.inventory, run.clustering, run.M, run.N, history))
    refuse_what_the_rule_keeps_out(before, (run.inventory, run.clustering, run.M, run.N, history))
    ledger = concepts_now(run)
    concepts_written(ledger, today())
    save(SYNTH / "inventory.json", run.inventory)
    save(history_path, history)
    save(OUT / "clustering.json", run.clustering)
    save(OUT / "contradictions-merged.json", run.M)
    save(OUT / "numbers-partial.json", run.N)
    render_inventory.main(str(SYNTH / "inventory.json"), str(SYNTH / "inventory.md"))
    render_clusters.main(str(OUT / "clustering.json"), str(SYNTH / "inventory.json"), str(SYNTH / "clusters.md"))
    render_contradictions2.main(str(OUT / "contradictions-merged.json"), str(OUT / "numbers-partial.json"),
                                str(SYNTH / "inventory.json"), str(SYNTH / "contradictions.md"), args["date"])
    __import__("check_verdict_quotes").main(str(OUT / "contradictions-merged.json"), str(OUT / "numbers-partial.json"),
                                            str(OUT / "verdict-quotes.json"))
    later = joined["waiting"] + args["items_waiting"]
    waiting = {k[len("concept:"):] for k in later if k.startswith("concept:")}
    placed = {k[len("concept:"):] for k in final if k.startswith("concept:")} - waiting
    unstamped = {k[len("stale:"):] for k in later if k.startswith("stale:")}
    new = stamp(run, state, only=set(read), checks=seen_after(state, ledger, set(read), placed, waiting), unstamped=unstamped)
    write_concepts(ledger, new)
    print(f"joined {len(read)} records ({len(left)} left out), {joined['placed']} verdicts ({len(joined['already'])} already rows,"
          f" {len(joined['unread'])} found rows with no verdict yet, {len(joined['waiting'])} items waiting), {kept} number rows"
          " with no verdict; pages rendered and the state stamped for what was read")
    return summary


if __name__ == "__main__":
    main()
