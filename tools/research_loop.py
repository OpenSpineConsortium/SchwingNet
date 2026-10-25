"""The research loop's clerk: whether a run may start, which item it works, and its prompt.

Source: issue #220, 2026-10-24. The owner asked for "A CLAUDE INTEGRATION DIRECTLY INTO THE TEXTBOOK"
that carries the research on "INDEPDENTLY OF HUMAN INTERACTION", and then, told the loop would ask
before any grid job, fetch or training, gave it "full command to direct autonmous research" (the
owner's spelling, quoted as written).
.github/workflows/research.yml runs it every four hours on the repository's one Claude token; the
standing brief the session follows is .github/symphony/research.md. This module is the part that is
code, not Claude, so that the cap, the switch and the choice of item can be tested.

    python3 tools/research_loop.py marked --marks M     # the last three admitted runs' ids, one a line
    python3 tools/research_loop.py admit --marks M --runs R --switch S --crowd C --token T --cap N --event E --words F
    python3 tools/research_loop.py pick [--issues I --pulls P | --repo OWNER/NAME] [--item ID] [--out F]
    python3 tools/research_loop.py prompt --brief .github/symphony/research.md --pick F --run URL
    python3 tools/research_loop.py grid --command CMD --issue N [--item ID] [--start] [--python|--no-python]
    python3 tools/research_loop.py gate status|start|stop --issue N [--item ID]
    python3 tools/research_loop.py runs [--limit N]
    python3 tools/research_loop.py log RUN_ID
    python3 tools/research_loop.py dispatch --requests FILE --repo OWNER/NAME [--limit N]
    python3 tools/research_loop.py why EXECUTION_FILE   # the result and the session's last words, secrets masked

admit counts the day's runs by the marker artifact research-runs each admitted run keeps, as
synthesis.yml counts its reads, and stops after three failures in a row for six hours. pick chooses
the work: an open issue labelled research that the loop may carry on comes first, best ranked first,
then the best-ranked ready item of docs/textbook/claims.json that no open issue or pull request
labelled research names; an item is named by the marker `<!-- research-item: E07 -->` in a body or
by a title that begins `Research E07`. grid and gate are the session's one route to the grid's
workflows, and neither starts anything: each checks its request and appends it as one JSON line to
the file RESEARCH_REQUESTS names, at most RESEARCH_DISPATCHES_PER_RUN a session, and after the session
has ended the workflow's second job runs dispatch, which reads every line again against main's code,
refuses what it does not admit, dispatches the rest on main up to the limit and posts each run's link
on the item's issue, an open issue labelled research and no other. So the session holds no token that
can start a workflow: it reads web pages and issue text it cannot vouch for, and its workflow token in
RESEARCH_READ_TOKEN only reads the grid's runs, for runs and log. A grid command is one committed
program with plain arguments (command_problem): grid.yml runs whatever it is given with bash on a
university node, in a checkout of main, so a shell operator, a substitution, an inline program (-c)
or a file that is not on main is refused, at the queue and again at the dispatch. why reads the
action's execution file when the session step fails, since the action hides the session's output
and a run refused before its first turn would otherwise say only is_error. Standard library only.
"""

import argparse
import datetime
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))
import claims_rank  # noqa: E402

WORKER = "research-loop"
LABEL = "research"
OWNER_LABEL = "owner-act"
MARK = "research-runs"
DEFAULT_CAP = 6
MAX_CAP = 50
FAILURE_PAUSE = datetime.timedelta(hours=6)
ITEM_MARKER = re.compile(r"<!--\s*research-item:\s*(E\d{1,4})\s*-->")
ITEM_TITLE = re.compile(r"^\s*Research\s+(E\d{1,4})\b")
GATE_WORDS = ("status", "start", "stop")
GRID_WORKFLOWS = ("grid.yml", "grid-gate.yml")
WORKFLOW_TITLES = {"grid.yml": "Grid", "grid-gate.yml": "Grid gate"}
# The session's grid requests: the file the workflow names, how many one session may queue, and
# the first line of the dispatch job's comment, by which the next run finds the runs' links.
REQUESTS_ENV = "RESEARCH_REQUESTS"
DISPATCHES_ENV = "RESEARCH_DISPATCHES_PER_RUN"
DEFAULT_DISPATCHES = 3
MAX_DISPATCHES = 10
DISPATCH_MARKER = "<!-- research-loop: dispatched -->"
ITEM_ID = re.compile(r"^E\d{1,4}$")
# An issue's number as the claim protocol bounds one: one to nine ASCII digits, no leading zero.
ISSUE_NUMBER = re.compile(r"^[1-9][0-9]{0,8}$")
# The shape of a grid command: a program the checkout holds, run by bash or python3, with
# arguments of plain characters. The operators and substitutions bash would act on are refused
# in the whole command, since grid.yml hands it to bash -c as one string.
PROGRAMS = ("bash", "python3")
PYTHON_FLAGS = ("-I", "-B", "-u", "-E", "-s")
SHELL_CHARS = frozenset(";&|<>$`(){}\n\r\\")
ARGUMENT = re.compile(r"^[A-Za-z0-9_./=:,+%@ -]+$")
COMMAND_LENGTH = 2000


# Whether a run may start.

def artifacts_of(marks):
    """The marker artifacts of every page a listing gave: --paginate --slurp gives a list of pages."""
    pages = marks if isinstance(marks, list) else [marks]
    return [a for page in pages if isinstance(page, dict) for a in page.get("artifacts", [])]


def runs_today(marks, today):
    """How many runs were admitted today, in UTC, by the marks they kept."""
    return sum(1 for a in artifacts_of(marks) if (a.get("created_at") or "").startswith(today))


def marked(marks, n=3):
    """The ids of the last n runs that kept a mark, newest first."""
    ids = []
    for a in sorted(artifacts_of(marks), key=lambda a: a.get("created_at") or "", reverse=True):
        run = (a.get("workflow_run") or {}).get("id")
        if isinstance(run, int) and run not in ids:
            ids.append(run)
    return ids[:n]


def failing(marks, runs, now):
    """Whether the last three admitted runs all failed, the last less than FAILURE_PAUSE ago, so a
    token at its limit or a broken brief does not spend the day."""
    admitted = set(marked(marks))
    done = sorted((r for r in runs.get("workflow_runs", []) if r.get("id") in admitted and r.get("status") == "completed"),
                  key=lambda r: r.get("created_at") or "", reverse=True)[:3]
    if len(done) < 3 or any(r.get("conclusion") != "failure" for r in done):
        return False
    last = datetime.datetime.fromisoformat((done[0].get("updated_at") or done[0]["created_at"]).replace("Z", "+00:00"))
    return now - last < FAILURE_PAUSE


def cap_of(text):
    """The day's runs: the variable's whole number from 1 up to MAX_CAP, else the default."""
    text = (text or "").strip()
    if text.isdigit() and len(text) <= 3 and int(text) > 0:
        return min(int(text), MAX_CAP)
    return DEFAULT_CAP


def admission(switch, crowd, token, done, cap, stopped, event):
    """Whether the run may start, and the sentence that says why."""
    if (switch or "").strip().lower() == "off":
        return False, "The variable RESEARCH_LOOP is off, so the loop does nothing; delete it or set it to on to start it again."
    if (crowd or "").strip().lower() == "true":
        return False, "Crowd mode is on (CLAUDE_CROWD), and in crowd mode no workflow runs Claude."
    if token != "true":
        return False, "The repository secret CLAUDE_CODE_OAUTH_TOKEN is not set (docs/setup/claude-action.md)."
    if done >= cap:
        return False, f"{done} runs have started today, the day's {cap} (RESEARCH_RUNS_PER_DAY); the next run after midnight UTC starts."
    if stopped and event != "workflow_dispatch":
        return False, "The last three runs failed, the last less than six hours ago; Run workflow always tries."
    return True, f"This run works: run {done + 1} of at most {cap} today."


def admit(args):
    """Print admit= and why= for GITHUB_OUTPUT, and the words for the job summary."""
    marks = load_json(args.marks)
    runs = load_json(args.runs) if args.runs else {}
    now = datetime.datetime.now(datetime.timezone.utc)
    done = runs_today(marks, now.date().isoformat())
    ok, why = admission(args.switch, args.crowd, args.token, done, cap_of(args.cap), failing(marks, runs, now), args.event)
    Path(args.words).write_text(f"### The research loop\n\n{why}\n", encoding="utf-8")
    print(f"admit={'true' if ok else 'false'}")
    print(f"why={why}")
    return 0


# Which item a run works.

def item_named(entry, known):
    """The register item an issue or a pull request names, or None."""
    for text, pattern in ((entry.get("body") or "", ITEM_MARKER), (entry.get("title") or "", ITEM_TITLE)):
        match = pattern.search(text)
        if match and match.group(1) in known:
            return match.group(1)
    return None


def label_names(entry):
    """The names of an entry's labels, whether gh gave them as objects or strings."""
    return {label["name"] if isinstance(label, dict) else label for label in entry.get("labels") or []}


def issue_standing(issue):
    """What an open research issue means for the loop: mine (the loop may carry it on) or the reason
    it may not (blocked, owner, review, other)."""
    labels = label_names(issue)
    workers = {name.split(":", 1)[1] for name in labels if name.startswith(("worker:", "account:", "agent:"))}
    if "blocked" in labels:
        return "blocked"
    if OWNER_LABEL in labels:
        return "owner"
    if "in-review" in labels:
        return "review"
    if workers - {WORKER}:
        return "other"
    return "mine"


def pull_holds(pull, resumable_issues):
    """Whether an open research pull request holds its item from the loop: one marked ready waits
    for its merge, and a draft holds unless it is the claim of an issue the loop may carry on."""
    if not pull.get("isDraft", False):
        return True
    branch = pull.get("headRefName") or ""
    return not any(branch == f"claude/{number}" for number in resumable_issues)


def choose(register, issues, pulls, wanted=None):
    """The work this run takes: {"mode": "resume"|"new"|"none", "issue", "item", "held", "why"}."""
    rows = claims_rank.ranked(register)
    rank = {row["item"]["id"]: number for number, row in enumerate(rows, 1)}
    by_id = {row["item"]["id"]: row for row in rows}
    known = {item["id"] for item in register["items"]}
    held, resumable = {}, {}
    for issue in issues:
        item = item_named(issue, known)
        if item is None:
            continue
        standing = issue_standing(issue)
        if standing == "mine":
            resumable.setdefault(item, issue["number"])
        else:
            held[item] = f"issue #{issue['number']} ({standing})"
    for pull in pulls:
        item = item_named(pull, known)
        if item is not None and pull_holds(pull, set(resumable.values())):
            held.setdefault(item, f"pull request #{pull['number']}")
    for item in held:
        resumable.pop(item, None)
    if wanted:
        return chosen_by_hand(register, wanted, held, resumable, by_id)
    for item in sorted(resumable, key=lambda i: rank.get(i, len(rank) + 1)):
        if item in by_id:
            return picked("resume", resumable[item], by_id[item], register, held)
    for row in rows:
        item = row["item"]
        if row["ready"] and claims_rank.status_of(item) in ("open", "doing") and item["id"] not in held \
                and item["id"] not in resumable:
            return picked("new", None, row, register, held)
    return {"mode": "none", "issue": None, "item": None, "held": held,
            "why": "every ready item is done, held by an open issue or pull request, or waits on another"}


def chosen_by_hand(register, wanted, held, resumable, by_id):
    """The item a person named on Run workflow, unless another worker or the owner holds it."""
    if wanted not in by_id:
        return {"mode": "none", "issue": None, "item": None, "held": held,
                "why": f"{wanted} is not an item of the register that is still open"}
    if wanted in held:
        return {"mode": "none", "issue": None, "item": None, "held": held, "why": f"{wanted} is held by {held[wanted]}"}
    mode = "resume" if wanted in resumable else "new"
    return picked(mode, resumable.get(wanted), by_id[wanted], register, held)


def picked(mode, issue, row, register, held):
    """One choice, with the item as claims_rank summarises it."""
    item = claims_rank.summary(row, register)
    item["depends_on"] = row["item"]["depends_on"]
    return {"mode": mode, "issue": issue, "item": item, "held": held,
            "why": f"{'carries on issue #' + str(issue) if issue else 'starts'} {item['id']}, score {item['score']}"}


def gh_json(args):
    """One gh call's JSON answer."""
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out or "[]")


def open_research(repo):
    """The open issues and pull requests labelled research, read with gh."""
    common = ["--repo", repo, "--label", LABEL, "--state", "open", "--limit", "200"]
    issues = gh_json(["issue", "list", *common, "--json", "number,title,body,labels"])
    pulls = gh_json(["pr", "list", *common, "--json", "number,title,body,labels,isDraft,headRefName"])
    return issues, pulls


def pick(args):
    """Print the choice as JSON, and write it to --out when given."""
    register = claims_rank.load(args.file)
    if args.issues is not None:
        issues, pulls = load_json(args.issues), load_json(args.pulls) if args.pulls else []
    else:
        issues, pulls = open_research(args.repo or os.environ.get("GITHUB_REPOSITORY", ""))
    choice = choose(register, issues, pulls, (args.item or "").strip() or None)
    text = json.dumps(choice, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


# The prompt.

def block(name, text):
    """A multi-line GITHUB_OUTPUT value under a delimiter the text cannot hold."""
    end = "END_RESEARCH_" + secrets.token_hex(8)
    return f"{name}<<{end}\n{text}\n{end}"


def prompt_text(brief, choice, run_url):
    """The standing brief, then this run's work."""
    work = json.dumps(choice, indent=2)
    return (f"{brief.rstrip()}\n\n## This run\n\nYou are the worker {WORKER}. This run's page: {run_url}\n\n"
            f"The loop chose this work with `python3 tools/research_loop.py pick` (mode new starts the item, "
            f"resume carries on the open issue it names):\n\n```json\n{work}\n```\n")


def prompt(args):
    """Print prompt= for GITHUB_OUTPUT."""
    brief = Path(args.brief).read_text(encoding="utf-8")
    print(block("prompt", prompt_text(brief, load_json(args.pick), args.run)))
    return 0


# Why a session ended in error. claude-code-action shows the session's output only whole, so a
# run that fails before its first turn (a token refused, a limit reached) leaves a log that says
# only is_error:true; the execution file it writes, which the usage recorder reads too, holds the
# result and the session's last words.

SECRET_SHAPES = re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                           r"|[A-Za-z0-9+/_=-]{40,}")
WHY_MOST = 400


def masked(text):
    """Text with the shapes of common secrets replaced, since an error can quote a header."""
    return SECRET_SHAPES.sub("[masked]", text)


def last_result(messages):
    """The session's last result message, or None when it ended before one."""
    return next((m for m in reversed(messages) if isinstance(m, dict) and m.get("type") == "result"), None)


def last_words(messages, result):
    """What the session said last: the result's text, else the last assistant text."""
    said = result.get("result") if isinstance(result.get("result"), str) else ""
    if said.strip():
        return said.strip()
    for entry in reversed(messages):
        if not (isinstance(entry, dict) and entry.get("type") == "assistant"):
            continue
        content = (entry.get("message") or {}).get("content") or []
        texts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        if any(t.strip() for t in texts):
            return "\n".join(t for t in texts if t.strip()).strip()
    return ""


def why_text(messages):
    """The lines of the step summary: the result's fields and the session's last words, masked."""
    result = last_result(messages)
    if result is None:
        return ("- The session left no result: it ended before Claude answered "
                "(a start-up failure, a timeout or a cancel).")
    lines = [f"- is_error: {bool(result.get('is_error'))}, subtype: {result.get('subtype', '')}, "
             f"turns: {result.get('num_turns', '')}, duration: {result.get('duration_ms', '')} ms"]
    said = last_words(messages, result)
    if said:
        lines.append("- The session's last words: " + masked(said)[:WHY_MOST])
    else:
        lines.append("- The session said nothing.")
    return "\n".join(lines)


def why(args):
    """Print why the session ended, from the action's execution file, for the step summary."""
    path = Path(args.file)
    try:
        messages = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        print(f"### Why the session ended\n\n- No execution file could be read at {path.name}: "
              "the action ended before writing one.")
        return 0
    if not isinstance(messages, list):
        messages = [messages]
    print("### Why the session ended\n\n" + why_text(messages))
    return 0


# The route to the grid's workflows.

def read_env():
    """gh's environment with the workflow token, which reads the grid's runs and nothing more, in
    place of the session's own, which may not read them."""
    token = os.environ.get("RESEARCH_READ_TOKEN", "")
    if not token:
        raise SystemExit("RESEARCH_READ_TOKEN is not set: only a run of research.yml reads the grid's runs this way")
    return dict(os.environ, GH_TOKEN=token)


def dispatches_per_run(text=None):
    """How many grid requests one session may queue, and the dispatch job runs: the variable's whole
    number from 1 up to MAX_DISPATCHES, else the default."""
    text = (os.environ.get(DISPATCHES_ENV, "") if text is None else text or "").strip()
    if text.isdigit() and len(text) <= 2 and int(text) > 0:
        return min(int(text), MAX_DISPATCHES)
    return DEFAULT_DISPATCHES


def issue_number(text):
    """An issue's number from text a session or a request line gives, or None."""
    text = str(text if text is not None else "").strip()
    return int(text) if ISSUE_NUMBER.match(text) else None


def requests_in(path, most=100):
    """The request lines of the file, each parsed where it is JSON and kept as text where it is not,
    so the dispatch job refuses it with a reason, and how many more the file holds beyond the first
    most, which are not read: a session queues at most MAX_DISPATCHES, so a longer file was written
    some other way, and the job's comment stays a page. A file not there holds none."""
    lines, dropped = [], 0
    if not path or not Path(path).is_file():
        return lines, dropped
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw.strip():
            continue
        if len(lines) >= most:
            dropped += 1
            continue
        try:
            lines.append(json.loads(raw))
        except ValueError:
            lines.append(raw)
    return lines, dropped


def describe(line):
    """One request in a few words: the workflow and its command or word."""
    inputs = line.get("inputs") or {}
    what = inputs.get("command") if line.get("workflow") == "grid.yml" else inputs.get("word")
    return f"{line.get('workflow')} `{what}`"


def queue(workflow, inputs, args):
    """Append one request to the file RESEARCH_REQUESTS names, for the dispatch job after the session,
    and say so. The request names the item's issue, since that is where the dispatch job posts the
    run's link and where the next run reads it: a session opens the issue before it asks."""
    path = os.environ.get(REQUESTS_ENV, "")
    if not path:
        raise SystemExit(f"{REQUESTS_ENV} is not set: only a run of research.yml queues the grid's workflows")
    issue = issue_number(args.issue or os.environ.get("RESEARCH_ISSUE", ""))
    if issue is None:
        raise SystemExit("the request needs the item's issue: open the issue first (the brief's step 2) and pass --issue N")
    item = (args.item or os.environ.get("RESEARCH_ITEM", "")).strip()
    if item and not ITEM_ID.match(item):
        raise SystemExit(f"{item} is not an item id of the register (E07)")
    cap = dispatches_per_run()
    lines, dropped = requests_in(path)
    queued = len(lines) + dropped
    if queued >= cap:
        raise SystemExit(f"this session has queued {queued} grid requests, the run's {cap} ({DISPATCHES_ENV}); "
                         "the next run may ask again")
    asked = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = {"workflow": workflow, "inputs": inputs, "item": item, "issue": issue, "asked": asked}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print(f"Queued request {queued + 1} of at most {cap}: {describe(line)}. It runs after this session ends, "
          f"from this run's dispatch job, which posts the run's link on issue #{issue} in a comment beginning "
          f"{DISPATCH_MARKER}; the next run reads it there and with runs and log.")
    return 0


def main_ref():
    """The name main goes by in this checkout: origin/main where the clone has it, as the workflow's
    checkout and a claim branch made from it do, else main, else HEAD."""
    for ref in ("origin/main", "main", "HEAD"):
        found = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                               capture_output=True, text=True)
        if found.returncode == 0:
            return ref
    return "HEAD"


def on_main(path):
    """Whether main holds the file, read from git and not from the working tree, since grid.yml checks
    main out and a file the session wrote on its branch is not there."""
    shown = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{main_ref()}:{path}"], capture_output=True)
    return shown.returncode == 0


def file_problem(program, target, committed):
    """Why the file a grid command names is refused, or None."""
    if target is None:
        return f"{program} needs a committed file to run"
    if target.startswith("-"):
        return f"{program} takes a committed file, not {target}: no inline program and nothing from stdin"
    if target.startswith("/") or ".." in Path(target).parts:
        return f"{target} is not a path inside the checkout"
    if not committed(target):
        return f"{target} is not on main, which grid.yml checks out; a new program lands by pull request first"
    return None


def command_problem(command, committed=None):
    """Why a grid command is refused, or None when it is one committed program with plain arguments:
    bash FILE, or python3 [-I -B -u -E -s] FILE or -m unittest, each argument of letters, digits and
    _ . / = : , + % @ -, with no shell operator or substitution. No NAME=value before the program
    either, since PATH, BASH_ENV or PYTHONPATH would change what the committed file does; a program
    that needs a setting takes a flag."""
    committed = committed or on_main
    if not command.strip():
        return "grid needs a command"
    if len(command) > COMMAND_LENGTH:
        return f"the command is longer than {COMMAND_LENGTH} characters"
    found = sorted(set(command) & SHELL_CHARS)
    if found:
        return ("the command holds shell operators or substitutions (" + " ".join(repr(c) for c in found)
                + "): send one committed program with plain arguments")
    try:
        words = shlex.split(command)
    except ValueError as why:
        return f"the command does not split into words: {why}"
    if not words:
        return "the command names no program"
    program, rest = words[0], words[1:]
    if program not in PROGRAMS:
        return f"the program is {program}; grid.yml runs {' or '.join(PROGRAMS)} with a committed file, and no setting before it"
    if program == "python3":
        while rest and rest[0] in PYTHON_FLAGS:
            rest.pop(0)
    if program == "python3" and rest[:1] == ["-m"]:
        if rest[1:2] != ["unittest"]:
            return "python3 -m runs only unittest here; any other program is a committed file"
        rest = rest[2:]
    else:
        problem = file_problem(program, rest.pop(0) if rest else None, committed)
        if problem:
            return problem
    for word in rest:
        if not ARGUMENT.match(word):
            return f"the argument {word!r} holds characters other than letters, digits and _ . / = : , + % @ -"
    return None


def grid_inputs(command, start, python, committed=None):
    """grid.yml's inputs by name, each a string as the dispatch API reads them. A command that is not
    one committed program with plain arguments is refused (command_problem)."""
    problem = command_problem(command, committed)
    if problem:
        raise SystemExit(f"grid refuses the command: {problem}")
    return {"command": command, "start": "true" if start else "false", "python": "true" if python else "false"}


def gate_inputs(word):
    """grid-gate.yml's input, one of its three words."""
    if word not in GATE_WORDS:
        raise SystemExit(f"the gate's word is one of {', '.join(GATE_WORDS)}, not {word}")
    return {"word": word}


def flags(inputs):
    """The inputs as gh workflow run takes them: -f, since -F would read a command that begins with
    @ as a file."""
    return [flag for name, value in inputs.items() for flag in ("-f", f"{name}={value}")]


# The dispatch job, after the session.

def request_problem(line, committed=None):
    """Why the dispatch job refuses a request line, or None. The file was written in the session's
    environment, where any command could have written to it, so every line is read again here against
    main's code, as if the session had never checked it."""
    if not isinstance(line, dict):
        return "the line is not a request"
    workflow, inputs = line.get("workflow"), line.get("inputs")
    if workflow not in GRID_WORKFLOWS:
        return f"the loop dispatches only {', '.join(GRID_WORKFLOWS)}, not {workflow!r}"
    if not isinstance(inputs, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in inputs.items()):
        return "the inputs are not strings by name"
    if issue_number(line.get("issue")) is None:
        return "the request names no issue"
    item = line.get("item") or ""
    if not isinstance(item, str) or (item and not ITEM_ID.match(item)):
        return "the item is not an id of the register"
    if workflow == "grid-gate.yml":
        if set(inputs) != {"word"} or inputs["word"] not in GATE_WORDS:
            return f"the gate's word is one of {', '.join(GATE_WORDS)}"
        return None
    if set(inputs) != {"command", "start", "python"}:
        return "grid.yml takes command, start and python"
    if inputs["start"] not in ("true", "false") or inputs["python"] not in ("true", "false"):
        return "start and python are true or false"
    return command_problem(inputs["command"], committed)


def research_issue(repo, number, env=None):
    """Whether the number is an open issue of the repository labelled research, read with gh. The
    comment with the runs' links goes there and nowhere else, so a forged line cannot write on another
    issue, and a request for an issue that is not the loop's open work is not run, since its result
    would reach nobody."""
    try:
        issue = gh_json_env(["api", f"repos/{repo}/issues/{number}"], env or dict(os.environ))
    except (subprocess.CalledProcessError, ValueError):
        return False
    return (isinstance(issue, dict) and "pull_request" not in issue and issue.get("state") == "open"
            and LABEL in label_names(issue))


def newest_run(workflow, since, env, repo, seen=()):
    """The id and address of the first run of the workflow dispatched at or after since and not yet
    seen, waiting up to a minute for GitHub to list it."""
    for _ in range(12):
        runs = gh_json_env(["run", "list", "--repo", repo, "--workflow", workflow, "--event", "workflow_dispatch",
                            "--limit", "10", "--json", "databaseId,createdAt,url,status"], env)
        fresh = [r for r in runs if (r.get("createdAt") or "") >= since and r.get("databaseId") not in seen]
        if fresh:
            run = min(fresh, key=lambda r: r["createdAt"])
            return run["databaseId"], run["url"]
        time.sleep(5)
    return None, None


def gh_json_env(args, env):
    """One gh call's JSON answer under the given environment."""
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True, env=env).stdout
    return json.loads(out or "[]")


def start_run(workflow, inputs, repo, env=None, seen=()):
    """Dispatch one of the grid's workflows on main and return its run's id and address."""
    env = env or dict(os.environ)
    since = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    subprocess.run(["gh", "workflow", "run", workflow, "--repo", repo, "--ref", "main", *flags(inputs)],
                   check=True, capture_output=True, text=True, env=env)
    return newest_run(workflow, since, env, repo, seen)


def settle(lines, repo, limit, committed=None, issue_check=None, starter=None):
    """What the dispatch job does with each request line, in order: the rows {line, issue, url, run,
    refused}, and for each issue the lines name whether it is the loop's open work. A line main's code
    does not admit, or whose issue is not such work, is refused with its reason; the admitted ones are
    dispatched up to the limit, and the rest refused as over it. Each issue is asked about once, and
    the gh calls are given so a test can stand them in."""
    issue_check = issue_check or research_issue
    starter = starter or start_run
    rows, standing, seen, started = [], {}, [], 0
    for line in lines:
        row = {"line": line, "issue": issue_number(line.get("issue")) if isinstance(line, dict) else None,
               "url": None, "run": None, "refused": request_problem(line, committed)}
        rows.append(row)
        if row["issue"] is not None and row["issue"] not in standing:
            standing[row["issue"]] = issue_check(repo, row["issue"])
        if row["refused"]:
            continue
        if not standing[row["issue"]]:
            row["refused"] = f"issue #{row['issue']} is not an open issue labelled {LABEL}, so nothing is run for it"
            continue
        if started >= limit:
            row["refused"] = f"over this run's limit of {limit} requests ({DISPATCHES_ENV})"
            continue
        try:
            row["run"], row["url"] = starter(line["workflow"], line["inputs"], repo, seen=seen)
        except subprocess.CalledProcessError as why:
            words = (why.stderr or why.stdout or "").strip().splitlines()
            row["refused"] = "gh workflow run failed: " + (words[0] if words else f"exit {why.returncode}")
            continue
        started += 1
        if row["run"] is not None:
            seen.append(row["run"])
    return rows, standing


def report(rows, run_url="", dropped=0):
    """The dispatch job's words for the issue and the job summary: the marker first, then each request
    with its run's link or its refusal and the reason."""
    lines = [DISPATCH_MARKER, "The research loop's grid requests" + (f" (run {run_url})" if run_url else "")
             + ", read again against main's code after the session ended:", ""]
    for row in rows:
        what = describe(row["line"]) if isinstance(row["line"], dict) else "a line that is no request"
        if row["refused"]:
            lines.append(f"- refused {what}: {row['refused']}")
        elif row["url"]:
            lines.append(f"- dispatched {what}: {row['url']}")
        else:
            lines.append(f"- dispatched {what}: GitHub did not list its run within a minute; "
                         "`python3 tools/research_loop.py runs` finds it")
    if dropped:
        lines.append(f"- {dropped} more lines were not read: a session queues at most {MAX_DISPATCHES} requests")
    if not rows and not dropped:
        lines.append("- no request")
    return "\n".join(lines) + "\n"


def comment(repo, number, text, env=None):
    """Post the words on the issue, from a file, since a body is text and not an argument."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as f:
        f.write(text)
    try:
        subprocess.run(["gh", "issue", "comment", str(number), "--repo", repo, "--body-file", f.name],
                       check=True, capture_output=True, text=True, env=env or dict(os.environ))
    finally:
        os.unlink(f.name)


def dispatch(args):
    """The second job's command: read the session's requests, settle each against main's code, run
    the admitted ones and say what happened, on each item's issue and in the job summary."""
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    lines, dropped = requests_in(args.requests)
    rows, standing = settle(lines, repo, dispatches_per_run(args.limit))
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{run_id}" if run_id else ""
    text = report(rows, run_url, dropped)
    print(text, end="")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    # each issue the loop works hears of its own requests, the refused ones too, so the next run
    # learns what main's code would not run; an issue that is not the loop's open work hears nothing
    for number, ok in sorted(standing.items()):
        if ok:
            comment(repo, number, report([row for row in rows if row["issue"] == number], run_url))
    return 1 if any((row["refused"] or "").startswith("gh workflow run failed") for row in rows) else 0


def runs(args):
    """The last runs of the grid's two workflows, so a job is checked before it is asked for again."""
    env = read_env()
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    listed = {}
    for workflow in GRID_WORKFLOWS:
        listed[workflow] = gh_json_env(["run", "list", "--repo", repo, "--workflow", workflow, "--limit", str(args.limit),
                                        "--json", "databaseId,displayTitle,status,conclusion,createdAt,url"], env)
    print(json.dumps(listed, indent=2))
    return 0


def log(args):
    """The whole log of one run of the grid's workflows, which the session's own token may not read."""
    env = read_env()
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    view = subprocess.run(["gh", "run", "view", str(args.run), "--repo", repo, "--json", "workflowName"],
                          check=True, capture_output=True, text=True, env=env).stdout
    name = json.loads(view or "{}").get("workflowName", "")
    if name not in WORKFLOW_TITLES.values():
        raise SystemExit(f"run {args.run} is {name or 'no run'}, not one of the grid's")
    subprocess.run(["gh", "run", "view", str(args.run), "--repo", repo, "--log"], check=True, env=env)
    return 0


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parser():
    """The commands and their arguments."""
    top = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = top.add_subparsers(dest="command", required=True)
    m = sub.add_parser("marked")
    m.add_argument("--marks", required=True)
    a = sub.add_parser("admit")
    for name in ("marks", "words"):
        a.add_argument("--" + name, required=True)
    for name in ("runs", "switch", "crowd", "token", "cap", "event"):
        a.add_argument("--" + name, default="")
    p = sub.add_parser("pick")
    p.add_argument("--file", default=str(claims_rank.REGISTER))
    p.add_argument("--issues")
    p.add_argument("--pulls")
    p.add_argument("--repo", default="")
    p.add_argument("--item", default="")
    p.add_argument("--out")
    q = sub.add_parser("prompt")
    q.add_argument("--brief", required=True)
    q.add_argument("--pick", required=True)
    q.add_argument("--run", default="")
    y = sub.add_parser("why")
    y.add_argument("file")
    g = sub.add_parser("grid")
    g.add_argument("--command", dest="grid_command", required=True)
    g.add_argument("--start", action="store_true")
    g.add_argument("--python", action=argparse.BooleanOptionalAction, default=True)
    w = sub.add_parser("gate")
    w.add_argument("word")
    for asks in (g, w):
        # the issue the run's link is posted on, and the item it works; RESEARCH_ISSUE and
        # RESEARCH_ITEM, which the workflow sets from the pick, stand in where they are not given
        asks.add_argument("--issue", default="")
        asks.add_argument("--item", default="")
    r = sub.add_parser("runs")
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--repo", default="")
    lg = sub.add_parser("log")
    lg.add_argument("run", type=int)
    lg.add_argument("--repo", default="")
    d = sub.add_parser("dispatch")
    d.add_argument("--requests", required=True)
    d.add_argument("--repo", default="")
    d.add_argument("--limit", default="")
    return top


def main(argv=None):
    """Run one command."""
    args = parser().parse_args(argv)
    if args.command == "marked":
        print("\n".join(str(run) for run in marked(load_json(args.marks))))
        return 0
    if args.command == "admit":
        return admit(args)
    if args.command == "pick":
        return pick(args)
    if args.command == "prompt":
        return prompt(args)
    if args.command == "why":
        return why(args)
    if args.command == "runs":
        return runs(args)
    if args.command == "log":
        return log(args)
    if args.command == "dispatch":
        return dispatch(args)
    if args.command == "grid":
        return queue("grid.yml", grid_inputs(args.grid_command, args.start, args.python), args)
    return queue("grid-gate.yml", gate_inputs(args.word), args)


if __name__ == "__main__":
    sys.exit(main())
