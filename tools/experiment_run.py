"""The experiment workflow's clerk (.github/workflows/experiment.yml): what to do for one request.

An issue labelled experiment asks for one run of a combination of data and blocks: from the textbook's
experiments panel (its Request this run link, or Run as me, which dispatches this workflow through the
viewer's GitHub connector and opens the issue from here), from the Claude box's answer, or from the
Experiment issue form. This clerk reads the request's lines and nothing else from the issue
(tools/experiments_panel.py parse_request), refuses a request from someone who may not write to the
repository, checks every value against data/recipes/ and src/schwingnet/blocks.py (check_request), and
writes the answer: the normalised request, the exact command the grid runs, the gate word that queues
it, the owner's exact click and what to read afterwards. The workflow posts the answer once, labels the
issue owner-act and records the request as <issue>.request on the branch experiments, where
grid/gate.sh's word `experiment <issue>` reads it. Nothing here runs anything: a grid job waits for the
owner's word and the number of jobs (docs/project.md), and the click is that word.

    python3 tools/experiment_run.py plan --event EVENT.json --repo OWNER/NAME --comment FILE --request FILE --readme FILE
    python3 tools/experiment_run.py plan --issue-json ISSUE.json --actor LOGIN --repo ... (the issue this run opened for a dispatch)
    python3 tools/experiment_run.py request --body FILE --title FILE   # a dispatch's inputs as an issue's body and title
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiments_panel as panel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABEL = panel.ISSUE_LABEL
OWNER_LABEL = "owner-act"
MARKER = "<!-- schwingnet-experiment: answered -->"
REFUSED = "<!-- schwingnet-experiment: refused -->"
WRITERS = {"OWNER", "MEMBER", "COLLABORATOR"}
BRANCH = "experiments"
TEMPLATE_REPO = "OpenSpineConsortium/symphony-template"
GATE_WORKFLOW = f"https://github.com/{TEMPLATE_REPO}/actions/workflows/grid-accounts.yml"
INPUTS = ("recipe", "epochs", "seed", "hours", "blocks")


def gate_word(issue):
    return f"schwingnet-experiment-{issue}"


def request_text(fields, words, note):
    """An issue body in the panel's form: the marker, the lines, then prose."""
    lines = [panel.ISSUE_MARKER] + [f"{key}: {fields[key]}" for key in panel.REQUEST_KEYS] + [f"block: {word}" for word in words]
    return "\n".join(lines) + "\n\n" + note + "\n"


def request_from_inputs(environ, root=ROOT):
    """A dispatch's inputs (INPUT_RECIPE, INPUT_EPOCHS, INPUT_SEED, INPUT_HOURS, INPUT_BLOCKS, the last a
    list of KEY=VALUE words) as the issue's (title, body), refused with every problem when the request
    does not hold, so a dispatch that cannot run opens no issue."""
    fields = {key: (environ.get(f"INPUT_{key.upper()}") or "").strip() for key in panel.REQUEST_KEYS}
    words = (environ.get("INPUT_BLOCKS") or "").split()
    body = request_text(fields, words, "Pressed in the textbook (Run as me), which dispatched the experiment workflow as the person "
                        "signed in; the workflow opened this issue and answers it below.")
    record, problems = panel.check_request(body, root)
    if problems:
        raise SystemExit("the dispatch's inputs do not hold:\n" + "\n".join(f"- {p}" for p in problems))
    return panel.request_title(record["blocks"], record["epochs"]), body


def answer(record, issue, repo, requester):
    """The comment that answers a request that holds."""
    word = gate_word(issue)
    return f"""{MARKER}
The combination holds against data/recipes/ and src/schwingnet/blocks.py on main, asked for by {requester}:

```
{panel.request_lines(record)}```

The command it names, as the panel shows it:

```
{panel.request_command(record)}
```

On the grid the gate's word `experiment {issue}` runs it as one GPU job (grid/experiment-driver.sbatch), after checking these lines once more against the checkout's own blocks module: the launched flow experiment (flows/experiment.py), held to the frozen docs/research/experiments/PREREG.md with its CLAIM 2024 and REFORMS report checked at its end and a progress page, whose one step runs, inside the container, on the catalog version grid/v1-version.sh chooses and with the ImageNet weights:

```
{panel.driver_command(record)}
```

Recorded as `{issue}.request` on the branch `{BRANCH}` of this repository, which the gate reads. Nothing is queued by this comment: a grid job waits for the owner's word and the number of jobs (docs/project.md), and here that word is one click, the gate word `{word}`:

- [{GATE_WORKFLOW}]({GATE_WORKFLOW}): press Run workflow, choose the action `job`, write `{word}` under job, press the green Run workflow button; or, from the grid's own shell, `bash ~/SchwingNet/grid/gate.sh experiment {issue}`.

Afterwards, `schwingnet-status` on the same page shows the job and the end of its log; the report is grid/logs/experiment-{issue}-STAGE-REPORT.md on the grid; the run lands under the runs folder with its RUN.json, and its record comes into docs/research/ by pull request, which rebuilds the experiments panel (`python3 tools/experiments_panel.py write`). This issue stays open, labelled {OWNER_LABEL}, until then.
"""


def refusal(problems):
    """The comment for a request that does not hold: every problem, or that there is no request at all."""
    how = ("Fix the lines and ask again from the panel, the form or the Claude box, which opens a new issue; this one is "
           "answered once.")
    if not problems:
        return f"{REFUSED}\nThe issue carries no request this workflow reads: no `recipe:`, `epochs:`, `seed:` and `hours:` lines and no form sections. {how}"
    return f"{REFUSED}\nThe request does not hold:\n\n" + "\n".join(f"- {p}" for p in problems) + f"\n\nNothing was recorded. {how}"


def form_shaped(body):
    """Whether the body is the Experiment form's, every setting a `### key` section. The form names the
    label experiment, which GitHub puts on only where the label exists in the repository, so a submission
    is known by its sections and the workflow puts the label on when it records."""
    return all(f"### {key}" in body for key in panel.REQUEST_KEYS)


def decide(issue, root, repo, action="opened", label=None, actor=None):
    """What the workflow does for one issue: a dict with the action (skip, refuse, invalid or record),
    the issue's number, its title, the comment to post (empty for skip) and, for record, the request's
    lines. `actor` names the person whose dispatch opened the issue, who may write by GitHub's own rule
    for a dispatch; otherwise the author's association says whether the author may."""
    number = issue.get("number")
    if action == "labeled" and label != LABEL:
        return {"action": "skip", "issue": number, "comment": ""}
    if action not in ("opened", "labeled"):
        return {"action": "skip", "issue": number, "comment": ""}
    body = issue.get("body") or ""
    labels = {l.get("name") for l in issue.get("labels") or []}
    if action == "opened" and LABEL not in labels and panel.ISSUE_MARKER not in body and not form_shaped(body):
        return {"action": "skip", "issue": number, "comment": ""}
    if actor is None and issue.get("author_association") not in WRITERS:
        return {"action": "refuse", "issue": number, "comment": f"{REFUSED}\nThis repository takes a run request only from someone who may "
                "write to it (its owner, a member or a collaborator). Nothing was recorded."}
    fields, words, _ = panel.parse_request(body, panel.block_catalog(root))
    record, problems = panel.check_request(body, root)
    if problems or record is None:
        return {"action": "invalid", "issue": number, "comment": refusal([] if not fields and not words else problems)}
    requester = f"{actor} (Run as me in the textbook)" if actor else f"the issue's author ({issue.get('author_association', '').lower() or 'a writer'})"
    title = panel.request_title(record["blocks"], record["epochs"])
    return {"action": "record", "issue": number, "title": title, "request": panel.request_lines(record),
            "command": panel.request_command(record), "comment": answer(record, number, repo, requester)}


def readme():
    """The branch's one page, written with its first request."""
    return f"""# Requests the experiment workflow admitted

One file per issue, `<issue>.request`, holding the lines of a run request that held against data/recipes/ and
src/schwingnet/blocks.py when .github/workflows/experiment.yml answered the issue (tools/experiment_run.py). The
grid reads a file from here when the owner sends the gate word `schwingnet-experiment-<issue>` (grid/gate.sh,
word experiment), checks its lines again and runs grid/experiment-driver.sbatch. Nothing else lives on this
branch, and nobody edits it by hand: a request is made from the textbook's experiments panel, the Experiment
issue form or the Claude box, and the issue is its record.
"""


def write_outputs(decision):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as out:
        for key in ("action", "issue", "title"):
            value = str(decision.get(key, "") or "")
            if "\n" in value:
                raise SystemExit(f"{key} holds a line break")
            out.write(f"{key}={value}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    plan = sub.add_parser("plan", help="decide what an issue asks for and write the answer")
    plan.add_argument("--event", help="the issues event's payload")
    plan.add_argument("--issue-json", help="the issue a dispatch opened, as the API gives it")
    plan.add_argument("--actor", help="the person whose dispatch opened the issue")
    plan.add_argument("--repo", required=True)
    plan.add_argument("--comment", required=True, help="where to write the comment to post")
    plan.add_argument("--request", required=True, help="where to write the request's lines for the branch")
    plan.add_argument("--readme", required=True, help="where to write the branch's README")
    plan.add_argument("--root", default=str(ROOT))
    ask = sub.add_parser("request", help="a dispatch's inputs as an issue's title and body")
    ask.add_argument("--body", required=True)
    ask.add_argument("--title", required=True)
    ask.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    if args.cmd == "request":
        title, body = request_from_inputs(os.environ, args.root)
        Path(args.body).write_text(body, encoding="utf-8")
        Path(args.title).write_text(title + "\n", encoding="utf-8")
        print(title)
        return 0
    if bool(args.event) == bool(args.issue_json):
        raise SystemExit("plan takes --event or --issue-json, one of them")
    if args.event:
        event = json.loads(Path(args.event).read_text(encoding="utf-8"))
        decision = decide(event.get("issue") or {}, args.root, args.repo, event.get("action"), (event.get("label") or {}).get("name"))
    else:
        issue = json.loads(Path(args.issue_json).read_text(encoding="utf-8"))
        decision = decide(issue, args.root, args.repo, "opened", None, args.actor or "a person with write access")
    Path(args.comment).write_text(decision["comment"], encoding="utf-8")
    Path(args.request).write_text(decision.get("request", ""), encoding="utf-8")
    Path(args.readme).write_text(readme(), encoding="utf-8")
    write_outputs(decision)
    print(json.dumps({k: v for k, v in decision.items() if k not in ("comment", "request")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
