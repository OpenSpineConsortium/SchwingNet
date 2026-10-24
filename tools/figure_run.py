"""Answer a Re-run issue for one of the textbook's figures (.github/workflows/figure.yml, issue #215).

The textbook's Re-run button opens an issue whose body carries one fixed line, `figure-rerun-id: NN/slug`.
This tool reads that line and nothing else from the issue: the figure's committed record,
docs/textbook/figures/NN/slug.json, says what may run. An issue opened by anyone who may not write to the
repository is refused, since the button is open to every reader of the site. What happens next is the
record's rerun.where:

- actions: the record's command runs on the runner from committed files, and the workflow opens a pull
  request with what it redrew; a run that changes anything outside the figure's own chapter folder fails.
- grid: nothing is submitted. The answer gives the exact command and the link to the grid workflow, since
  a grid job waits for the owner's word and the number of jobs (docs/project.md), which an issue is not;
  the owner starts it by hand.
- none: the answer lists the figure's Explore links, the method and the data, since no command is known.

    python3 tools/figure_run.py plan --event EVENT.json --repo OWNER/NAME --run-number N --comment OUT.md
    python3 tools/figure_run.py run --id NN/slug
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIGURES = Path("docs/textbook/figures")
LABEL = "figure-rerun"
ID_LINE = re.compile(r"^figure-rerun-id:[ \t]*([0-9]{2}/[a-z0-9][a-z0-9-]{0,99})[ \t]*$", re.M)
WRITERS = {"OWNER", "MEMBER", "COLLABORATOR"}
MARKER = "<!-- figure-rerun -->"
RUN_TIMEOUT = 50 * 60


def figure_id(body):
    """The one figure id the issue's fixed line names, or None when the line is missing or given twice
    with two ids."""
    found = set(ID_LINE.findall(body or ""))
    return found.pop() if len(found) == 1 else None


def load_record(root, fid):
    """The committed record of a figure id, or None. The id is matched by the pattern above before it
    is used as a path, so no issue text can name a file outside the figures folder."""
    if not fid or not re.fullmatch(r"[0-9]{2}/[a-z0-9][a-z0-9-]{0,99}", fid):
        return None
    path = Path(root) / FIGURES / f"{fid}.json"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and record.get("id") == fid else None


def blob(repo, href):
    if re.match(r"^https://", href):
        return href
    return f"https://github.com/{repo}/blob/HEAD/{href.strip('/')}" if not href.endswith("/") else \
        f"https://github.com/{repo}/tree/HEAD/{href.strip('/')}"


def explore_lines(repo, record):
    out = []
    for item in record.get("explore") or []:
        if isinstance(item, dict) and item.get("href"):
            out.append(f"- [{item.get('label') or item['href']}]({blob(repo, item['href'])})")
    source = record.get("source") or {}
    out.append(f"- The method: {source.get('made_by') or 'not recorded'}")
    if source.get("data"):
        out.append("- The data: " + "; ".join(source["data"]))
    out.append(f"- The record: [{record['id']}.json]({blob(repo, (FIGURES / (record['id'] + '.json')).as_posix())})")
    return out


def branch_for(fid, run_number):
    return f"figure-rerun/{fid.replace('/', '-')}-{run_number}"


def decide(event, root, repo, run_number):
    """What the workflow does for one issue event: a dict with the action (skip, refuse, invalid,
    actions, grid or none), the figure id where there is one, the branch for actions, and the
    comment to post (empty for skip)."""
    action = event.get("action")
    issue = event.get("issue") or {}
    if action == "labeled" and (event.get("label") or {}).get("name") != LABEL:
        return {"action": "skip", "comment": ""}
    if action not in ("opened", "labeled"):
        return {"action": "skip", "comment": ""}
    fid = figure_id(issue.get("body"))
    if action == "opened" and fid is None and LABEL not in {l.get("name") for l in issue.get("labels") or []}:
        return {"action": "skip", "comment": ""}
    if issue.get("author_association") not in WRITERS:
        return {"action": "refuse", "comment": f"{MARKER}\nThis repository re-runs a figure only for an issue opened by "
                "someone who may write to it (its owner, a member or a collaborator). Nothing was run."}
    record = load_record(root, fid)
    if record is None:
        return {"action": "invalid", "comment": f"{MARKER}\nThe issue needs one line `figure-rerun-id: NN/slug` naming a "
                "figure whose record is committed under docs/textbook/figures/. None was found, so nothing was run."}
    rerun = record.get("rerun") or {}
    where = rerun.get("where")
    command = rerun.get("command")
    head = f"{MARKER}\nFigure `{fid}`, {record.get('title', '')}."
    if where == "actions" and command:
        return {"action": "actions", "id": fid, "branch": branch_for(fid, run_number), "command": command,
                "comment": f"{head}\n\nRunning its recorded command on a GitHub runner:\n\n```\n{command}\n```\n\n"
                           f"Cost: {rerun.get('cost') or 'not recorded'}. A pull request with what it draws follows "
                           "from this run; a pull request this workflow opens starts no check by itself, so push to it "
                           "or close and reopen it to run them."}
    if where == "grid" and command:
        grid = f"https://github.com/{repo}/actions/workflows/grid.yml"
        return {"action": "grid", "id": fid, "comment": (
            f"{head}\n\nThis figure is drawn on the grid, from its data or on a GPU, so nothing is submitted from here: "
            "a grid job waits for the owner's word and the number of jobs (docs/project.md), and this issue is not that "
            "word. The command the record gives:\n\n"
            f"```\n{command}\n```\n\nCost: {rerun.get('cost') or 'not recorded'}.\n\n"
            f"To run it through this repository, open [the grid workflow]({grid}), press Run workflow and paste the "
            "command. That runner works in a checkout of this repository inside a container, with no lab volume and no "
            "scheduler (docs/setup/grid.md), so a command that reads the lab volume or calls sbatch runs instead from the "
            "owner's own grid shell, in the checkout the record names.\n\nTo explore the method first:\n\n"
            + "\n".join(explore_lines(repo, record)))}
    return {"action": "none", "id": fid, "comment": (
        f"{head}\n\nNo command is recorded that redraws this figure, so nothing was run. Where it came from, as far as "
        f"the record goes: {(record.get('source') or {}).get('notes') or 'not written down'}\n\n"
        + "\n".join(explore_lines(repo, record)))}


def changed_paths(root):
    out = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-z", "--untracked-files=all"],
                         capture_output=True, text=True, check=True).stdout
    return [entry[3:] for entry in out.split("\0") if len(entry) > 3]


def outside(paths, chapter):
    folder = (FIGURES / chapter).as_posix() + "/"
    return [p for p in paths if not p.startswith(folder)]


def run(root, fid):
    """Run a figure's recorded command from the repository root, then hold the change to the figure's
    own chapter folder."""
    record = load_record(root, fid)
    if record is None:
        raise SystemExit(f"no committed record for {fid!r}")
    rerun = record.get("rerun") or {}
    if rerun.get("where") != "actions" or not rerun.get("command"):
        raise SystemExit(f"{fid}: its record does not say it runs on a runner")
    subprocess.run(["bash", "-c", rerun["command"]], cwd=root, check=True, timeout=RUN_TIMEOUT)
    paths = changed_paths(root)
    stray = outside(paths, fid.split("/", 1)[0])
    if stray:
        raise SystemExit("the command changed files outside the figure's folder: " + ", ".join(stray[:20]))
    print("\n".join(paths) if paths else "nothing changed")
    return paths


def write_outputs(decision):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as out:
        for key in ("action", "id", "branch"):
            value = str(decision.get(key, ""))
            if "\n" in value:
                raise SystemExit(f"{key} holds a line break")
            out.write(f"{key}={value}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan", help="decide what an issue event asks for")
    plan.add_argument("--event", required=True)
    plan.add_argument("--repo", required=True)
    plan.add_argument("--run-number", required=True)
    plan.add_argument("--comment", required=True, help="where to write the comment to post")
    plan.add_argument("--root", default=str(ROOT))
    go = sub.add_parser("run", help="run a figure's recorded command")
    go.add_argument("--id", required=True)
    go.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    if args.cmd == "plan":
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        decision = decide(event, args.root, args.repo, args.run_number)
        Path(args.comment).write_text(decision["comment"], encoding="utf-8")
        write_outputs(decision)
        print(json.dumps({k: v for k, v in decision.items() if k != "comment"}))
        return 0
    run(args.root, args.id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
