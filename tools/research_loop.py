"""The research loop's clerk: whether a run may start, which item it works, and its prompt.

Source: issue #220, 2026-10-24. The owner asked for "a Claude integration directly into the textbook"
that carries the research on "independently of human interaction", and then, told the loop would ask
before any grid job, fetch or training, gave it "full command to direct autonomous research".
.github/workflows/research.yml runs it every four hours on the repository's one Claude token; the
standing brief the session follows is .github/symphony/research.md. This module is the part that is
code, not Claude, so that the cap, the switch and the choice of item can be tested.

    python3 tools/research_loop.py marked --marks M     # the last three admitted runs' ids, one a line
    python3 tools/research_loop.py admit --marks M --runs R --switch S --crowd C --token T --cap N --event E --words F
    python3 tools/research_loop.py pick [--issues I --pulls P | --repo OWNER/NAME] [--item ID] [--out F]
    python3 tools/research_loop.py prompt --brief .github/symphony/research.md --pick F --run URL
    python3 tools/research_loop.py grid --command CMD [--start] [--python|--no-python]
    python3 tools/research_loop.py gate status|start|stop
    python3 tools/research_loop.py runs [--limit N]
    python3 tools/research_loop.py log RUN_ID

admit counts the day's runs by the marker artifact research-runs each admitted run keeps, as
synthesis.yml counts its reads, and stops after three failures in a row for six hours. pick chooses
the work: an open issue labelled research that the loop may carry on comes first, best ranked first,
then the best-ranked ready item of docs/textbook/claims.json that no open issue or pull request
labelled research names; an item is named by the marker `<!-- research-item: E07 -->` in a body or
by a title that begins `Research E07`. grid, gate, runs and log are the session's one route to the grid's
workflows: they dispatch grid.yml or grid-gate.yml on main, or list their runs, with the workflow
token in RESEARCH_DISPATCH_TOKEN, which the session's own GitHub token cannot do. Standard library
only.
"""

import argparse
import datetime
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
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


# The route to the grid's workflows.

def dispatch_env():
    """gh's environment with the workflow token, which may dispatch, in place of the session's own."""
    token = os.environ.get("RESEARCH_DISPATCH_TOKEN", "")
    if not token:
        raise SystemExit("RESEARCH_DISPATCH_TOKEN is not set: only a run of research.yml may dispatch the grid's workflows")
    return dict(os.environ, GH_TOKEN=token)


def grid_inputs(command, start, python):
    """grid.yml's inputs as gh workflow run takes them."""
    if not command.strip():
        raise SystemExit("grid needs a command")
    return ["-f", f"command={command}", "-F", f"start={'true' if start else 'false'}",
            "-F", f"python={'true' if python else 'false'}"]


def gate_inputs(word):
    """grid-gate.yml's input, one of its three words."""
    if word not in GATE_WORDS:
        raise SystemExit(f"the gate's word is one of {', '.join(GATE_WORDS)}, not {word}")
    return ["-f", f"word={word}"]


def newest_run(workflow, since, env, repo):
    """The id and address of the first run of the workflow dispatched at or after since, waiting
    up to a minute for GitHub to list it."""
    for _ in range(12):
        runs = gh_json_env(["run", "list", "--repo", repo, "--workflow", workflow, "--event", "workflow_dispatch",
                            "--limit", "10", "--json", "databaseId,createdAt,url,status"], env)
        fresh = [r for r in runs if (r.get("createdAt") or "") >= since]
        if fresh:
            run = min(fresh, key=lambda r: r["createdAt"])
            return run["databaseId"], run["url"]
        time.sleep(5)
    return None, None


def gh_json_env(args, env):
    """One gh call's JSON answer under the given environment."""
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True, env=env).stdout
    return json.loads(out or "[]")


def dispatch(workflow, inputs, repo):
    """Dispatch one of the grid's workflows on main and print its run's address."""
    if workflow not in GRID_WORKFLOWS:
        raise SystemExit(f"the loop dispatches only {', '.join(GRID_WORKFLOWS)}")
    env = dispatch_env()
    since = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    subprocess.run(["gh", "workflow", "run", workflow, "--repo", repo, "--ref", "main", *inputs], check=True, env=env)
    run_id, url = newest_run(workflow, since, env, repo)
    print(json.dumps({"workflow": workflow, "run": run_id, "url": url}))
    return 0


def runs(args):
    """The last runs of the grid's two workflows, so a job is checked before it is sent again."""
    env = dispatch_env()
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    listed = {}
    for workflow in GRID_WORKFLOWS:
        listed[workflow] = gh_json_env(["run", "list", "--repo", repo, "--workflow", workflow, "--limit", str(args.limit),
                                        "--json", "databaseId,displayTitle,status,conclusion,createdAt,url"], env)
    print(json.dumps(listed, indent=2))
    return 0


def log(args):
    """The whole log of one run of the grid's workflows, which the session's own token may not read."""
    env = dispatch_env()
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    view = subprocess.run(["gh", "run", "view", str(args.run), "--repo", repo, "--json", "workflowName"],
                          check=True, capture_output=True, text=True, env=env).stdout
    name = json.loads(view or "{}").get("workflowName", "")
    if name not in ("Grid", "Grid gate"):
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
    g = sub.add_parser("grid")
    g.add_argument("--command", dest="grid_command", required=True)
    g.add_argument("--start", action="store_true")
    g.add_argument("--python", action=argparse.BooleanOptionalAction, default=True)
    g.add_argument("--repo", default="")
    w = sub.add_parser("gate")
    w.add_argument("word")
    w.add_argument("--repo", default="")
    r = sub.add_parser("runs")
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--repo", default="")
    lg = sub.add_parser("log")
    lg.add_argument("run", type=int)
    lg.add_argument("--repo", default="")
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
    if args.command == "runs":
        return runs(args)
    if args.command == "log":
        return log(args)
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY", "")
    if args.command == "grid":
        return dispatch("grid.yml", grid_inputs(args.grid_command, args.start, args.python), repo)
    return dispatch("grid-gate.yml", gate_inputs(args.word), repo)


if __name__ == "__main__":
    sys.exit(main())
