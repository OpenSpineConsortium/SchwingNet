"""What .github/workflows/add-worker.yml decides and says when someone asks
for a worker with the "Add a worker" issue form.

The form (.github/ISSUE_TEMPLATE/worker.yml) asks for a worker's settings,
GitHub writes the answers into the issue's body, and the workflow turns
them into the worker's file under .github/symphony/workers/ with
`python3 tools/workers.py from-form`, which also checks them. It then
pushes the file on a branch of its own, opens the pull request that adds
it, or, where the repository does not let GitHub Actions open one, gives
the link that opens it in one press, and answers on the issue with what
to do next: for a routine, the one prompt to paste, its name filled in.
The workflow runs only git, gh and the two scripts, so what it decides and
says is tested here (tests/test_add_worker.py).

  is-form                    exit 0 when the body on stdin is the form's
                             answers, 1 when it is not
  branch --name NAME         the branch the pull request comes from
  title --name NAME          the pull request's title, the commit's subject
  message --name NAME --runs RUNS --issue N
                             the commit message
  body --name NAME --runs RUNS --issue N
                             the pull request's body
  reply --name NAME --runs RUNS --url URL [--opened]
                             the answer on the issue: the pull request, or
                             the link that opens it, and what to do next
  refused --problems FILE    the answer when the form's answers do not hold
                             together, one problem a line in FILE
  not-allowed                the answer to someone who may not write here
  crowd                      the answer to a worker in Actions in crowd mode
"""

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from sdlc_protocol import workers  # noqa: E402

WORKER_PAGE = ROOT / "docs" / "agents" / "routines" / "worker.md"
BRANCH_PREFIX = "symphony/worker-"
NAME_SLOT = "<name>"
# The crowd's worker page, which scripts/crowd.py puts in the worker page's
# place in crowd mode, names its worker by the contributor's login and keeps
# one of two lines for the area, both of which `scripts/crowd.py doctor
# --worker` fills in; a page whose prompt has this slot and not the name's is
# that page.
LOGIN_SLOT = "<login>"
# The headings GitHub writes for the form's two dropdowns, which no other
# issue form here asks; an issue that has both is the form's.
FORM_HEADINGS = ("### Where it runs", "### How its pull requests land")
NOTHING_SECRET = "Nothing on this issue or in the file is ever a credential."


def is_form(body):
    lines = {line.strip() for line in (body or "").splitlines()}
    return all(heading in lines for heading in FORM_HEADINGS)


def branch(name):
    return BRANCH_PREFIX + name


def title(name):
    return f"Add the worker {name}"


def kind(runs):
    return {"actions": "a worker in GitHub Actions", "routine": "a routine on a Claude account",
            "session": "a person's own sessions"}[runs]


def message(name, runs, issue):
    return (f"{title(name)}\n\n"
            f"{name} is {kind(runs)}: .github/symphony/workers/{name}.json, written by\n"
            f".github/workflows/add-worker.yml from the answers on #{issue}.\n")


def body(name, runs, issue):
    return (f"This adds the worker {name}, {kind(runs)}, to the registry: .github/symphony/workers/{name}.json, "
            f"from the answers on #{issue}. docs/agents/WORKERS.md says what each setting does; change one in this "
            f"pull request before it merges, or in a pull request of its own after.\n\n"
            f"Closes #{issue}\n")


def first_block(page=WORKER_PAGE):
    """The worker page's first fenced block, its short prompt as written."""
    return Path(page).read_text(encoding="utf-8").split("```")[1::2][0].strip("\n")


def short_prompt(name, page=WORKER_PAGE):
    """The worker prompt's short form, the first fenced block of the worker
    page, with the worker's name in its slot."""
    return first_block(page).replace(NAME_SLOT, name)


def is_crowd_page(page=WORKER_PAGE):
    """Whether the worker page is the crowd's, whose prompt names the worker
    by the contributor's login."""
    block = first_block(page)
    return NAME_SLOT not in block and LOGIN_SLOT in block


def next_steps(name, runs, page=WORKER_PAGE):
    if runs == "actions":
        return (f"Once it merges, .github/workflows/workers.yml runs {name} on its own: every six hours, when an "
                f"issue is queued or given to it, and again while it has work. It runs on the repository secret "
                f"CLAUDE_CODE_OAUTH_TOKEN, on that account's plan; docs/setup/claude-action.md says how to set it "
                f"if it is not there yet. There is nothing to paste.")
    if runs == "routine" and is_crowd_page(page):
        return ("Once it merges, make the routine on your own Claude account. In crowd mode a contributor's worker "
                "works under their GitHub login: run `python3 scripts/crowd.py doctor --worker` in your clone, "
                "which checks your setup and prints your worker's prompt with your login and your area filled in, "
                "and make the routine with it as docs/agents/routines/worker.md says.")
    if runs == "routine":
        return (f"Once it merges, make the routine on the Claude account that runs it, with this prompt as it "
                f"stands, as docs/agents/routines/worker.md says (in that account's Project, with a schedule):\n\n"
                f"```\n{short_prompt(name, page)}\n```")
    return (f"Your sessions take your GitHub login as their name; if {name} is not your login, start them with "
            f"SYMPHONY_WORKER={name} in their environment, so their claims and the area here are {name}'s.")


def reply(name, runs, url, opened, page=WORKER_PAGE):
    where = (f"The pull request that adds it: {url}." if opened else
             f"This repository does not let GitHub Actions open a pull request, so open it here, in one press: "
             f"{url}.")
    return f"{where}\n\n{next_steps(name, runs, page)}\n\n{NOTHING_SECRET}\n"


def refused(problems):
    lines = [line for line in problems.splitlines() if line.strip()]
    listed = "\n".join(f"- {line.removeprefix('workers: ')}" for line in lines)
    return ("These answers do not make a worker yet:\n\n"
            f"{listed}\n\n"
            "Edit the issue's answers and the workflow reads them again. "
            ".github/symphony/workers/README.md says what each setting takes.\n")


def not_allowed():
    return ("Only someone who may write to this repository can add a worker, since a worker spends a Claude "
            "account's plan. A maintainer can add it from these answers, or by a pull request that adds its file.\n")


def crowd():
    return ("This repository is in crowd mode, which keeps every Claude token out of it, so a worker cannot run in "
            "GitHub Actions here. Choose \"routine\" and run it on your own account, as "
            "docs/agents/routines/worker.md says.\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="What add-worker.yml decides and says.")
    parser.add_argument("command", choices=("is-form", "branch", "title", "message", "body", "reply", "refused",
                                            "not-allowed", "crowd"))
    parser.add_argument("--name")
    parser.add_argument("--runs", choices=workers.RUNS)
    parser.add_argument("--issue")
    parser.add_argument("--url")
    parser.add_argument("--opened", action="store_true")
    parser.add_argument("--problems")
    args = parser.parse_args(argv)
    needs = {"branch": ("name",), "title": ("name",), "message": ("name", "runs", "issue"),
             "body": ("name", "runs", "issue"), "reply": ("name", "runs", "url"), "refused": ("problems",)}
    missing = [name for name in needs.get(args.command, ()) if not getattr(args, name)]
    if missing:
        parser.error(f"{args.command} needs " + ", ".join(f"--{name}" for name in missing))
    if args.command == "is-form":
        return 0 if is_form(sys.stdin.read()) else 1
    texts = {
        "branch": lambda: branch(args.name) + "\n",
        "title": lambda: title(args.name) + "\n",
        "message": lambda: message(args.name, args.runs, args.issue),
        "body": lambda: body(args.name, args.runs, args.issue),
        "reply": lambda: reply(args.name, args.runs, args.url, args.opened),
        "refused": lambda: refused(Path(args.problems).read_text(encoding="utf-8")),
        "not-allowed": not_allowed,
        "crowd": crowd,
    }
    sys.stdout.write(texts[args.command]())
    return 0


if __name__ == "__main__":
    sys.exit(main())
