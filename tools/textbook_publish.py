"""The publish of the textbook's reader, the one small claude.ai artifact that shows the book, from
the owner's computer (issues #236, #277 and #294): the page from main's commit, the prompt that
tells Claude Code exactly what to publish, and the record left on the branch textbook-artifact.

The owner decided on 2026-10-24 that the book is also one private claude.ai artifact (#236). A
GitHub Action could not publish it, since the session claude-code-action starts has no Artifact
tool (#277), and on 2026-10-25 the session on the owner's computer published nothing either, as it
should: the Artifact tool publishes a file Claude did not write only once Claude has read the whole
of it, and the edition is about 450 files and 109 MB (docs/research/textbook-as-an-artifact.md). So
the owner chose, the same day, a reader (#294): tools/textbook_reader.html, one page small enough
to read in full, which holds no part of the book and, when it is opened, reads the book from the
files of the Claude project the textbook thread belongs to, with the viewer's own access, through
the artifact runtime's files capability; a thread of that project copies the book there with
`python3 tools/textbook_reader.py stage`. The page is published once and again only when it
changes, not when the book does.

This command publishes it: it fetches main, takes the page from main's commit into a folder beside
the clone, stops where the page and its capabilities are the ones already published, opens Claude
Code there on a mechanical prompt that has it read the page whole and then publish it, and records
the session's answer on the branch once the person leaves it. The record is one file, state.json,
on the branch textbook-artifact, written by fast-forward commits alone: the artifact's link, the
commit the page came from, the page's sha256 and the capabilities it was published with.

    python3 tools/textbook_publish.py local [--work FOLDER] [--no-launch] [--record] [--anyway]
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_NAME = "OpenSpineConsortium/SchwingNet"
PAGE_SOURCE = "tools/textbook_reader.html"
PAGE = "reader.html"                # the page's name in the work folder, where the Artifact tool reads it
SCHEMA = "textbook-reader-page/1"
# The Claude project whose files hold the book: the project the textbook thread runs in, which
# tools/textbook_reader.py stage copies the book into. A project member publishes; a viewer who
# cannot open the project's files reads nothing. On 2026-10-25 the work moved to another Claude
# account and its own project, so the id is that project's; the old account's reader keeps the old one.
PROJECT = "chan_017oGDcW5qgxYtogE2Rbh26i"
# What the reader uses of the viewer's: the project's files, and sample, which the book's own pages
# reach through the reader for Ask Claude and Ask the book. No connector: a figure's Run as me
# answers "no connector" here and its prefilled issue still works.
CAPABILITIES = {"files": {"project": PROJECT}, "sample": {}}
REFUSED = "CAPABILITIES_REFUSED"
BRANCH = "textbook-artifact"
STATE_FILE = "state.json"
TITLE = "SchwingNet Textbook"
DESCRIPTION = "The SchwingNet textbook, read from the SchwingNet Claude project's files when it is opened."
URL = re.compile(r"^https://claude\.ai/(?:code/)?artifact/[A-Za-z0-9_-]+$")
# What the command keeps in its work folder, outside the clone: the session's instructions, the
# marker lines it writes back, what the record needs once it ends, and a small repository of the
# command's own for the record (record_repo says why).
PROMPT_FILE, ANSWER_FILE, META_FILE, RECORD_GIT = "prompt.txt", "answer.txt", "page.json", "record.git"
LOCAL_ASK = "Read the file prompt.txt in this folder and do exactly what it says."
# The interpreter's name in the steps the command prints: on Windows python3 may be the Store's stub.
PYTHON = "python" if os.name == "nt" else "python3"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_state(path):
    """The record as the branch holds it, or an empty one where the branch, the file or its
    JSON is not there yet; a record of another schema, such as the edition's of #236, is read as
    empty, so the reader is published as a new artifact once."""
    if not path:
        return {}
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        return {}
    return state


def plan(page, state, capabilities=None):
    """What to publish: nothing where the record holds this page and these capabilities; else the
    page, as a new artifact where the record has no link, with the capabilities on a first publish
    and again only when the record's differ, since a redeploy that passes none keeps what it has."""
    capabilities = capabilities or CAPABILITIES
    digest = sha256(page)
    first = not state.get("url")
    nothing = not first and state.get("page") == digest and state.get("capabilities") == capabilities
    return {"first": first, "url": state.get("url", ""), "nothing": nothing, "page": digest,
            "bytes": Path(page).stat().st_size,
            "capabilities": capabilities if first or state.get("capabilities") != capabilities else None}


# prompt

def prompt(plan_, sha, page, answer):
    """The session's instructions, mechanical: read the page whole, then the tool calls in order
    with their arguments, and the marker lines its answer ends with and writes to the answer file."""
    label = f"Reader {sha[:7]}"
    lines = [
        "You are publishing the reader of a confidential book, the SchwingNet textbook, as one private claude.ai",
        "artifact from the owner's computer, with the Artifact tool. Do these steps in order and nothing else: call",
        f"no other tool than Artifact, Read and Write (only for the answer file, {answer}), write no other file, and",
        f"publish nothing but {page}.",
        "",
        f"The page is {page}, {plan_['bytes']} bytes of HTML that hold no part of the book: when it is opened it",
        f"reads the book from the files of the Claude project {PROJECT}, with the viewer's own access.",
        "",
        f"If the Artifact tool is not among your tools, write the line ARTIFACT_TOOL_MISSING to {answer}, tell the",
        "person to type /exit, and stop.",
        "",
        f"1. Read {page} with the Read tool, the whole of it, before any publish.",
    ]
    capabilities = json.dumps(plan_["capabilities"]) if plan_["capabilities"] else ""
    if plan_["first"]:
        lines += [
            f"2. Publish it: action publish, file_path {page}, title \"{TITLE}\", icon book, description",
            f"   \"{DESCRIPTION}\", capabilities {capabilities}, label \"{label}\". The result gives the artifact's url.",
        ]
    else:
        keep = (f", capabilities {capabilities}, since the reader's capabilities changed" if capabilities
                else "; pass no capabilities")
        lines += [
            f"2. Action read with url {plan_['url']} (a publish to an artifact this session has not read is refused).",
            f"3. Action publish with url {plan_['url']}, file_path {page}, label \"{label}\"{keep}; pass no icon,",
            "   title or description, so the artifact keeps what it has.",
        ]
    if plan_["capabilities"]:
        lines += [
            "If the publish is refused for its capabilities, do not publish without them, since the reader shows",
            f"nothing without the project's files: write the line {REFUSED} to the answer file with the refusal's",
            "words after it on the same line, tell the person what the refusal said, and stop.",
        ]
    lines += [
        "If a publish fails for any other reason, try it once more; if it fails again, stop and say why.",
        f"Last of all, if the page was published, write the line ARTIFACT_URL=<url> to {answer} with the Write",
        "tool, the artifact's url and nothing else on that line. Then tell the person the artifact's url, and that",
        "typing /exit lets the command that opened this session record it.",
    ]
    return "\n".join(lines) + "\n"


# answer and record

def answer_of(text):
    """What the answer says, read from its marker lines alone: the artifact's link from the last
    non-empty line, whether the tool was missing, and the words of a refusal of the capabilities."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    found = {"url": "", "missing_tool": False, "refused": ""}
    for line in lines:
        if line == "ARTIFACT_TOOL_MISSING":
            found["missing_tool"] = True
        elif line.startswith(REFUSED):
            found["refused"] = line[len(REFUSED):].strip(" :=") or "no reason given"
    if lines and lines[-1].startswith("ARTIFACT_URL="):
        url = lines[-1].split("=", 1)[1].strip()
        if URL.match(url):
            found["url"] = url
    return found


def record(state, plan_, answer, sha, run):
    """The record a publish leaves, and the message of its commit; refused where the session reports
    no link, or another artifact's link than the one recorded, which a person settles."""
    if answer.get("missing_tool"):
        raise SystemExit("the session had no Artifact tool (ARTIFACT_TOOL_MISSING), and nothing was recorded")
    if answer.get("refused"):
        raise SystemExit(f"the publish was refused for the reader's capabilities ({answer['refused']}); the account "
                         f"Claude Code is signed in to must be a member of the Claude project {PROJECT}, the one whose "
                         "files hold the book; nothing was recorded")
    url = answer.get("url", "")
    if not url:
        raise SystemExit("the session's answer ends with no ARTIFACT_URL line, so nothing is known to have been "
                         "published; nothing was recorded")
    if state.get("url") and state["url"] != url:
        raise SystemExit(f"the session published to {url}, not to the recorded artifact {state['url']}; nothing was "
                         "recorded, and a person decides which artifact stays")
    capabilities = plan_["capabilities"] or state.get("capabilities") or CAPABILITIES
    new = {"schema": SCHEMA, "url": url, "sha": sha, "page": plan_["page"], "capabilities": capabilities, "run": run}
    return new, f"Reader {sha[:7]}: published"


# the publish from the owner's computer, where Claude Code carries the Artifact tool

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
    other commit, and the record's one file is no part of that tree, so the record leaves from here."""
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


def take_page(clone, sha, work):
    """The reader page as main's commit holds it, written into the work folder; the bytes are
    git's own, so the page published is the one reviewed and merged."""
    done = subprocess.run(["git", "-C", str(clone), "show", f"{sha}:{PAGE_SOURCE}"], capture_output=True)
    if done.returncode != 0:
        raise SystemExit(f"{PAGE_SOURCE} is not in main's commit {sha[:7]}; nothing was published")
    page = Path(work) / PAGE
    page.write_bytes(done.stdout)
    return page


def default_work(clone):
    """The work folder beside the clone, so the session there loads none of the repository's files."""
    clone = Path(clone).resolve()
    return clone.parent / f"{clone.name}-textbook-reader"


def open_session(command, work):
    """Claude Code in the work folder on the one line that sends it to the prompt, until the person
    leaves it; file edits are accepted, so its one write, the answer file, asks nothing."""
    subprocess.run([command, "--permission-mode", "acceptEdits", LOCAL_ASK], cwd=work)


def steps_by_hand(work):
    script = Path(__file__).resolve()
    return (f"The reader is ready in {work}. Two steps publish it:\n"
            "1. Open Claude Code in that folder, signed in to the claude.ai account that keeps the book, and type:\n"
            f"   {LOCAL_ASK}\n"
            "2. When it has given the link and you have left it, record it:\n"
            f"   {PYTHON} {script} local --record --work {work}\n")


def local_publish(clone, work, claude="claude", launch=True, anyway=False):
    """The whole publish from this computer: main's commit fetched, the record read, the page taken
    from that commit, a stop where it and its capabilities are the ones already published, and
    Claude Code opened in the work folder on the prompt, its answer recorded once the person leaves
    it. Where Claude Code is not found, or the launch is declined, the folder is left ready and the
    two steps are printed."""
    clone, work = Path(clone).resolve(), Path(work).resolve()
    if work == clone or clone in work.parents:
        raise SystemExit(f"{work} is inside the clone; the page is published from outside it, so the session there "
                         "loads none of the repository's files")
    git_out(clone, "fetch", "--quiet", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
    sha = git_out(clone, "rev-parse", "refs/remotes/origin/main")
    work.mkdir(parents=True, exist_ok=True)
    state = recorded_state(work, remote_url(clone))
    page = take_page(clone, sha, work)
    plan_ = plan(page, state)
    if plan_["nothing"] and not anyway:
        print(f"The reader is already published at {state['url']}, as main holds it; the book it shows is copied "
              "into the project's files by a thread (tools/textbook_reader.py stage). --anyway publishes it again.")
        return 0
    if plan_["nothing"]:
        plan_["nothing"] = False
    meta = {"clone": str(clone), "sha": sha, "plan": plan_}
    (work / META_FILE).write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    (work / ANSWER_FILE).unlink(missing_ok=True)
    text = prompt(plan_, sha, page.as_posix(), (work / ANSWER_FILE).as_posix())
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
    """The record of what the session in the work folder answered, onto the branch, and the link."""
    work = Path(work).resolve()
    try:
        meta = json.loads((work / META_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SystemExit(f"{work} holds no page waiting for its record; run the command without --record first") from None
    if answer is None:
        answer = answer_in(work)
    when = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    new, message = record(load_state(work / STATE_FILE), meta["plan"], answer, meta["sha"], f"local {when}")
    write_record(work, remote_url(meta["clone"]), new, message)
    (work / ANSWER_FILE).unlink(missing_ok=True)
    (work / META_FILE).unlink(missing_ok=True)
    print(message)
    print(new["url"])
    return 0


# the command

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    local = commands.add_parser("local", help="the publish from this computer, where Claude Code has the Artifact tool")
    local.add_argument("--clone", default=str(ROOT), help="the clone to take the page from, this one by default")
    local.add_argument("--work", default="", help="the folder to publish from, outside the clone; beside it by default")
    local.add_argument("--claude", default="claude", help="the command that opens Claude Code")
    local.add_argument("--no-launch", action="store_true", help="leave the folder ready and print the two steps")
    local.add_argument("--anyway", action="store_true", help="publish even where this page is already published")
    local.add_argument("--record", action="store_true", help="record what the session answered, after it ran by hand")

    args = parser.parse_args(argv)
    work = args.work or default_work(args.clone)
    if args.record:
        return finish(work)
    return local_publish(args.clone, work, args.claude, not args.no_launch, args.anyway)


if __name__ == "__main__":
    sys.exit(main())
