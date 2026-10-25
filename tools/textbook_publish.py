"""The steps around the publish of the textbook edition as one claude.ai artifact (issue #236):
what the book is built from, whether a run may publish, what changed since the last publish, the
prompt that tells Claude exactly what to publish, and the record left on the branch
textbook-artifact.

The owner decided on 2026-10-24 that the book is republished after each merge to main by an
Action (.github/workflows/textbook-artifact.yml) on the repository's Claude token, the
subscription token of one account, so the artifact lands in that account's gallery, private until
that account shares it. The Action's first run, on 2026-10-25, found that the session
claude-code-action starts has no Artifact tool, and Claude Code's documentation says the tool is
off in the GitHub Action, the Agent SDK and `claude -p` whatever the settings say
(docs/research/textbook-as-an-artifact.md). So the command `local` makes the same publish from a
computer where Claude Code is signed in to the account that keeps the artifact (issue #277): it
fetches main, reads the record, stops where the book's inputs are the ones already published,
builds the edition from main's commit in a folder outside the clone, opens Claude Code there on
the same mechanical prompt, and records the session's answer on the branch as the workflow's
record job does. Nothing here carries the book's text: the prompt and the record hold paths,
hashes, a commit and a link, and the only text the session sees of the book is what the Artifact
tool's own read of the front page returns, which the tool requires before a publish to an
existing artifact.

The record is one file, state.json, on the branch textbook-artifact, written with GITHUB_TOKEN
by fast-forward commits alone: the artifact's link, the commit the published edition was built
from and its date, a fingerprint of the book's inputs at that commit, and the sha256 of every
published path. A run reads it first and stops before building when the inputs it would build
from are the ones already published, so the schedule, which exists because a merge GitHub's
auto-merge makes starts no workflow, costs nothing while the book is unchanged. The day's
publishes are counted from that branch's commits, one per publish, so no run list and no
marker artifact is needed. A publish that fails partway leaves the record as it was, or, where
the link is known, records the link with nothing published, so the next run publishes the whole
edition to the same artifact instead of making a second one.

    python3 tools/textbook_publish.py inputs --root . --sha HEAD
    python3 tools/textbook_publish.py admit --state state.json --inputs HEX --sha SHA ...
    python3 tools/textbook_publish.py plan --out textbook-out --state state.json --plan plan.json
    python3 tools/textbook_publish.py prompt --plan plan.json --sha SHA
    python3 tools/textbook_publish.py args [--model M] [--effort E] [--fallback M]
    python3 tools/textbook_publish.py answer --execution-file F --out answer.json
    python3 tools/textbook_publish.py record --state state.json --plan plan.json --answer answer.json ...
    python3 tools/textbook_publish.py local [--work FOLDER] [--no-launch] [--record] [--anyway]
"""

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What the book is built from: the paths the workflow's push filter names, in the same order, so
# the fingerprint and the trigger agree (tests/test_textbook_publish.py holds them together). The
# site reads the chapters and figures, the synthesis's records and the exported artifacts under
# artifacts/, its own code and the stylesheet, and CODEOWNERS for the login its privacy pass hides.
# Its code is every module of tools/ the two builders import, the claims register's queue and the
# book's search among them, and the search's package, which tools/rag.py loads by path; a test
# follows the builders' imports and fails on one this list leaves out, since a change to it alone
# would otherwise republish nothing (issue #269).
FILTER = ["docs/textbook/**", "artifacts/**", "tools/textbook_site.py", "tools/textbook_artifact.py",
          "tools/living_docs.py", ".github/CODEOWNERS", "tools/claims_rank.py", "tools/rag.py",
          "src/schwingnet/rag.py"]
INPUTS = [path.removesuffix("/**") for path in FILTER]
SCHEMA = "textbook-artifact/1"
# What the pages may use of the viewer's: Ask Claude's sample, and the GitHub connector's two tools behind
# Run as me and a panel's read (docs/research/experiments-panel.md, section 4). A redeploy that passes none
# keeps what the artifact has, so they go with the first publish and again only when the record's differ.
CAPABILITIES = {"sample": {}, "mcp": {"servers": [{"server": "GitHub", "tools": ["actions_run_trigger", "get_file_contents"]}]}}
# What the pages keep where the publish refuses the connector's entry (an account with no GitHub connector,
# or a server name the control plane does not take): Ask Claude alone, the dispatcher answering "no
# connector" and every figure its fallback. The record keeps what was applied, so the next publish offers
# the connector again and the pages gain it once the account has it.
BASIC_CAPABILITIES = {"sample": {}}
REFUSED = "CAPABILITIES_REFUSED"
BRANCH = "textbook-artifact"
STATE_FILE = "state.json"
PAGE = "index.html"
OUT_REL = "textbook-out"           # the edition's folder inside the checkout, where the Artifact tool reads it
PER_PUBLISH_FILES = 240            # the tool takes 255 entries a publish
PER_PUBLISH_BYTES = 60 * 1024 * 1024    # and 64 MB
CAP_DEFAULT, CAP_MOST = 12, 50
TURNS = 40
TOOLS = "Artifact,Read"
TITLE = "SchwingNet Textbook"
DESCRIPTION = ("The SchwingNet textbook, built from the repository's records and exported artifacts "
               "and republished after each merge.")
URL = re.compile(r"^https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9_-]+$")
NAME = re.compile(r"^[a-z0-9][a-z0-9.-]*$")
EFFORTS = ("low", "medium", "high", "max")
NOT_PUBLISHED = {"batches.json", "plan.json"}
# What the command local keeps in its work folder, outside the clone: the session's instructions, the
# marker lines it writes back, what the record needs once it ends, and a small repository of the
# command's own for the record (record_repo says why).
REPO_NAME = "OpenSpineConsortium/SchwingNet"
PROMPT_FILE, ANSWER_FILE, META_FILE, RECORD_GIT = "prompt.txt", "answer.txt", "edition.json", "record.git"
LOCAL_ASK = "Read the file prompt.txt in this folder and do exactly what it says."


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_state(path):
    """The record as the branch holds it, or an empty one where the branch, the file or its
    JSON is not there yet; a record of another schema is read as empty, so a later schema
    republishes everything once."""
    if not path:
        return {}
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        return {}
    return state


# inputs

def inputs_fingerprint(root, sha):
    """The sha256 of git's listing of the book's inputs at a commit, every blob's hash and path:
    two commits that hold the same inputs give the same fingerprint, whatever else they changed,
    and a run whose fingerprint the record already carries has nothing new to publish."""
    listing = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", sha, "--", *INPUTS],
                             capture_output=True, text=True, check=True).stdout
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


# admit

def cap_of(text):
    """The day's cap from the variable: its default when unset or not a number, and never over
    the most this workflow allows."""
    try:
        value = int(str(text).strip())
    except ValueError:
        return CAP_DEFAULT
    return max(1, min(value, CAP_MOST))


def publishes_today(commits, today):
    """How many publishes the state branch records today, in UTC: its commits of the day whose
    message says an edition was published; a commit that only moved the fingerprint is none."""
    count = 0
    for commit in commits or []:
        inner = commit.get("commit") or {}
        when = ((inner.get("committer") or {}).get("date") or "")[:10]
        if when == today and str(inner.get("message", "")).startswith("Edition "):
            count += 1
    return count


def admit(state, inputs, event, switch, crowd, token, cap, commits, today):
    """Whether this run may build and publish, and the first reason it may not: the switch, crowd
    mode, the token, nothing new since the published edition (a Run workflow builds anyway, so a
    person can republish after a publish that failed partway), and the day's cap."""
    if str(switch).strip().lower() == "off":
        return False, "the variable TEXTBOOK_ARTIFACT is off"
    if str(crowd).strip().lower() == "true":
        return False, "crowd mode is on (the variable CLAUDE_CROWD), and no workflow runs Claude in it"
    if str(token).strip().lower() != "true":
        return False, "the secret CLAUDE_CODE_OAUTH_TOKEN is not set"
    if event != "workflow_dispatch" and state.get("inputs") and state.get("inputs") == inputs:
        return False, (f"the edition built from {state.get('sha', '')[:7]} is already published and the book's "
                       f"inputs have not changed since")
    done = publishes_today(commits, today)
    if done >= cap:
        return False, f"{done} publishes today reached the day's cap of {cap} (the variable TEXTBOOK_PUBLISHES_PER_DAY)"
    return True, f"{done} of {cap} publishes today"


# plan

def edition_files(out):
    """Every file of the edition by its path inside the folder, with its hash and size; the
    summaries the builders write are not pages of the book."""
    out = Path(out)
    files = {}
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(out).as_posix()
        if rel in NOT_PUBLISHED:
            continue
        files[rel] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    return files


def batched(paths, sizes, removed):
    """The paths grouped under the per-publish limits, in the order given, the removals in the
    first group, where they count as entries too."""
    groups, group, count, size = [], [], len(removed), 0
    for rel in paths:
        if group and (count >= PER_PUBLISH_FILES or size + sizes[rel] > PER_PUBLISH_BYTES):
            groups.append(group)
            group, count, size = [], 0, 0
        group.append(rel)
        count += 1
        size += sizes[rel]
    if group or removed:
        groups.append(group)
    return [{"n": i + 1, "files": g, "remove": list(removed) if i == 0 else [],
             "bytes": sum(sizes[r] for r in g)} for i, g in enumerate(groups)]


def plan(out, state):
    """What to publish: the paths whose bytes differ from the record's, the record's paths the
    edition no longer has, grouped under the limits, with the page in the first batch whenever
    anything is published, and the hashes the new record will hold."""
    files = edition_files(out)
    if PAGE not in files:
        raise SystemExit(f"{out}: no {PAGE}; not an edition tools/textbook_artifact.py built")
    before = state.get("files") or {}
    changed = [rel for rel, f in files.items() if before.get(rel) != f["sha256"] and rel != PAGE]
    removed = sorted(rel for rel in before if rel not in files)
    page_changed = before.get(PAGE) != files[PAGE]["sha256"]
    nothing = not changed and not removed and not page_changed
    sizes = {rel: f["bytes"] for rel, f in files.items()}
    batches = [] if nothing else batched(changed, sizes, removed)
    if not nothing and not batches:
        batches = [{"n": 1, "files": [], "remove": [], "bytes": 0}]
    first = not state.get("url")
    capabilities = CAPABILITIES if first or state.get("capabilities") != CAPABILITIES else None
    return {"first": first, "url": state.get("url", ""), "page": PAGE, "root": OUT_REL, "capabilities": capabilities,
            "nothing": nothing, "batches": batches, "changed": len(changed) + int(page_changed),
            "removed": len(removed), "unchanged": len(files) - len(changed) - int(page_changed),
            "total_files": len(files), "total_bytes": sum(sizes.values()),
            "files": {rel: f["sha256"] for rel, f in files.items()}}


# prompt and args

def opening(answer):
    """Where the session runs and what it may touch: a run in Actions writes nothing, and a session on
    the owner's computer writes the answer file alone, since no execution file carries its answer back."""
    if not answer:
        return [
            "You are publishing a confidential book, the SchwingNet textbook, as one private claude.ai artifact from a",
            "GitHub Actions run, with the Artifact tool, in the batches below. Do these steps in order and nothing",
            "else: call no other tool than Artifact (and Read, only to read the plan again if you must), write no",
            "file, quote nothing of the book's pages in your answer, and never publish from any other folder.",
        ]
    return [
        "You are publishing a confidential book, the SchwingNet textbook, as one private claude.ai artifact from the",
        "owner's computer, with the Artifact tool, in the batches below. Do these steps in order and nothing else:",
        "call no other tool than Artifact, Read (only to read the plan again if you must) and Write (only for the",
        f"answer file, {answer}), write no other file, quote nothing of the book's pages in your answer, and never",
        "publish from any other folder.",
    ]


def prompt(plan_, sha, folder="", answer=""):
    """The session's instructions, mechanical: the tool calls in order with their arguments, the
    marker lines its answer ends with, and nothing of the book but the paths of its files. The
    folder is where the edition is, absolute where the caller gives it; the answer file, which the
    command local gives, is where a session on the owner's computer writes those marker lines."""
    label = f"Edition {sha[:7]}"
    root = folder or plan_["root"]
    page = f"{root}/{plan_['page']}"
    if answer:
        missing = (f"If the Artifact tool is not among your tools, write the line ARTIFACT_TOOL_MISSING to {answer},\n"
                   "tell the person to type /exit, and stop.")
    else:
        missing = "If the Artifact tool is not among your tools, print the line ARTIFACT_TOOL_MISSING and stop."
    lines = opening(answer) + [
        "",
        f"The edition's files are under {root}/ in the working directory, {plan_['total_files']} files in all; the",
        f"page is {page}, which every publish names as file_path with root {root}, and the other files are passed",
        f"in files as a map of each path to the same path (relative to root). The plan is {root}/plan.json.",
        "",
        missing,
        "",
    ]
    if plan_["first"]:
        lines += [
            "This is the first publish, so there is no artifact yet.",
            f"1. Publish batch 1: action publish, file_path {page}, root {root}, title \"{TITLE}\", icon book,",
            f"   description \"{DESCRIPTION}\", capabilities {json.dumps(CAPABILITIES)}, label \"{label}\", and files",
            "   mapping each path of batch 1 to itself. The result gives the artifact's url; use it in every later call.",
            "2. For each later batch, in order: action publish with that url, the same file_path and root, the",
            "   label, and files mapping each path of the batch to itself; no icon, title, description or capabilities.",
        ]
    else:
        if plan_.get("capabilities"):
            keep = [f"   null, and on the first of them alone capabilities {json.dumps(plan_['capabilities'])}, since the",
                    "   artifact's capabilities changed; pass no icon, title or description, so the artifact keeps what it has. If a"]
        else:
            keep = ["   null. Pass no capabilities, icon, title or description, so the artifact keeps what it has. If a"]
        lines += [
            f"The artifact exists: {plan_['url']}",
            "1. Action read with that url (a publish to an artifact this session has not read is refused).",
            "2. Action list with scope files and that url, so the paths about to be replaced are ones you listed.",
            f"3. For each batch, in order: action publish with that url, file_path {page}, root {root}, label",
            f"   \"{label}\", and files mapping each path of the batch to itself, with each path to remove mapped to",
            *keep,
            "   publish is refused for paths you have not read or listed, publish that batch again with those paths,",
            "   and only those, in overwrite_unread.",
        ]
    if plan_.get("first") or plan_.get("capabilities"):
        lines += [
            "If the publish that carries capabilities is refused for them (the mcp entry or its server), make that",
            f"publish again with capabilities {json.dumps(BASIC_CAPABILITIES)} instead, carry on, and print a line {REFUSED}",
            "before the last line.",
        ]
    lines += [
        "If a publish fails, try that batch once more. If it fails again, stop and print a line",
        "PUBLISH_INCOMPLETE=<n> of <m> naming the batch that failed, before the last line.",
        "Whatever happened after the first publish, the last line of your answer is ARTIFACT_URL=<url>, the",
        "artifact's url and nothing else on that line.",
    ]
    if answer:
        lines += [
            f"Last of all, write the marker lines of your answer to {answer} with the Write tool, one to a line and",
            f"nothing else: {REFUSED} and PUBLISH_INCOMPLETE=<n> of <m> where they apply, and last ARTIFACT_URL=<url>.",
            "Then tell the person the artifact's url, and that typing /exit lets the command that opened this session",
            "record the edition.",
        ]
    lines.append("")
    for batch in plan_["batches"]:
        lines.append(f"Batch {batch['n']} of {len(plan_['batches'])}: {len(batch['files'])} files, {batch['bytes']} bytes"
                     + (f", {len(batch['remove'])} to remove" if batch["remove"] else ""))
        lines += [f"  {rel}" for rel in batch["files"]]
        lines += [f"  remove: {rel}" for rel in batch["remove"]]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def args_lines(model="", effort="", fallback=""):
    """The session's claude_args: its turns, the model, effort and fallback the pool's settings
    give where they are plain names, the user's settings alone, so no file of the repository's
    adds a hook or an instruction, and the two tools it may use."""
    lines = [f"--max-turns {TURNS}"]
    if model and NAME.match(model):
        lines.append(f"--model {model}")
    if effort in EFFORTS:
        lines.append(f"--effort {effort}")
    if fallback and NAME.match(fallback) and fallback != model:
        lines.append(f"--fallback-model {fallback}")
    lines += ["--permission-mode default", "--setting-sources user", f'--allowedTools "{TOOLS}"']
    return lines


# answer and record

def result_text(execution_file):
    """The session's last answer from the action's execution file, a JSON list of messages whose
    last entry of type result carries the text; an empty string where there is none."""
    try:
        messages = json.loads(Path(execution_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if isinstance(messages, dict):
        messages = [messages]
    text = ""
    for message in messages if isinstance(messages, list) else []:
        if isinstance(message, dict) and message.get("type") == "result":
            text = str(message.get("result") or "")
    return text


def answer_of(text):
    """What the answer says, read from its marker lines alone: the artifact's link from the last
    non-empty line, whether the tool was missing, which batch failed, where one did, and whether the
    connector's capability was refused."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    found = {"url": "", "missing_tool": False, "incomplete": "", "capabilities_refused": False}
    for line in lines:
        if line == "ARTIFACT_TOOL_MISSING":
            found["missing_tool"] = True
        elif line == REFUSED:
            found["capabilities_refused"] = True
        elif line.startswith("PUBLISH_INCOMPLETE="):
            found["incomplete"] = line.split("=", 1)[1].strip()
    if lines and lines[-1].startswith("ARTIFACT_URL="):
        url = lines[-1].split("=", 1)[1].strip()
        if URL.match(url):
            found["url"] = url
    return found


def record(state, plan_, answer, sha, built, inputs, run):
    """The record a run leaves, and the message of its commit: a whole publish records the
    edition and every hash; one that failed partway records the link with nothing published, so
    the next run publishes everything to the same artifact; a run that found nothing to publish
    moves the fingerprint alone. The record is refused, and the run fails, where the session
    reports no link or another artifact's link than the one recorded, which a person settles."""
    if answer.get("nothing"):
        if not state.get("url"):
            raise SystemExit("nothing to publish and no artifact recorded; the first edition is published by a run "
                             "that finds the book changed, or by Run workflow")
        new = dict(state, inputs=inputs, run=run)
        return new, f"Inputs at {sha[:7]}: nothing to publish"
    if answer.get("missing_tool"):
        raise SystemExit("the session had no Artifact tool (ARTIFACT_TOOL_MISSING): the publish cannot run from Actions "
                         "with this action and token, and nothing was recorded")
    url = answer.get("url", "")
    if not url:
        raise SystemExit("the session's answer ends with no ARTIFACT_URL line, so nothing is known to have been "
                         "published; nothing was recorded")
    if state.get("url") and state["url"] != url:
        raise SystemExit(f"the session published to {url}, not to the recorded artifact {state['url']}; nothing was "
                         "recorded, and a person decides which artifact stays")
    if answer.get("incomplete"):
        new = {"schema": SCHEMA, "url": url, "sha": "", "built": "", "inputs": "", "run": run, "files": {},
               "incomplete": answer["incomplete"]}
        return new, f"Edition {sha[:7]}: incomplete ({answer['incomplete']}); the next run publishes it whole"
    new = {"schema": SCHEMA, "url": url, "sha": sha, "built": built, "inputs": inputs, "run": run,
           "files": plan_["files"], "capabilities": BASIC_CAPABILITIES if answer.get("capabilities_refused") else CAPABILITIES}
    message = (f"Edition {sha[:7]}: {plan_['changed']} files published, {plan_['removed']} removed, "
               f"{plan_['unchanged']} unchanged")
    return new, message


# local: the same publish from the owner's computer, where Claude Code carries the Artifact tool

def git_out(where, *args, stdin=None):
    """git's output in a repository, stripped, or a stop that quotes git's own words; the input goes
    as bytes, so no platform turns its line ends into others."""
    done = subprocess.run(["git", "-C", str(where), *args], capture_output=True,
                          input=None if stdin is None else stdin.encode("utf-8"))
    if done.returncode != 0:
        words = (done.stderr or done.stdout).decode("utf-8", "replace").strip()
        raise SystemExit(f"git {args[0]} failed: {words}")
    return done.stdout.decode("utf-8", "replace").strip()


def remote_url(clone):
    """Where the clone fetches from, read again whenever it is needed and never written down."""
    return git_out(clone, "remote", "get-url", "origin")


def record_repo(work):
    """The small repository of the command's own, in the work folder, that reads and writes the
    record. The clone's pre-push hook runs the gate on the checked-out tree and refuses to push any
    other commit, and the record's one file is no part of that tree, so the record leaves from here,
    as the workflow's record job writes it from a runner."""
    repo = Path(work) / RECORD_GIT
    if not (repo / "HEAD").is_file():
        git_out(work, "init", "--quiet", "--bare", RECORD_GIT)
    return repo


def record_head(repo, remote):
    """The branch's head on the remote, fetched into the record's repository, or "" where the branch
    is not there yet; a remote that cannot be read stops the command, since a record read wrong
    would make a second artifact."""
    if not git_out(repo, "ls-remote", "--heads", remote, f"refs/heads/{BRANCH}"):
        return ""
    git_out(repo, "fetch", "--quiet", "--no-tags", remote, f"+refs/heads/{BRANCH}:refs/heads/{BRANCH}")
    return git_out(repo, "rev-parse", f"refs/heads/{BRANCH}")


def recorded_state(work, remote):
    """The record as the branch holds it, kept in the work folder as state.json, or an empty one
    where the branch or its file is not there yet."""
    repo = record_repo(work)
    path = Path(work) / STATE_FILE
    path.unlink(missing_ok=True)
    head = record_head(repo, remote)
    if not head:
        return {}
    shown = subprocess.run(["git", "-C", str(repo), "show", f"{head}:{STATE_FILE}"], capture_output=True)
    if shown.returncode != 0:
        return {}
    path.write_bytes(shown.stdout)
    return load_state(path)


def write_record(work, remote, new, message):
    """The record onto the branch as one commit on its head, pushed without force, so the push goes
    through only while the branch is still that head: a branch that moved meanwhile is read again
    once, and a branch that holds anything but state.json is the project's own and never replaced."""
    repo = record_repo(work)
    body = json.dumps(new, indent=1, sort_keys=True) + "\n"
    for _attempt in range(2):
        previous = record_head(repo, remote)
        if previous:
            names = git_out(repo, "ls-tree", "--name-only", previous).splitlines()
            foreign = [name for name in names if name != STATE_FILE]
            if foreign:
                raise SystemExit(f"the branch {BRANCH} holds files the record does not write ({', '.join(foreign)}); "
                                 "it is the project's own and stays as it is, so nothing was recorded")
        blob = git_out(repo, "hash-object", "-w", "--stdin", stdin=body)
        tree = git_out(repo, "mktree", stdin=f"100644 blob {blob}\t{STATE_FILE}\n")
        commit = git_out(repo, "commit-tree", tree, *(["-p", previous] if previous else []), stdin=message + "\n")
        pushed = subprocess.run(["git", "-C", str(repo), "push", "--quiet", remote, f"{commit}:refs/heads/{BRANCH}"],
                                capture_output=True)
        if pushed.returncode == 0:
            return commit
        if record_head(repo, remote) == previous:
            words = pushed.stderr.decode("utf-8", "replace").strip()
            raise SystemExit(f"the push of the record failed: {words}; nothing was recorded")
    raise SystemExit(f"the branch {BRANCH} moved twice while the record was written; nothing was recorded, and "
                     "the command's --record writes it again")


def drop_tree(clone, tree):
    """A build's worktree gone, from the clone's list and from the disk, whatever state it was left in."""
    subprocess.run(["git", "-C", str(clone), "worktree", "remove", "--force", str(tree)], capture_output=True)
    shutil.rmtree(tree, ignore_errors=True)
    subprocess.run(["git", "-C", str(clone), "worktree", "prune"], capture_output=True)


def run_builder(script, *args):
    done = subprocess.run([sys.executable, str(script), *map(str, args)])
    if done.returncode != 0:
        raise SystemExit(f"{script.name} failed; nothing was published")


def build(clone, sha, built, work):
    """The site and the edition from a commit, by that commit's own builders in a worktree of the
    clone made in the work folder, as the workflow builds from its checkout; the worktree and the
    site go again, and the edition stays in the folder for the session."""
    work = Path(work)
    tree, site, out = work / "tree", work / "site", work / OUT_REL
    drop_tree(clone, tree)
    shutil.rmtree(site, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    git_out(clone, "worktree", "add", "--quiet", "--detach", str(tree), sha)
    try:
        run_builder(tree / "tools" / "textbook_site.py", site, "--repo", REPO_NAME, "--sha", sha, "--root", tree)
        run_builder(tree / "tools" / "textbook_artifact.py", site, out, "--repo", REPO_NAME, "--sha", sha,
                    "--built", built)
    finally:
        drop_tree(clone, tree)
        shutil.rmtree(site, ignore_errors=True)
    return out


def default_work(clone):
    """The work folder beside the clone, so the session there loads none of the repository's files."""
    clone = Path(clone).resolve()
    return clone.parent / f"{clone.name}-textbook-edition"


def open_session(command, work):
    """Claude Code in the work folder on the one line that sends it to the prompt, until the person
    leaves it; file edits are accepted, so its one write, the answer file, asks nothing."""
    subprocess.run([command, "--permission-mode", "acceptEdits", LOCAL_ASK], cwd=work)


def steps_by_hand(work):
    script = Path(__file__).resolve()
    return (f"The edition is ready in {work}. Two steps publish it:\n"
            "1. Open Claude Code in that folder, signed in to the claude.ai account that keeps the book, and type:\n"
            f"   {LOCAL_ASK}\n"
            "2. When it has given the link and you have left it, record the edition:\n"
            f"   python3 {script} local --record --work {work}\n")


def local_publish(clone, work, claude="claude", launch=True, anyway=False):
    """The whole publish from this computer: main's commit fetched, the record read, a stop where
    the book's inputs are the ones already published, the edition built and planned in the work
    folder, and Claude Code opened there on the prompt, its answer recorded once the person leaves
    it. Where Claude Code is not found, or the launch is declined, the folder is left ready and the
    two steps are printed."""
    clone, work = Path(clone).resolve(), Path(work).resolve()
    if work == clone or clone in work.parents:
        raise SystemExit(f"{work} is inside the clone; the edition is built outside it, so the session there loads "
                         "none of the repository's files")
    git_out(clone, "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
    sha = git_out(clone, "rev-parse", "refs/remotes/origin/main")
    built = git_out(clone, "show", "-s", "--format=%cI", sha)
    inputs = inputs_fingerprint(clone, sha)
    work.mkdir(parents=True, exist_ok=True)
    state = recorded_state(work, remote_url(clone))
    if state.get("inputs") and state.get("inputs") == inputs and not anyway:
        print(f"The edition built from {state.get('sha', '')[:7]} is already published at {state.get('url', '')}, and "
              "the book's inputs have not changed since; --anyway publishes it again.")
        return 0
    out = build(clone, sha, built, work)
    plan_ = plan(out, state)
    (out / "plan.json").write_text(json.dumps(plan_, indent=1) + "\n", encoding="utf-8")
    meta = {"clone": str(clone), "sha": sha, "built": built, "inputs": inputs}
    (work / META_FILE).write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    (work / ANSWER_FILE).unlink(missing_ok=True)
    if plan_["nothing"]:
        return finish(work, {"nothing": True})
    text = prompt(plan_, sha, out.as_posix(), (work / ANSWER_FILE).as_posix())
    (work / PROMPT_FILE).write_text(text, encoding="utf-8")
    found = shutil.which(claude) if launch else None
    if not found:
        print(steps_by_hand(work), end="")
        return 0
    open_session(found, work)
    return finish(work)


def answer_in(work):
    """What the session wrote to the answer file, refused where it wrote none or had no Artifact tool."""
    path = Path(work) / ANSWER_FILE
    try:
        found = answer_of(path.read_text(encoding="utf-8"))
    except OSError:
        raise SystemExit(f"the session wrote no {ANSWER_FILE}, so nothing is known to have been published and nothing "
                         f"was recorded; if it did publish, write the line ARTIFACT_URL=<its link> to {path} and run "
                         "this command again with --record") from None
    if found["missing_tool"]:
        raise SystemExit("the session had no Artifact tool (ARTIFACT_TOOL_MISSING): Claude Code carries it only when "
                         "it is signed in to a claude.ai account on a paid plan, so type /login in Claude Code, choose "
                         "that account and run this command again; nothing was recorded")
    return found


def finish(work, answer=None, now=None):
    """The record of what the session in the work folder answered, onto the branch, and the link;
    the edition's files leave the folder once the record holds what was published."""
    work = Path(work).resolve()
    try:
        meta = json.loads((work / META_FILE).read_text(encoding="utf-8"))
        plan_ = json.loads((work / OUT_REL / "plan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(f"{work} holds no edition waiting for its record; run the command without --record "
                         "first") from None
    if answer is None:
        answer = answer_in(work)
    when = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    new, message = record(load_state(work / STATE_FILE), plan_, answer, meta["sha"], meta["built"], meta["inputs"],
                          f"local {when}")
    write_record(work, remote_url(meta["clone"]), new, message)
    shutil.rmtree(work / OUT_REL, ignore_errors=True)
    (work / ANSWER_FILE).unlink(missing_ok=True)
    print(message)
    if new.get("url"):
        print(new["url"])
    return 0


# the command

def output(key, value):
    print(f"{key}={value}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    fingerprint = commands.add_parser("inputs", help="the fingerprint of the book's inputs at a commit")
    fingerprint.add_argument("--root", default=".")
    fingerprint.add_argument("--sha", default="HEAD")

    admitting = commands.add_parser("admit", help="whether this run may build and publish, as step outputs")
    admitting.add_argument("--state", default="", help="state.json as the branch holds it, or nothing")
    admitting.add_argument("--inputs", required=True)
    admitting.add_argument("--event", default="")
    admitting.add_argument("--switch", default="")
    admitting.add_argument("--crowd", default="")
    admitting.add_argument("--token", default="")
    admitting.add_argument("--cap", default="")
    admitting.add_argument("--commits", default="", help="the branch's commits of the day, as the API lists them")
    admitting.add_argument("--today", default="", help="the UTC date, for tests")
    admitting.add_argument("--words", default="", help="where to write the summary's line")

    planning = commands.add_parser("plan", help="what changed since the record, in batches")
    planning.add_argument("--out", required=True)
    planning.add_argument("--state", default="")
    planning.add_argument("--plan", required=True)

    prompting = commands.add_parser("prompt", help="the session's instructions, as a step output")
    prompting.add_argument("--plan", required=True)
    prompting.add_argument("--sha", required=True)
    prompting.add_argument("--folder", default="", help="where the edition is on the runner, absolute")

    arguments = commands.add_parser("args", help="the session's claude_args, as a step output")
    arguments.add_argument("--model", default="")
    arguments.add_argument("--effort", default="")
    arguments.add_argument("--fallback", default="")

    answering = commands.add_parser("answer", help="what the session's answer says, as a small file")
    answering.add_argument("--execution-file", required=True)
    answering.add_argument("--out", required=True)

    recording = commands.add_parser("record", help="the record the run leaves on the branch")
    recording.add_argument("--state", default="")
    recording.add_argument("--plan", required=True)
    recording.add_argument("--answer", required=True)
    recording.add_argument("--sha", required=True)
    recording.add_argument("--built", required=True)
    recording.add_argument("--inputs", required=True)
    recording.add_argument("--run", default="")
    recording.add_argument("--write", required=True)
    recording.add_argument("--message", required=True, help="where to write the commit's message")

    local = commands.add_parser("local", help="the publish from this computer, where Claude Code has the Artifact tool")
    local.add_argument("--clone", default=str(ROOT), help="the clone to build from, this one by default")
    local.add_argument("--work", default="", help="the folder to build in, outside the clone; beside it by default")
    local.add_argument("--claude", default="claude", help="the command that opens Claude Code")
    local.add_argument("--no-launch", action="store_true", help="leave the folder ready and print the two steps")
    local.add_argument("--anyway", action="store_true", help="publish even where these inputs are already published")
    local.add_argument("--record", action="store_true", help="record what the session answered, after it ran by hand")

    args = parser.parse_args(argv)
    if args.command == "inputs":
        output("inputs", inputs_fingerprint(args.root, args.sha))
    elif args.command == "admit":
        commits = []
        if args.commits:
            try:
                commits = json.loads(Path(args.commits).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                commits = []
        today = args.today or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        ok, why = admit(load_state(args.state), args.inputs, args.event, args.switch, args.crowd, args.token,
                        cap_of(args.cap), commits if isinstance(commits, list) else [], today)
        output("admit", "true" if ok else "false")
        output("why", why)
        if args.words:
            verb = "publishes" if ok else "does not publish"
            Path(args.words).write_text(f"This run {verb}: {why}.\n", encoding="utf-8")
    elif args.command == "plan":
        plan_ = plan(args.out, load_state(args.state))
        Path(args.plan).write_text(json.dumps(plan_, indent=1) + "\n", encoding="utf-8")
        for key in ("nothing", "first", "changed", "removed", "unchanged", "total_files", "total_bytes"):
            output(key, str(plan_[key]).lower())
        output("batches", str(len(plan_["batches"])))
    elif args.command == "prompt":
        plan_ = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        text = prompt(plan_, args.sha, args.folder)
        print("prompt<<TEXTBOOK_PROMPT")
        print(text, end="")
        print("TEXTBOOK_PROMPT")
    elif args.command == "args":
        print("args<<TEXTBOOK_ARGS")
        print("\n".join(args_lines(args.model, args.effort, args.fallback)))
        print("TEXTBOOK_ARGS")
    elif args.command == "answer":
        found = answer_of(result_text(args.execution_file))
        Path(args.out).write_text(json.dumps(found, indent=1) + "\n", encoding="utf-8")
        output("url", found["url"])
        if found["missing_tool"]:
            print("::error::the session had no Artifact tool (ARTIFACT_TOOL_MISSING); the publish cannot run from "
                  "Actions with this action and token", file=sys.stderr)
            return 1
        if not found["url"]:
            print("::error::the session's answer ends with no ARTIFACT_URL line; nothing is known to have been "
                  "published", file=sys.stderr)
            return 1
        if found["incomplete"]:
            print(f"::warning::the publish stopped at batch {found['incomplete']}; the next run publishes the whole "
                  "edition to the same artifact", file=sys.stderr)
    elif args.command == "record":
        plan_ = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        answer = json.loads(Path(args.answer).read_text(encoding="utf-8"))
        new, message = record(load_state(args.state), plan_, answer, args.sha, args.built, args.inputs, args.run)
        Path(args.write).write_text(json.dumps(new, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        Path(args.message).write_text(message + "\n", encoding="utf-8")
        output("url", new.get("url", ""))
        output("published", "true" if message.startswith("Edition ") else "false")
    elif args.command == "local":
        work = args.work or default_work(args.clone)
        if args.record:
            return finish(work)
        return local_publish(args.clone, work, args.claude, not args.no_launch, args.anyway)
    return 0


if __name__ == "__main__":
    sys.exit(main())
