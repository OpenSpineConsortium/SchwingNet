"""The steps of .github/workflows/synthesis.yml that are not Claude's: whether a run may read, each
Claude session's arguments and brief, its answer taken from the session's record, the verdict
batches the finders' candidates make with the planned items, the re-checkers' and the judges'
inputs, and the pull request's words.

Usage, as the workflow runs it (paths absolute, as the plan wrote them):
  synth_actions.py admit --status F --marks F --runs F --event E [--switch S] [--crowd C]
                         [--token true|false] [--app true|false] [--without W] [--conflict N]
                         [--foreign N] [--rejected N] [--cap N] --words F
  synth_actions.py marked --marks F            the runs the last marks name, one id a line
  synth_actions.py matrix PLAN                 the read legs, as reads=[...]
  synth_actions.py args STAGE [--model M] [--fallback M] [--effort E]
  synth_actions.py prompt STAGE PLAN BATCHES K
  synth_actions.py answer STAGE K EXECUTION_FILE ANSWERS
  synth_actions.py batch PLAN ANSWERS BATCHES  the skeptics' batches, as batches=[...]
  synth_actions.py recheck BATCHES ANSWERS B   the re-checker's input, as count=N
  synth_actions.py disputes BATCHES ANSWERS B  the judge's input, as count=N
  synth_actions.py message SUMMARY [--carried] the join's commit message
  synth_actions.py body SUMMARY --run URL [--old F]  the pull request's body
Every output meant for GITHUB_OUTPUT is printed as name=value lines, or as name<<END blocks for
the arguments and the prompt. A stage is read (one artifact's record and its finder), skeptic,
recheck or judge; K is the artifact's or the batch's number in the plan.
"""
import argparse
import datetime
import json
import os
import re
import string
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import redact  # noqa: E402
import synth_reads as sr  # noqa: E402

BRIEFS = Path(__file__).resolve().parent.parent / "briefs"
DEFAULT_CAP = 10
MAX_CAP = 50
# Three reading runs that all failed stop the runs a push or the schedule starts, for this long
# after the last of them, so a token at its limit or a broken brief does not spend the day's runs;
# a run started by hand always tries.
FAILURE_PAUSE = datetime.timedelta(hours=6)
NAME = re.compile(r"^[A-Za-z0-9._\[\]-]+$")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# Every tool that writes, runs a command, fetches or starts another session is denied, and so are
# the checkouts' .git folders, since the action writes its token into the remote's address there;
# reading inside the checkout needs no rule, and reading outside it asks, which a run refuses.
DENIED = ("Bash,Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch,Task,Agent,TodoWrite,"
          "Read(./.git/**),Read(./symphony-template/.git/**)")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")


def block(name, text, end):
    """A multi-line GITHUB_OUTPUT value; the text may not hold the line that ends it."""
    if end in text.splitlines():
        raise SystemExit(f"{name} holds its own delimiter {end}")
    return f"{name}<<{end}\n{text}\n{end}"


# Whether a run may read.

def artifacts_of(marks):
    """The marker artifacts of every page the listing gave: gh api --paginate --slurp gives a list
    of pages, one call a single page."""
    pages = marks if isinstance(marks, list) else [marks]
    return [a for page in pages if isinstance(page, dict) for a in page.get("artifacts", [])]


def runs_today(marks, today):
    """How many runs have read today, by the marker artifacts they kept."""
    return sum(1 for a in artifacts_of(marks) if (a.get("created_at") or "").startswith(today))


def marked(marks, n=3):
    """The ids of the last n runs that kept a mark, newest first, which the workflow then reads
    one by one, so a day of runs that did not read cannot push them out of a listing."""
    ids = []
    for a in sorted(artifacts_of(marks), key=lambda a: a.get("created_at") or "", reverse=True):
        run = (a.get("workflow_run") or {}).get("id")
        if isinstance(run, int) and run not in ids:
            ids.append(run)
    return ids[:n]


def failing(marks, runs, now):
    """Whether the last three runs that read all failed, the last of them less than
    FAILURE_PAUSE ago."""
    reading = set(marked(marks))
    done = sorted((r for r in runs.get("workflow_runs", []) if r.get("id") in reading and r.get("status") == "completed"),
                  key=lambda r: r.get("created_at") or "", reverse=True)[:3]
    if len(done) < 3 or any(r.get("conclusion") != "failure" for r in done):
        return False
    last = datetime.datetime.fromisoformat((done[0].get("updated_at") or done[0]["created_at"]).replace("Z", "+00:00"))
    return now - last < FAILURE_PAUSE


def cap_of(text):
    """The day's runs: the variable's whole number up to MAX_CAP, else the default."""
    text = (text or "").strip()
    return min(int(text), MAX_CAP) if text.isdigit() and len(text) <= 3 else DEFAULT_CAP


def admission(waiting, switch, crowd, token, conflict, done, cap, stopped, app="true", without="", foreign="", rejected=""):
    """Whether the run reads, and why, in the order a person would fix them."""
    if not waiting:
        return False, "Nothing waits to be read."
    if (switch or "").strip().lower() == "off":
        return False, "Reads wait, but the variable SYNTHESIS_READS is off, so no run reads; set it to on, or delete it, to let them start."
    if (crowd or "").strip().lower() == "true":
        return False, "Reads wait, but crowd mode is on (the variable CLAUDE_CROWD), and in crowd mode no workflow runs Claude."
    if token != "true":
        return False, "Reads wait, but the repository secret CLAUDE_CODE_OAUTH_TOKEN is not set, so no run can read."
    if app != "true":
        return False, ("Reads wait, but the variable SDLC_APP_ID or the secret SDLC_APP_PRIVATE_KEY of the SymphonyBoard App is not set,"
                       " so no run could open the pull request with what it read.")
    if without:
        return False, (f"Reads wait, but this run could not check out {without}, whose artifacts the synthesis reads too, and a run"
                       " reads only with both repositories, since a stamp made without one would take its checks as gone; the next"
                       " run that can check it out reads.")
    if conflict:
        return False, (f"Reads wait, but the open synthesis pull request #{conflict} no longer merges cleanly with main; merge or close it,"
                       " and the next run reads again.")
    if foreign:
        return False, (f"Reads wait, but the open synthesis pull request #{foreign} changes a file no join writes, such as a tool or a"
                       " brief, so no run builds on it; a person reads it and closes it, and the next run opens a new one.")
    if rejected:
        return False, (f"Reads wait, but owner-ok failed on the head of the open synthesis pull request #{rejected}, as it does when the"
                       " owner presses Reject, so no run builds on it; close it to start over, or run its owner-ok job again and"
                       " approve, and the next run reads.")
    if done >= cap:
        return False, f"Reads wait, but {done} runs have read today, the day's {cap}; the next run after midnight UTC reads."
    if stopped:
        return False, ("Reads wait, but the last three runs that read all failed, the last less than six hours ago, so this run does not"
                       " read; read their logs, and Run workflow on the Synthesis workflow tries again at once.")
    return True, f"This run reads: run {done + 1} of at most {cap} today."


def admit(a):
    import synth
    status = load(a.status)
    w = synth.reads_waiting(status)
    waiting = w["inventory"] + w["verdicts"]
    marks, runs = load(a.marks), load(a.runs)
    now = datetime.datetime.now(datetime.timezone.utc)
    stopped = a.event != "workflow_dispatch" and failing(marks, runs, now)
    ok, why = admission(waiting, a.switch, a.crowd, a.token, a.conflict, runs_today(marks, now.date().isoformat()), cap_of(a.cap),
                        stopped, a.app, a.without, a.foreign, a.rejected)
    with open(a.words, "w", encoding="utf-8") as f:
        f.write(f"## This run\n\n{why}\n")
    print(f"admit={'true' if ok else 'false'}")
    print(f"waiting={waiting}")
    print(f"why={why}")
    return 0


# The sessions' arguments, briefs and answers.

def schema(stage):
    import synth_schemas
    return synth_schemas.SCHEMAS[stage]


STAGES = {"read": {"turns": 150, "effort": None}, "skeptic": {"turns": 150, "effort": "high"},
          "recheck": {"turns": 150, "effort": "high"}, "judge": {"turns": 100, "effort": "high"}}


def claude_args(stage, model="", fallback="", effort=""):
    """The session's claude_args: its turns, model and effort, the tools it may not use, the
    user's settings alone, so no file of the repository's adds a hook or an instruction, and its
    schema. A name that is not a plain model name is left out, since the arguments are parsed as
    a shell's would be; the schema holds no single quote, backslash or dollar sign for the same
    reason."""
    spec = STAGES[stage]
    lines = [f"--max-turns {spec['turns']}"]
    if model and NAME.match(model):
        lines.append(f"--model {model}")
    if fallback and NAME.match(fallback) and fallback != model:
        lines.append(f"--fallback-model {fallback}")
    chosen = spec["effort"] or (effort if effort in EFFORTS else "")
    if chosen:
        lines.append(f"--effort {chosen}")
    text = json.dumps(schema(stage), separators=(",", ":"), ensure_ascii=True)
    if set(text) & set("'\\$"):
        raise SystemExit(f"the {stage} schema holds a quote, a backslash or a dollar sign, which claude_args cannot carry")
    lines += ["--permission-mode default", "--setting-sources user", f'--disallowedTools "{DENIED}"', f"--json-schema '{text}'"]
    return "\n".join(lines)


def brief(stage, values):
    """The common brief and the stage's own, with the run's values in their places."""
    text = (BRIEFS / "common.md").read_text(encoding="utf-8") + "\n" + (BRIEFS / f"{stage}.md").read_text(encoding="utf-8")
    return string.Template(text).substitute(values).strip()


def prompt(stage, plan, batches, k):
    found = sr.FOUND
    if stage == "read":
        unit = load(os.path.join(plan, "args.json"))["inventory"][int(k)]
        values = {"file": unit["file"], "max_cluster": found["cluster"], "max_number": found["number"], "max_other": found["number_other"]}
    else:
        name = {"skeptic": "skeptic", "recheck": "recheck", "judge": "judge"}[stage]
        path = os.path.join(batches, f"{name}-{k}.json")
        values = {"file": path, "count": len(load(path)["items"])}
    return brief(stage, values)


def structured_output(messages):
    """The answer of a session's last result message, or None."""
    for m in reversed(messages if isinstance(messages, list) else []):
        if isinstance(m, dict) and m.get("type") == "result":
            out = m.get("structured_output")
            return out if isinstance(out, dict) else None
    return None


def answer(stage, k, execution_file, out):
    """The session's answer written where the join reads it, by its label; none where the
    session gave none, which the join reads as an answer that did not come back."""
    try:
        result = structured_output(load(execution_file))
    except (OSError, ValueError):
        result = None
    if result is None:
        print(f"the {stage} session {k} gave no answer; what it was to read waits for the next run")
        return 0
    if stage == "read":
        save(os.path.join(out, f"inventory-{k}.json"), {"label": f"inventory:{k}", "result": {
            f: result.get(f) for f in ("record", "changed", "cluster", "cluster_why")}})
        save(os.path.join(out, f"candidates-{k}.json"), {"label": f"candidates:{k}", "result": {
            "cluster_candidates": result.get("cluster_candidates") or [],
            "number_candidates": (result.get("number_candidates") or []) + (result.get("number_other") or [])}})
    else:
        save(os.path.join(out, f"{stage}-{k}.json"), {"label": f"{stage}:{k}", "result": result})
    print(f"the {stage} session {k} answered")
    return 0


# The verdicts' batches and the files the re-checkers and judges read.

def apart(planned, new):
    """The items in the groups no batch mixes: the planned items, then each finder's candidates,
    so what one artifact's text says reaches the skeptic, re-checker and judge of its own
    finder's rows and nobody else's."""
    by_finder = {}
    for it in new:
        by_finder.setdefault(it["key"].rsplit(":", 2)[0], []).append(it)
    return [group for group in [planned, *by_finder.values()] if group]


def batch(plan, answers, out):
    args = load(os.path.join(plan, "args.json"))
    planned = load(args["items"])["items"]
    new, dropped = sr.found_items(args, sr.results_by_label(answers))
    items = planned + new
    os.makedirs(out, exist_ok=True)
    units = []
    for group in apart(planned, new):
        for b in range(0, len(group), sr.BATCH):
            chunk = group[b:b + sr.BATCH]
            path = os.path.join(out, f"skeptic-{len(units)}.json")
            save(path, {"items": chunk})
            units.append({"file": path, "keys": [it["key"] for it in chunk]})
    save(os.path.join(out, "batches.json"), {"batches": units, "items": {it["key"]: it for it in items}, "dropped": dropped})
    print(f"batches={json.dumps(list(range(len(units))))}")
    print(f"items={len(items)}")
    print(f"dropped={len(dropped)}")
    return 0


def batch_items(batches, b):
    listed = load(os.path.join(batches, "batches.json"))
    keys = listed["batches"][int(b)]["keys"]
    return [listed["items"][k] for k in keys]


def recheck(batches, answers, b):
    """The re-checker's input: each item the skeptic answered, with the skeptic's reading."""
    found = sr.results_by_label(answers)
    items = batch_items(batches, b)
    skeptic = sr.entries(found, f"skeptic:{b}", "items", {it["key"] for it in items})
    mine = [{**it, "verdict_under_review": skeptic[it["key"]]} for it in items if it["key"] in skeptic]
    save(os.path.join(batches, f"recheck-{b}.json"), {"items": mine})
    print(f"count={len(mine)}")
    return 0


def disputes(batches, answers, b):
    """The judge's input: each item whose re-checker overturned the skeptic's verdict or hint,
    with both readings."""
    found = sr.results_by_label(answers)
    items = batch_items(batches, b)
    skeptic = sr.entries(found, f"skeptic:{b}", "items", {it["key"] for it in items})
    checked = sr.entries(found, f"recheck:{b}", "items", set(skeptic))
    keys = set(sr.disputed(skeptic, checked))
    mine = [{**it, "verdict_under_review": skeptic[it["key"]], "re_checker_reading": checked[it["key"]]}
            for it in items if it["key"] in keys]
    save(os.path.join(batches, f"judge-{b}.json"), {"items": mine})
    print(f"count={len(mine)}")
    return 0


# The commit and the pull request.

def counts(s):
    return (f"{len(s['read'])} artifact record(s) read, {s['placed']} verdict(s) placed, {len(s['unread'])} found row(s) with no"
            f" verdict yet, {s['kept_numbers']} number row(s) kept without a verdict")


def message(summary, carried=False):
    """The commit's message. The branch is one commit on main, made again by every run that
    writes to it, so where an earlier run's reads are in it too the message says so."""
    s = load(summary)
    text = f"Synthesis: what the run of {s['date']} read\n\n{counts(s)}."
    if carried:
        text += " The commit carries the reads of the earlier runs its pull request lists too, laid on main again."
    return redact.scrub(text + "\n", Counter())


RUN_MARK = re.compile(r"^<!-- synthesis-run: (?P<id>[^ ]+) -->$")


def run_sections(old):
    """The sections of earlier runs in the pull request's body, each from its marker to the
    next, kept as they were written."""
    sections, current = [], None
    for line in (old or "").splitlines():
        if RUN_MARK.match(line.strip()):
            current = [line]
            sections.append(current)
        elif current is not None:
            current.append(line)
    return ["\n".join(s).strip() for s in sections]


def listing(title, entries):
    if not entries:
        return []
    return [f"{title}:", ""] + [f"- {e}" for e in entries] + [""]


def run_section(s, url):
    out = [f"<!-- synthesis-run: {url.rsplit('/', 1)[-1]} -->", f"### The run of {s['date']}", "",
           f"[The run]({url}): {counts(s)}.", ""]
    out += listing("Artifacts read", [f"`{a}`" for a in s["read"]])
    out += listing("Artifacts whose record did not come back or could not be placed, read again by the next run",
                   [f"`{a}`: {why}" for a, why in sorted(s["left"].items())])
    out += listing("Artifacts left for the next run by this run's limit", [f"`{a}`" for a in s["waiting_artifacts"]])
    out += listing("Verdict items with no verdict, which wait for the next run",
                   [f"{k}: {s['missing'].get(k, 'not read')}" for k in s["waiting"]])
    out += listing("Rows the finders found whose verdict did not come back, added with none for the next run to read",
                   [f"{k}: {s['missing'].get(k, 'not read')}" for k in s["unread"]])
    out += listing("Candidates dropped before any skeptic read them", [f"{d['key']}: {d['why']}" for d in s["dropped"]])
    out += listing("Verdicts placed whose quotes the script does not find in their artifacts, which the pages mark; read the"
                   " passage before relying on one", s.get("unfound_quotes", []))
    if s["items_waiting"]:
        out += [f"{len(s['items_waiting'])} planned verdict item(s) past this run's limit wait for the next run.", ""]
    if s["already"]:
        out += [f"{len(s['already'])} finder candidate(s) were rows already and were left as they stand.", ""]
    return "\n".join(out).strip()


HEADER = """\
Before: The synthesis of the artifacts (artifacts/_synthesis/) was read from the artifacts, the research notes and the dataset records as they stood at its stamp (work/out/state.json), and they have changed since, as the issue labelled synthesis lists.

After: What the runs below read is in the records: each new or changed artifact's record (the one it replaces is kept in work/out/inventory-history.json), each verdict read again in place of the one it replaces, which its delta mark keeps, each candidate the finders found as a new row at the end of its list, and the pages rendered again from the records. The stamp says what was read, so what a run did not read waits for the next.

What: The reads .github/workflows/synthesis.yml ran on this repository's Claude token, and the join of their answers (work/tools/synth.py join).

How: A Claude session read each new or changed artifact into a record and, as the finder, set it against its cluster and the numbers table; each verdict item, planned or found, was read by a skeptic, then by a re-checker told to overturn the skeptic's verdict and its hint, and each dispute by a judge (work/briefs/), the planned items and each finder's candidates in batches of their own. The sessions could read and search the checkout and nothing more, every tool that writes, runs a command, fetches or starts another session denied and the checkouts' .git folders too, with no repository instructions and a JSON schema for their answers; the join refuses an answer that holds an e-mail address, a phone number or a credential's shape, replaces a login, the owner's first name or a form's link with an editor's words (work/tools/redact.py), keeps a candidate only where the script finds its quotes in the artifacts it names, takes a verdict only on its item's scale, and places nothing it cannot name. The tools that ran are main's, and this pull request changes the records and the pages rendered from them alone; a run builds on it only while that holds and while owner-ok has not failed on its head. It merges by itself once the checks are green and the owner has tapped owner-ok; where main's rules do not require owner-ok, it is opened as a draft, and turned back into one by each later run, so a person marks it ready.

## Adversarial review

Each verdict here was read by a skeptic and then by a re-checker told to overturn it, and, where the re-checker disagreed with the verdict or its hint, by a judge who read both sources and ruled, before it was placed. A record of an artifact was read once, by its reader, and was not read again; a planner reads a row, and the passage it rests on, before relying on it, as the contradictions page says. A person's tap on owner-ok is the last read before this merges.
"""


def body(summary, url, old=None):
    s = load(summary)
    earlier = run_sections(Path(old).read_text(encoding="utf-8") if old and os.path.exists(old) else "")
    mine = run_section(s, url)
    marker = mine.splitlines()[0]
    sections = [x for x in earlier if x.splitlines()[0] != marker] + [mine]
    return redact.scrub(HEADER + "\n## The runs\n\n" + "\n\n".join(sections) + "\n", Counter())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("admit")
    for name in ("status", "marks", "runs", "words"):
        a.add_argument(f"--{name}", required=True)
    for name in ("event", "switch", "crowd", "token", "conflict", "cap", "without", "foreign", "rejected"):
        a.add_argument(f"--{name}", default="")
    a.add_argument("--app", default="true")
    sub.add_parser("marked").add_argument("--marks", required=True)
    sub.add_parser("matrix").add_argument("plan")
    g = sub.add_parser("args")
    g.add_argument("stage", choices=sorted(STAGES))
    for name in ("model", "fallback", "effort"):
        g.add_argument(f"--{name}", default="")
    r = sub.add_parser("prompt")
    for name in ("stage", "plan", "batches", "k"):
        r.add_argument(name)
    w = sub.add_parser("answer")
    for name in ("stage", "k", "execution_file", "answers"):
        w.add_argument(name)
    b = sub.add_parser("batch")
    for name in ("plan", "answers", "batches"):
        b.add_argument(name)
    for command in ("recheck", "disputes"):
        c = sub.add_parser(command)
        for name in ("batches", "answers", "b"):
            c.add_argument(name)
    m = sub.add_parser("message")
    m.add_argument("summary")
    m.add_argument("--carried", action="store_true")
    d = sub.add_parser("body")
    d.add_argument("summary")
    d.add_argument("--run", required=True)
    d.add_argument("--old")
    x = p.parse_args(argv)
    if x.command == "admit":
        return admit(x)
    if x.command == "marked":
        print("\n".join(str(i) for i in marked(load(x.marks))))
        return 0
    if x.command == "matrix":
        print(f"reads={json.dumps(list(range(len(load(os.path.join(x.plan, 'args.json'))['inventory']))))}")
        return 0
    if x.command == "args":
        print(block("args", claude_args(x.stage, x.model, x.fallback, x.effort), "SYNTHESIS_ARGS_END"))
        return 0
    if x.command == "prompt":
        print(block("prompt", prompt(x.stage, x.plan, x.batches, x.k), "SYNTHESIS_PROMPT_END"))
        return 0
    if x.command == "answer":
        return answer(x.stage, x.k, x.execution_file, x.answers)
    if x.command == "batch":
        return batch(x.plan, x.answers, x.batches)
    if x.command == "recheck":
        return recheck(x.batches, x.answers, x.b)
    if x.command == "disputes":
        return disputes(x.batches, x.answers, x.b)
    if x.command == "message":
        sys.stdout.write(message(x.summary, x.carried))
        return 0
    sys.stdout.write(body(x.summary, x.run, x.old))
    return 0


if __name__ == "__main__":
    sys.exit(main())
