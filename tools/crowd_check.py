"""The rules crowd mode holds a repository to, in one place.

A crowdsourced repository (docs/setup/crowdsourcing.md) is worked by
volunteers on their own Claude accounts. It holds no Claude credential,
token or routine trigger token of anyone's, runs none of the workflows that
spend a subscription, and takes work into the queue only from someone with
the Maintain or Admin role. scripts/crowd.py sets a repository up that way,
audits it and checks a contributor's machine; this module holds every name
those rules use, so the setup, the audit and the checks cannot drift apart.

GitHub enforces the rules through two commands here, the only parts that
read the environment, run git or run gh; everything they decide is a pure
function above them:

  guard  a step of the required check "check" (.github/workflows/ci.yml):
         while any sign of crowd mode is there, no Claude secret or variable
         may reach the repository; while the default branch says crowd mode
         is on, the variable CLAUDE_CROWD that keeps the Claude workflows
         from starting must be true, and a pull request may not change a
         committed checkpoint. It is told which secrets exist by name only,
         by ci.yml's job values, so the job that runs this repository's
         code never holds a secret's value.
  queue  .github/workflows/queue.yml, on every issue event that queues
         work: takes todo or blocker off again when someone without the
         Maintain or Admin role put it on, or changed a queued issue.

Standard library only, like the other tools, and no syntax newer than
Python 3.8: scripts/crowd.py imports this module and may run on an older
Python to say what is wrong with it.
"""

import json
import os
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import marked_section

# The secrets that would let a workflow run on someone's Claude
# subscription, or start a routine, or act as the template's GitHub App.
# None of them has a place in a crowd repository, from the repository or
# from the organization.
SECRET_NAMES = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "COORDINATOR_TRIGGER_URL",
    "COORDINATOR_TRIGGER_TOKEN",
    "SDLC_APP_PRIVATE_KEY",
)
# The variables that switched on the Actions worker and team mode before
# the registry of workers took their place (docs/agents/WORKERS.md). A crowd
# repository has no use for either, and the guard still refuses them, so a
# switch left over from an older copy cannot linger unseen.
VARIABLE_NAMES = ("CLAUDE_WORKER", "CLAUDE_TEAM")
# The variable the workflows read at job level: while it is true, the
# Claude workflows never start.
CROWD_VARIABLE = "CLAUDE_CROWD"
# The roles GitHub reports for someone who may queue work.
MAINTAINER_ROLES = ("admin", "maintain")
# The labels that put an issue in front of the workers.
QUEUE_LABELS = ("todo", "blocker")
# The line in docs/project.md that says which mode the repository is in;
# docs/project.md is imported into every session, so every session knows.
MODE_LINE = re.compile(r"^- Crowd mode: (on|off)\.", re.MULTILINE)

PROJECT = "docs/project.md"
CLAUDE_MD = "CLAUDE.md"
SESSION = ".claude/session.md"
# The files the guard reads at the default branch and in the checkout.
GUARDED_FILES = (PROJECT, CLAUDE_MD, SESSION)
# How ci.yml tells the guard what reaches the repository. SECRETS_SET is the
# space-separated names the job values found set, that job's only output,
# and VALUES_RESULT how that job ended: the job check, which runs the
# repository's code, names no secret, since GitHub hands a job's runner the
# value of every secret the job names. Variables are no secret, so the guard
# step reads them itself: SET_<NAME> is "true" when the variable is set.
SECRETS_SET = "SECRETS_SET"
VALUES_RESULT = "VALUES_RESULT"
SET_PREFIX = "SET_"
# An issue edit that changes what it asks.
EDITED_FIELDS = ("title", "body")
QUEUE_MARKER = "<!-- crowd:queue -->"
ACTIONS_BOT = "github-actions[bot]"
BOARD_WORKFLOW = "board.yml"
API_VERSION = "2022-11-28"
STATUS_LINE = re.compile(r"^HTTP/\S+ (\d{3})")
HEAD_END = re.compile(r"\r?\n\r?\n")
NEXT_LINK = re.compile(r'<https://api\.github\.com/([^>]+)>;\s*rel="next"')


class CheckError(Exception):
    """Something a check could not see or do; the message says what."""


def mode_of(text):
    """'on' or 'off' as docs/project.md's mode line says, or None when the
    text has no such line (a copy older than crowd mode)."""
    match = MODE_LINE.search(text or "")
    return match.group(1) if match else None


def is_true(value):
    """Whether a value says true, read generously: any sign of crowd mode
    holds a run to the secret rule."""
    return str(value or "").strip().lower() == "true"


def gate_holds(value):
    """Whether the Claude workflows' gate holds for this CLAUDE_CROWD: their
    condition `vars.CLAUDE_CROWD != 'true'` is false only for true in some
    case, since GitHub compares strings without case but trims nothing, so
    "true " leaves the gate open, and the guard must call that off."""
    return str(value or "").lower() == "true"


# The guard: a pure decision over what the default branch and the checkout
# hold and what the workflow saw.

GATE_OFF = (
    "the Claude workflows' gate is off: the default branch says crowd mode is on, but the variable {variable} is not "
    "true; set it back with `gh variable set {variable} --repo {repo} --body true`, and find out who removed it in "
    "the organization's audit log"
)
VALUE_REACHES = (
    "the {kind} {name} reaches this repository (from the repository, the organization or both), and in crowd mode "
    "no Claude credential or switch has a place here; delete it with `gh {kind} delete {name} --repo {repo}`, or take "
    "this repository off the organization {kind}'s list; `python3 scripts/crowd.py audit {repo}` says which"
)
VALUES_UNKNOWN = (
    "the job values, which names the Claude secrets that reach this repository, ended {result}, so whether one "
    "does is unknown; run the check again"
)
CHECKPOINT_CHANGED = (
    "this pull request changes {what}: in crowd mode a checkpoint is a comment on the pull request, never a commit "
    "(.claude/rules/crowd.md, the checkpoint skill); put it back as it is on the default branch"
)


def checkpoint_block(text):
    """The checkpoint block of CLAUDE.md, its markers included, or None when
    the file or a marker is missing."""
    if text is None:
        return None
    begin = text.find(marked_section.MARK_BEGIN)
    end = text.find(marked_section.MARK_END, begin) if begin != -1 else -1
    if begin == -1 or end == -1:
        return None
    return text[begin:end + len(marked_section.MARK_END)]


def value_problem(name, repo):
    kind = "secret" if name in SECRET_NAMES else "variable"
    return VALUE_REACHES.format(kind=kind, name=name, repo=repo)


def checkpoint_problems(base, head):
    changed = []
    if base.get(SESSION) != head.get(SESSION):
        changed.append(SESSION)
    if checkpoint_block(base.get(CLAUDE_MD)) != checkpoint_block(head.get(CLAUDE_MD)):
        changed.append("the checkpoint block of CLAUDE.md")
    return [CHECKPOINT_CHANGED.format(what=what) for what in changed]


def guard_problems(base, head, crowd_value, present, pull_request, repo, from_fork=False, values_result="success"):
    """Every way the run breaks crowd mode's rules, one sentence each with
    its fix; none when it keeps them or the repository is not in crowd mode.

    base and head map each of GUARDED_FILES to its text, None when absent:
    base is the default branch (a pull request's base, or the branch as
    pushed), head the checkout. crowd_value is CLAUDE_CROWD as the workflow
    saw it, present the forbidden names that reach the repository. Any sign
    of crowd mode holds the run to the secret rule, so the window between
    setup's variable and the merge of its pull request is covered too. The
    gate and the checkpoint rule follow the default branch alone: the setup
    pull request, whose base is off, may write the block once, and one that
    turns the mode off is still held to the rules it would remove. A fork's
    pull request sees no secret and perhaps no variable, so it is held to
    the checkpoint rule alone; the push that merges it is held to the rest.
    values_result is how ci.yml's job values ended: when it did not succeed,
    present may be missing a secret, so a run with crowd mode showing fails.
    """
    base_on = mode_of(base.get(PROJECT)) == "on"
    signalled = base_on or mode_of(head.get(PROJECT)) == "on" or is_true(crowd_value)
    problems = []
    if signalled and not from_fork:
        problems += [value_problem(name, repo) for name in present]
        if values_result != "success":
            problems.append(VALUES_UNKNOWN.format(result=values_result or "without running"))
    if base_on and not from_fork and not gate_holds(crowd_value):
        problems.append(GATE_OFF.format(variable=CROWD_VARIABLE, repo=repo))
    if base_on and pull_request:
        problems += checkpoint_problems(base, head)
    return problems


def guard_summary(base, head, crowd_value, from_fork=False):
    """The one line a passing run prints."""
    modes = (mode_of(base.get(PROJECT)), mode_of(head.get(PROJECT)))
    if "on" not in modes and not is_true(crowd_value):
        return "crowd: off"
    seen = "its checkpoint rule holds; a fork's pull request sees no secret" if from_fork else "its rules hold"
    return (f"crowd: on (the default branch says {modes[0] or 'nothing'}, this tree {modes[1] or 'nothing'}, "
            f"{CROWD_VARIABLE} {crowd_value or 'unset'}), and {seen}")


def present_names(environ):
    """The forbidden names that reach the repository: the secrets the job
    values named, and the variables the guard step was told are set."""
    secrets = set((environ.get(SECRETS_SET) or "").split())
    return ([name for name in SECRET_NAMES if name in secrets]
            + [name for name in VARIABLE_NAMES if is_true(environ.get(SET_PREFIX + name))])


# The guard's command line: git for the two trees, the environment for the
# rest.

def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd)] + list(args), capture_output=True, text=True, encoding="utf-8")


def has_commit(cwd, revision):
    return git(cwd, "cat-file", "-e", revision + "^{commit}").returncode == 0


def fetched(cwd, ref):
    """ref from origin, one commit deep, as FETCH_HEAD; the checkout holds
    only its own commit."""
    done = git(cwd, "fetch", "--no-tags", "--quiet", "--depth=1", "origin", ref)
    if done.returncode != 0:
        raise CheckError(f"could not fetch {ref} from origin to read the default branch's {PROJECT} "
                         f"({(done.stderr or '').strip()[:200]}); run the check again")
    return "FETCH_HEAD"


def base_revision(environ, cwd, pull_request):
    """The commit that says the default branch's mode: a pull request's
    base, or on a push the default branch itself, which is the checkout when
    the push was to it."""
    if pull_request:
        sha = environ.get("BASE_SHA") or ""
        if not re.match(r"^[0-9a-f]{40}$", sha):
            raise CheckError("BASE_SHA does not name the pull request's base commit; ci.yml passes it")
        if not has_commit(cwd, sha):
            fetched(cwd, sha)
        return sha
    default = environ.get("DEFAULT_BRANCH") or ""
    if not default or environ.get("GITHUB_REF_NAME") == default:
        return "HEAD"
    return fetched(cwd, "refs/heads/" + default)


def tree_files(cwd, revision):
    """The guarded files' texts at one revision, None for one not there."""
    if not has_commit(cwd, revision):
        raise CheckError(f"no commit {revision} in {cwd} to read {PROJECT} from")
    files = {}
    for path in GUARDED_FILES:
        done = git(cwd, "show", f"{revision}:{path}")
        files[path] = done.stdout if done.returncode == 0 else None
    return files


def guard(environ, cwd="."):
    repo = environ.get("GITHUB_REPOSITORY") or "OWNER/NAME"
    pull_request = environ.get("GITHUB_EVENT_NAME") == "pull_request"
    from_fork = pull_request and is_true(environ.get("FROM_FORK"))
    head = tree_files(cwd, "HEAD")
    base = tree_files(cwd, base_revision(environ, cwd, pull_request))
    crowd_value = environ.get(CROWD_VARIABLE, "")
    problems = guard_problems(base, head, crowd_value, present_names(environ), pull_request, repo, from_fork,
                              environ.get(VALUES_RESULT, ""))
    for problem in problems:
        print("crowd: " + problem, file=sys.stderr)
    if not problems:
        print(guard_summary(base, head, crowd_value, from_fork))
    return 1 if problems else 0


# The queue gate: a pure decision over one issue event and its sender's
# role.

QueueAction = namedtuple("QueueAction", "remove comment dispatch")
NOTHING = QueueAction((), False, False)


def queue_actions(event, role, commented=False):
    """What the queue gate does for one issue event, given the sender's role
    here (None for no role, a bot included): take off a queue label someone
    without Maintain or Admin added, and both of them from a queued issue
    such a person opened or whose title or body they changed, since an edit
    can change what a maintainer queued; comment once per issue, unless
    commented says the comment is there; and start the board, which a label
    taken off with GITHUB_TOKEN does not start by itself. A maintainer's
    event changes nothing."""
    if role in MAINTAINER_ROLES:
        return NOTHING
    action = event.get("action")
    on_issue = [label.get("name") for label in (event.get("issue") or {}).get("labels") or []]
    if action == "labeled":
        name = (event.get("label") or {}).get("name")
        remove = [name] if name in QUEUE_LABELS else []
    elif action == "opened" or (action == "edited" and set(event.get("changes") or {}) & set(EDITED_FIELDS)):
        remove = [name for name in QUEUE_LABELS if name in on_issue]
    else:
        remove = []
    if not remove:
        return NOTHING
    return QueueAction(tuple(remove), not commented, True)


def queue_comment(login, removed):
    return "\n".join([
        QUEUE_MARKER,
        f"Only someone with the Maintain or Admin role queues work here (docs/project.md, Crowd mode). "
        f"@{login}'s change took {' and '.join(removed)} off this issue; a maintainer reads it and queues it again "
        "if it should be worked. Workers take only what a maintainer queued.",
    ])


# The queue gate's command line: the event from Actions, GitHub through gh
# on the workflow's own token.

def parsed(output):
    """gh api --include's output as (status, headers, body)."""
    match = STATUS_LINE.match(output or "")
    if not match:
        return None
    end = HEAD_END.search(output)
    head, rest = (output[:end.start()], output[end.end():]) if end else (output, "")
    headers = {}
    for line in head.splitlines()[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    try:
        body = json.loads(rest) if rest.strip() else None
    except ValueError:
        body = rest
    return int(match.group(1)), headers, body


def api(method, path, body=None, ok=()):
    """One REST call through gh: its status, headers and body. A status of
    400 or more raises unless ok names it."""
    args = ["gh", "api", "--include", "--method", method, path,
            "-H", "Accept: application/vnd.github+json", "-H", "X-GitHub-Api-Version: " + API_VERSION]
    stdin = None
    if body is not None:
        args += ["--input", "-"]
        stdin = json.dumps(body)
    done = subprocess.run(args, input=stdin, capture_output=True, text=True, encoding="utf-8")
    answer = parsed(done.stdout)
    if answer is None:
        raise CheckError(f"{method} {path}: gh gave no HTTP answer ({(done.stderr or '').strip()[:200]})")
    if answer[0] >= 400 and answer[0] not in ok:
        raise CheckError(f"{method} {path}: HTTP {answer[0]}")
    return answer


def pages(path):
    items = []
    while path:
        _, headers, body = api("GET", path)
        items.extend(body or [])
        match = NEXT_LINK.search(headers.get("link", ""))
        path = match.group(1) if match else None
    return items


def role_of(repo, sender):
    """The sender's role here, or None: a bot or someone with no access has
    none, and so may not queue."""
    login = sender.get("login") or ""
    if not login or sender.get("type") == "Bot":
        return None
    status, _, body = api("GET", f"repos/{repo}/collaborators/{login}/permission", ok=(404,))
    return (body or {}).get("role_name") if status == 200 else None


def already_commented(repo, number):
    return any(QUEUE_MARKER in (comment.get("body") or "") and (comment.get("user") or {}).get("login") == ACTIONS_BOT
               for comment in pages(f"repos/{repo}/issues/{number}/comments?per_page=100"))


def queue(environ):
    event = json.loads(Path(environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    repo = environ["GITHUB_REPOSITORY"]
    number = event["issue"]["number"]
    sender = event.get("sender") or {}
    login = sender.get("login") or "someone"
    role = role_of(repo, sender)
    action = queue_actions(event, role)
    if not action.remove:
        print(f"queue: #{number}: {login} ({role or 'no role'}) changed nothing a maintainer queued")
        return 0
    action = queue_actions(event, role, commented=already_commented(repo, number))
    for name in action.remove:
        api("DELETE", f"repos/{repo}/issues/{number}/labels/{name}", ok=(404,))
    if action.comment:
        api("POST", f"repos/{repo}/issues/{number}/comments", {"body": queue_comment(login, action.remove)})
    if action.dispatch:
        branch = environ.get("DEFAULT_BRANCH") or (event.get("repository") or {}).get("default_branch") or "main"
        api("POST", f"repos/{repo}/actions/workflows/{BOARD_WORKFLOW}/dispatches", {"ref": branch})
    print(f"queue: #{number}: took {' and '.join(action.remove)} off, since {login} has {role or 'no role'} here")
    return 0


COMMANDS = {"guard": guard, "queue": queue}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in COMMANDS:
        print("usage: crowd_check.py guard|queue (run by .github/workflows/ci.yml and queue.yml)", file=sys.stderr)
        return 2
    try:
        return COMMANDS[args[0]](os.environ)
    except CheckError as problem:
        print(f"crowd: {problem}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
