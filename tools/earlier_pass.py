"""Whether this pull request's head already passed a job of the check, so
a Checks run that no commit started can skip the work the commit decides.

A pull request's Checks run also starts on events that bring no commit:
the body edited, the pull request marked ready, or turned back to draft.
Of what the check holds, only the protocol and review-record checks read
what those change; the checks and the tests read the commit, which an
earlier run on the same head has checked already. On 2026-10-25, 39 of
SchwingNet's 124 pull-request runs of Checks were such re-runs
(docs/research/actions-minutes-2026-10-25.md). So on such an event a job
that runs the checks asks GitHub first for this workflow's runs on the
head, and skips its work only where the newest of them, not this run, has
finished and holds a job of the same name that succeeded, or, with --step,
a job of that name whose step of that name succeeded. Only the newest
decides: an edit that changed the base branch ran in full, and one that
failed there, was cancelled, or is still going lets nothing older stand in
for it. A job whose work an earlier pass let it skip succeeds, so in a
job of parts the pass carries on to the next such event; with --step the
skipped step is skipped, not passed, and a run whose job succeeded with
that step skipped is read past to the run before it. Whatever GitHub does
not answer reads as not passed, so the work runs as it always did.

An earlier run checked GitHub's test merge of the head with its base
branch as that branch then stood, as every run on the head did until the
next push, so a body edit re-checks the head against a moved base branch
no more than a label does. That is the rule already: the check is not
required to be up to date, and the overlap check (tools/locks.py overlap)
says when a pull request must bring its base branch in. Two open pull
requests on one head, which the claim protocol never makes (one issue,
one branch, one pull request), share their runs here.

  python3 tools/earlier_pass.py --job "check part 1/4" [--step NAME]

reads GITHUB_REPOSITORY, GITHUB_RUN_ID, HEAD_SHA and GITHUB_TOKEN, prints
one line, and writes passed=true or passed=false to GITHUB_OUTPUT.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CI_WORKFLOW = "ci.yml"
PASSED, CARRIED = "passed", "carried"


def standing(jobs, job, step=None):
    """What a finished run says of the job: PASSED where its job of that
    name succeeded, or, with step, where that step succeeded, whatever the
    job's later steps did, since the body's checks may fail after the
    commit's checks passed and the body is what the next event fixes;
    CARRIED where the job succeeded with that step skipped, which only an
    earlier pass does to it; else None, so the work runs."""
    for entry in jobs:
        if entry.get("name") != job:
            continue
        succeeded = entry.get("conclusion") == "success"
        if step is None:
            return PASSED if succeeded else None
        found = [s.get("conclusion") for s in entry.get("steps") or [] if s.get("name") == step]
        if "success" in found:
            return PASSED
        return CARRIED if succeeded and found == ["skipped"] else None
    return None


def earlier_runs(api, workflow, head, run_id):
    """This workflow's pull-request runs on the head, finished or not,
    newest first, leaving out the run asking."""
    path = f"/repos/{api.repo}/actions/workflows/{workflow}/runs"
    params = {"head_sha": head, "event": "pull_request", "per_page": 100}
    runs = (api.get(path, params) or {}).get("workflow_runs", [])
    mine = [r for r in runs if r.get("head_sha") == head and str(r.get("id")) != str(run_id)]
    return sorted(mine, key=lambda r: r.get("created_at") or "", reverse=True)


def run_that_passed(api, workflow, head, run_id, job, step=None):
    """The id of the run that passed the job, where the newest earlier run
    on the head passed it or carried a pass from the runs before it, or
    None."""
    for run in earlier_runs(api, workflow, head, run_id):
        if run.get("status") != "completed":
            return None
        path = f"/repos/{api.repo}/actions/runs/{run['id']}/jobs"
        jobs = (api.get(path, {"per_page": 100}) or {}).get("jobs", [])
        found = standing(jobs, job, step)
        if found == PASSED:
            return run["id"]
        if found != CARRIED:
            return None
    return None


def verdict(api, workflow, head, run_id, job, step=None):
    """True or False, and the line that says why. Any failure to read
    GitHub is a False, so the job does its work."""
    what = repr(job) + (f" (step {step!r})" if step else "")
    try:
        passed = run_that_passed(api, workflow, head, run_id, job, step)
    except Exception as problem:  # whatever stops the read runs the work
        return False, f"earlier pass: not read ({problem}), so {what} runs"
    if passed is None:
        return False, f"earlier pass: no earlier run on {head[:12]} passed {what}, so it runs"
    return True, f"earlier pass: run {passed} passed {what} on {head[:12]}, so its work is skipped"


def client(repo):
    from sdlc_protocol.adapters.github import GitHub
    return GitHub(None, repo)


def write_output(passed):
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a", encoding="utf-8") as out:
            out.write(f"passed={'true' if passed else 'false'}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--job", required=True)
    parser.add_argument("--step")
    parser.add_argument("--workflow", default=CI_WORKFLOW)
    args = parser.parse_args(argv)
    head = os.environ.get("HEAD_SHA", "")
    if not head:
        passed, line = False, "earlier pass: no HEAD_SHA, so the work runs"
    else:
        try:
            api = client(os.environ["GITHUB_REPOSITORY"])
        except Exception as problem:  # no client, no skip
            passed, line = False, f"earlier pass: no client ({problem}), so the work runs"
        else:
            run_id = os.environ.get("GITHUB_RUN_ID", "")
            passed, line = verdict(api, args.workflow, head, run_id, args.job, args.step)
    print(line)
    write_output(passed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
