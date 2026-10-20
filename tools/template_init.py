"""Turn a fresh copy of the template into its own repository.

"Use this template" copies the files with their placeholders still in them.
This script, run once by .github/workflows/template-init.yml on the first
push, fills the six placeholders in every text file outside
.github/workflows/, removes the marker folder .template/, starts the copy
with a blank checkpoint (.claude/session.md, and the decisions and
constraints in the block at the end of CLAUDE.md, which are the template's
own) and, with a token, makes the labels the board uses and opens the "Set
up this project" issue.
The code owner .github/CODEOWNERS names is the owner in a personal copy and,
in an organization's copy, the user whose push made it, read from the event
that started the run: GitHub asks a user or a team for review, never an
organization.
The workflows are never written: they carry no placeholder, and the
GITHUB_TOKEN the workflow runs with may not create, change or delete a file
under .github/workflows/, so the init workflow stays in the tree and ends
early on every later push. The script prints each path it changed or
removed. Running it twice changes nothing the second time: the placeholders
are gone, the folder is gone, a label that exists is fine and an open setup
issue is not opened again.
"""

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import marked_section

API = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "symphony-template-init"
TIMEOUT = 60
PLACEHOLDER_NAMES = ("PROJECT_NAME", "REPO", "OWNER", "CODE_OWNER", "DEFAULT_BRANCH", "YEAR")
REMOVED = (".template",)
WORKFLOWS = (".github", "workflows")
WORKFLOWS_NOTE = "(workflows are left as they are: GITHUB_TOKEN may not write them)"
NO_CODE_OWNER_NOTE = (
    "(.github/CODEOWNERS names the organization, which GitHub never asks for review, because"
    " no user made this copy: replace it with a user or a team, docs/setup/github.md section 7)"
)
SETUP_ISSUE_TITLE = "Set up this project"
# The labels GitHub Issues needs to be the queue, and the two the
# coordinator's planning reads: name, colour, description, the claim
# protocol's own list (sdlc_protocol.labels.LABELS) word for word. A
# worker's label, worker:<name>, is made when the worker first needs it.
LABELS = (
    ("todo", "0e8a16", "In the queue, open for a claim"),
    ("claimed", "fbca04", "A claude/<issue> branch holds it"),
    ("in-review", "1d76db", "A pull request is open and waiting"),
    ("blocker", "b60205", "Stops everyone until it is settled"),
    ("epic", "8b5cf6", "A request the coordinator plans into tasks (docs/agents/WORKERS.md)"),
    ("blocked", "e99695", "A worker waits on a peer or the coordinator (docs/agents/WORKERS.md)"),
)


class InitError(Exception):
    """Something the script could not do; the message never holds the token."""


def placeholder(name):
    """The marker for one value, assembled so this file carries none of them
    and survives its own run."""
    return "{{" + name + "}}"


def values(repo, default_branch, year, code_owner=None):
    """What each placeholder becomes. The code owner is the owner unless
    another login is given."""
    owner, _, name = repo.partition("/")
    if not owner or not name or "/" in name:
        raise InitError(f"--repo must be OWNER/NAME, not {repo!r}")
    return {
        placeholder("PROJECT_NAME"): name,
        placeholder("REPO"): repo,
        placeholder("OWNER"): owner,
        placeholder("CODE_OWNER"): code_owner or owner,
        placeholder("DEFAULT_BRANCH"): default_branch,
        placeholder("YEAR"): str(year),
    }


def read_event(path):
    """The event that started this workflow run, from the file Actions names
    in GITHUB_EVENT_PATH; empty without a path or when the file is not a
    JSON object."""
    if not path:
        return {}
    try:
        event = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return event if isinstance(event, dict) else {}


def is_organization_copy(repo, event):
    """Whether the event says this repository belongs to an organization. An
    event about another repository says nothing about this one."""
    repository = event.get("repository")
    if not isinstance(repository, dict) or str(repository.get("full_name", "")).lower() != repo.lower():
        return False
    owner = repository.get("owner")
    return isinstance(owner, dict) and owner.get("type") == "Organization"


def pushing_user(event):
    """The login of the user who sent the event, or None when an app or a
    bot sent it, since neither can be a code owner."""
    sender = event.get("sender")
    if isinstance(sender, dict) and sender.get("type") == "User" and sender.get("login"):
        return str(sender["login"])
    return None


def code_owner(repo, event):
    """The login .github/CODEOWNERS names, or None when nobody fits.

    GitHub requests review only from a user or a team with write access,
    never from an organization, so `* @ORG` asks nobody. In a personal copy
    the owner fits. In an organization's copy the user whose push started
    this run does: "Use this template" makes the copy's first commit as the
    person who made the repository, the GITHUB_ACTOR of that run. An
    organization's copy made by an app has no such person, and None says
    so; without an event the run cannot tell an organization from a user
    and keeps the owner.
    """
    owner = repo.partition("/")[0]
    if not is_organization_copy(repo, event):
        return owner
    return pushing_user(event)


def is_removed(rel):
    """Whether a relative path is, or lies under, something the run deletes."""
    posix = rel.as_posix()
    return any(posix == gone or posix.startswith(gone + "/") for gone in REMOVED)


def is_workflow(rel):
    """Whether a relative path lies under .github/workflows/, which the run
    never writes."""
    return tuple(rel.parts[:2]) == WORKFLOWS


def candidate_files(root):
    """Every file under root that may carry a placeholder, in a fixed order:
    .git, the workflows and the paths about to be removed are left out."""
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_symlink() or not path.is_file():
            continue
        if rel.parts[0] == ".git" or is_workflow(rel) or is_removed(rel):
            continue
        yield path


def fill(path, mapping):
    """Replace the placeholders in one file; True when it changed. A file that
    is not UTF-8 is not text and is left alone, and the bytes are rewritten
    as they were, so line endings survive."""
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return False
    filled = text
    for marker, value in mapping.items():
        filled = filled.replace(marker, value)
    if filled == text:
        return False
    path.write_bytes(filled.encode("utf-8"))
    return True


def fill_tree(root, mapping):
    """The relative paths of the files that changed."""
    changed = []
    for path in candidate_files(root):
        if fill(path, mapping):
            changed.append(path.relative_to(root).as_posix())
    return changed


# The checkpoint a new copy starts with. The template's own repository
# keeps its real checkpoint in .claude/session.md, for whoever continues
# the template's work, and a copy must not inherit it.
CHECKPOINT = ".claude/session.md"
BLANK_CHECKPOINT = '# Session checkpoint\n\nNothing has been checkpointed yet. The checkpoint skill (.claude/skills/checkpoint) and `cswap checkpoint write` rewrite this file at the end of a session, with these sections.\n\n## Completed work\n\n(none yet)\n\n## Current state\n\n(none yet)\n\n## Remaining tasks\n\n(none yet)\n\n## Decisions\n\n(none yet)\n\n## Constraints\n\n(none yet)\n'


def reset_checkpoint(root):
    """Write the blank checkpoint over the template's own; the path when it changed."""
    path = root / CHECKPOINT
    if not path.exists() or path.read_text(encoding="utf-8") == BLANK_CHECKPOINT:
        return []
    path.write_text(BLANK_CHECKPOINT, encoding="utf-8")
    return [CHECKPOINT]


# The block at the end of CLAUDE.md, between the cswap markers, holds the
# template's own durable decisions and constraints, which are about building
# the template and not about a copy. A copy starts with the block's empty
# form: its heading and intro kept, and each list holding the one line the
# checkpoint skill (.claude/skills/checkpoint) writes for an empty list.
CLAUDE_MD = "CLAUDE.md"
BLANK_LISTS = "### Durable decisions\n- (none recorded)\n### Constraints\n- (none recorded)"


def blank_block(block):
    """The checkpoint block with both lists emptied. What stands before its
    first ### heading, the begin marker, the heading and the intro, is kept
    as it is; a block with no such heading keeps all it holds, and the
    lists follow it."""
    cut = block.find("\n### ")
    if cut != -1:
        head = block[:cut + 1]
    else:
        head = block[:-len(marked_section.MARK_END)].rstrip("\n") + "\n\n"
    return head + BLANK_LISTS + "\n" + marked_section.MARK_END


def reset_checkpoint_block(root):
    """Empty the lists of CLAUDE.md's checkpoint block through the block's
    own helper, which keeps the rest of the file byte for byte and a CRLF
    file CRLF; the path when it changed. A file without the marker pair is
    left alone: the docs check reports it."""
    path = root / CLAUDE_MD
    if not path.is_file():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    begin = text.find(marked_section.MARK_BEGIN)
    end = text.find(marked_section.MARK_END, begin) if begin != -1 else -1
    if begin == -1 or end == -1:
        return []
    block = text[begin:end + len(marked_section.MARK_END)].replace("\r\n", "\n")
    updated = marked_section.upsert_marked_section(text, blank_block(block))
    if updated == text:
        return []
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    return [CLAUDE_MD]


def remove_template_files(root):
    """Delete the marker folder; the paths removed."""
    removed = []
    for gone in REMOVED:
        path = root / gone
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(gone + "/")
        elif path.exists():
            path.unlink()
            removed.append(gone)
    return removed


def request(token, method, path, body=None, params=None):
    """One call to GitHub's REST API; the answer's status and JSON. An error
    names the status and the path, never the token."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": USER_AGENT,
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    call = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(call, timeout=TIMEOUT) as answer:
            raw = answer.read()
            return answer.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as problem:
        raw = problem.read()
        try:
            detail = json.loads(raw) if raw else None
        except ValueError:
            detail = None
        return problem.code, detail
    except OSError as problem:
        raise InitError(f"{method} {path}: {getattr(problem, 'reason', problem)}") from None


def already_exists(detail):
    """Whether a 422 says the label is there, which is the fine kind."""
    errors = (detail or {}).get("errors") or []
    return any(e.get("code") == "already_exists" for e in errors if isinstance(e, dict))


def create_labels(token, repo):
    """Make the board's labels; one line per label saying what happened."""
    lines = []
    for name, color, description in LABELS:
        status, detail = request(
            token, "POST", f"/repos/{repo}/labels",
            {"name": name, "color": color, "description": description},
        )
        if status == 201:
            lines.append(f"label {name}: created")
        elif status == 422 and already_exists(detail):
            lines.append(f"label {name}: exists")
        else:
            raise InitError(f"POST /repos/{repo}/labels ({name}): HTTP {status}")
    return lines


# The Claude GitHub App's install page. GitHub documents a form of an app's
# install URL that preselects the account and the repositories, with
# suggested_target_id and repository_ids[] (its page on migrating an OAuth
# app to a GitHub App); the plain page is what the issue links when the ids
# could not be read.
APP_INSTALL = "https://github.com/apps/claude/installations/new"


def app_install_link(owner_id, repository_id):
    """The install page with this owner and this repository preselected."""
    return f"{APP_INSTALL}/permissions?suggested_target_id={owner_id}&repository_ids[]={repository_id}"


def repository_ids(token, repo):
    """The owner's id and the repository's id from one GET, or None when the
    call fails or answers something else; the issue then links the plain
    install page. The ids come from the API, which GITHUB_TOKEN may read on
    its own repository, and not from the workflow's event, so
    .github/workflows/template-init.yml passes nothing new and is unchanged."""
    status, found = request(token, "GET", f"/repos/{repo}")
    if status != 200 or not isinstance(found, dict):
        return None
    try:
        return int(found["owner"]["id"]), int(found["id"])
    except (KeyError, TypeError, ValueError):
        return None


def setup_issue_body(repo, default_branch, app_link=APP_INSTALL):
    """The checklist the person works through after the template has landed,
    with one absolute link per remaining step, because an issue body is not
    in the tree. The first box is the one command, scripts/setup-repo.sh,
    with the settings pages behind it for whoever does it by hand; the second
    is the one OAuth flow, with the app's install page and the new-secret
    form behind it. GitHub's secret and variable forms take no prefill, so
    those links open the form and the text names what to type. The opening
    line points a project for volunteers on their own Claude accounts at
    scripts/crowd.py instead, which rewrites this checklist for crowd mode:
    the first two boxes would store the owner's token and turn auto-merge on,
    which crowd mode keeps off."""
    base = f"https://github.com/{repo}/blob/{default_branch}"
    settings = f"https://github.com/{repo}/settings"
    return "\n".join([
        "This repository was made from the Symphony template. Finish setting it up below; or, to open it to volunteers "
        "who each work on their own Claude account, run `python3 scripts/crowd.py setup` instead, which rewrites "
        f"this checklist ([docs/setup/crowdsourcing.md]({base}/docs/setup/crowdsourcing.md)):",
        "",
        f"- [ ] Run `bash scripts/setup-repo.sh` once from your clone, with gh signed in; or by hand: import the branch rules under [Rules]({settings}/rules) (New ruleset, Import a ruleset, docs/setup/ruleset-main.json from your clone), tick \"Automatically delete head branches\" and \"Allow auto-merge\" under [General]({settings}) and \"Allow GitHub Actions to create and approve pull requests\" under [Actions]({settings}/actions) (Workflow permissions), turn on secret scanning and push protection under [Code security]({settings}/security_analysis), check the six labels under [Labels](https://github.com/{repo}/labels), and open [.github/CODEOWNERS]({base}/.github/CODEOWNERS) to see that GitHub marks no line of it as an error ([docs/setup/github.md]({base}/docs/setup/github.md), section 7).",
        f"- [ ] One OAuth flow for the Claude side: from Claude Code signed in as the main account, run /install-github-app and pick this repository; it installs the Claude GitHub App and writes the secret CLAUDE_CODE_OAUTH_TOKEN, which turns on @claude. By hand: [install the app]({app_link}), then run `claude setup-token` and paste the token as a [new repository secret]({settings}/secrets/actions/new) named CLAUDE_CODE_OAUTH_TOKEN ([docs/setup/claude-action.md]({base}/docs/setup/claude-action.md)).",
        f"- [ ] Make the thin Project for each Claude account ([docs/setup/claude-project.md]({base}/docs/setup/claude-project.md)).",
        f"- [ ] Add the workers that should run on their own, if any, with the [\"Add a worker\" issue form](https://github.com/{repo}/issues/new?template=worker.yml): a worker in GitHub Actions on the token above, or a routine on a Claude account ([docs/agents/WORKERS.md]({base}/docs/agents/WORKERS.md), [docs/agents/routines/worker.md]({base}/docs/agents/routines/worker.md)). People's sessions need nothing, and neither does the coordinator: the board's own run releases idle claims and tells overlapping work, and with the token set the coordinator workflow plans epics and tidies the memory every week ([docs/agents/routines/coordinator.md]({base}/docs/agents/routines/coordinator.md)).",
        f"- [ ] Fill in [docs/project.md]({base}/docs/project.md) and [docs/agents/OWNERSHIP.md]({base}/docs/agents/OWNERSHIP.md), and pick the spending profile in [docs/setup/tiers.md]({base}/docs/setup/tiers.md).",
        "- [ ] Run `bash scripts/check.sh` once locally.",
        "",
        "Close this issue when every box is ticked.",
    ])


def open_setup_issue(token, repo, default_branch):
    """Open the setup issue unless one with its title is already open."""
    status, found = request(token, "GET", f"/repos/{repo}/issues", params={"state": "open", "per_page": 100})
    if status != 200:
        raise InitError(f"GET /repos/{repo}/issues: HTTP {status}")
    for issue in found or []:
        if issue.get("title") == SETUP_ISSUE_TITLE and "pull_request" not in issue:
            return f"issue #{issue['number']}: exists"
    ids = repository_ids(token, repo)
    app_link = app_install_link(*ids) if ids else APP_INSTALL
    status, made = request(
        token, "POST", f"/repos/{repo}/issues",
        {"title": SETUP_ISSUE_TITLE, "body": setup_issue_body(repo, default_branch, app_link)},
    )
    if status != 201:
        raise InitError(f"POST /repos/{repo}/issues: HTTP {status}")
    return f"issue #{made['number']}: opened"


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Fill the template's placeholders and remove its marker folder.")
    parser.add_argument("--repo", required=True, help="OWNER/NAME of this repository")
    parser.add_argument("--default-branch", required=True, help="the default branch's name")
    parser.add_argument("--year", type=int, default=datetime.now().year, help="the LICENSE year (default: this year)")
    parser.add_argument("--root", default=".", help="the repository root (default: the current directory)")
    parser.add_argument("--create-labels", action="store_true", help="make the board's labels through the API (needs GITHUB_TOKEN)")
    parser.add_argument("--open-issue", action="store_true", help="open the setup issue through the API (needs GITHUB_TOKEN)")
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_PATH", ""),
                        help="the event file of the run, which says who made an organization's copy (default: $GITHUB_EVENT_PATH, set by Actions)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    root = Path(args.root).resolve()
    try:
        person = code_owner(args.repo, read_event(args.event))
        mapping = values(args.repo, args.default_branch, args.year, person)
        filled = fill_tree(root, mapping)
        for path in filled:
            print(f"{path}: filled")
        if filled:
            print(WORKFLOWS_NOTE)
        if filled and person is None:
            print(NO_CODE_OWNER_NOTE)
        for path in remove_template_files(root):
            print(f"{path}: deleted")
        for path in reset_checkpoint(root):
            print(f"{path}: reset to a blank checkpoint")
        for path in reset_checkpoint_block(root):
            print(f"{path}: checkpoint block emptied of the template's decisions and constraints")
        token = os.environ.get("GITHUB_TOKEN")
        if (args.create_labels or args.open_issue) and not token:
            raise InitError("GITHUB_TOKEN is not set; labels and the issue need it")
        if args.create_labels:
            for line in create_labels(token, args.repo):
                print(line)
        if args.open_issue:
            print(open_setup_issue(token, args.repo, args.default_branch))
    except InitError as problem:
        print(f"template_init: {problem}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
