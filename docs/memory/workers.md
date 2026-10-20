One way of working at every scale: whatever claims an issue is a worker named by its label worker:<name>, routines and workers in Actions are registered as files and run one prompt, and the coordinator is code in the board's run plus Claude in coordinator.yml.

A worker is a person's sessions, local or cloud, with whatever helpers
they start; a routine on someone's Claude account; or a worker in GitHub
Actions. Each has a name, unique in the repository: its label is
worker:<name> and its claim files say "- Worker: <name>", while the older
account:<name>, agent:<name> and "- Account:" are read as the same. A
person's sessions take the person's GitHub login as their name, unless the
session's environment sets SYMPHONY_WORKER to another, and need no file;
several sessions of one person each claim their own issue, since the
branch claude/<issue> is the lock. A routine or a worker in Actions is
named after its job, never after a login: a worker carries on every claim
made under its name, so two under one name would take each other's
claims. An issue a worker's label names is that worker's alone: the board
leaves it out of the Queue and lists it under "Given to workers" until it
is claimed; one that several workers' labels name is given to each of
them, and the first of them to claim it holds it, its Announce taking
the others' labels off (symphony-protocol's F18). A worker's label is
made when it is first needed (by the claim skill, the worker prompt, or
the clerk when the coordinator gives a task), so a copy makes six labels
up front: todo, claimed, in-review, blocker, epic and blocked.

The registry is one JSON file per routine or worker in Actions,
.github/symphony/workers/<name>.json: name, runs (actions, routine or
session), about, area (path globs), lands (owner or auto-merge), model,
max_turns, rounds and a note of whose account, never a credential. Its
README.md lists the settings, and `python3 tools/workers.py check`, part
of scripts/check.sh, holds every file to them. A person may register with
"runs": "session" to give their sessions an area. A worker is added by the
"Add a worker" issue form (.github/ISSUE_TEMPLATE/worker.yml), whose
workflow .github/workflows/add-worker.yml checks the answers, opens the
pull request that adds the file and answers with what to do next (for a
routine, the short prompt with its name filled in), or by adding the file
by hand in a pull request. Only someone who may write to the repository
can add one, and in crowd mode a worker in Actions is refused. Every
routine and worker in Actions runs the one prompt,
docs/agents/routines/worker.md, which differs only in the name.

.github/workflows/workers.yml runs every worker whose file says
"runs": "actions", one leg each, in parallel: every six hours, when an
issue is queued or given to one (given to several, every worker runs,
since the deal may give it to one the new label does not name), and
again while it has work, up to its rounds. Before any Claude session,
tools/team.py deals the open work on GITHUB_TOKEN, once for the run from
one look at the repository in its first job (its own claim, else the
task it was given, a task shared by several workers going to the first
of them in the registry's order with nothing else to do (F18), else the
next blocker or queued issue in its area), so no two legs of one run
race for one claim or are dealt one issue from looks at different
moments, and an idle worker spends no Claude usage; a leg that
waited looks again and keeps only its worker's own work from that look,
taking a queued or shared issue only as dealt; in a copy made before
symphony-template#77 (2026-10-14), whose workers.yml is older, each leg
asks for itself until the copy takes the template's workers.yml, and in
one made between #77 and #78 until the release 0.5.0 reaches it, by hand
with the template's tests/fixtures/board-STATE.md, which its protocol.yml
does not bring. The sessions run on the secret CLAUDE_CODE_OAUTH_TOKEN;
no repository variable switches workers on.

The coordinator is two things. A step of the board's own run, on
GITHUB_TOKEN and with no Claude usage, releases a claim idle for 24 hours
(not one in-review, marked ready, or a draft its author called "finished;
ready to mark") with one comment saying why, whose, what the branch holds
and what the plan was, renames its branch in the same run, and tells
overlapping open work once; the board's Overlaps section lists the shared
files and the landing order (a blocker, then work marked ready, then the
oldest). And Claude in .github/workflows/coordinator.yml, on the Claude
token, plans an issue labelled epic into tasks given to registered
workers, settles a task labelled blocked, integrates a finished epic, and
weekly runs the coordinator prompt docs/agents/routines/coordinator.md,
which splits requests into issues and tidies the memory. Only a repository
with no Claude token, as in crowd mode, runs that prompt as a routine.

The planning follows CooperBench's best-scoring configuration, from the
authors' later ablation, unreviewed: team 62%, shared remote 56%, solo
48%, messaging-only 26%. Inside claude-code-action Claude gets only the
action's GitHub tools unless --allowedTools grants more, so both workflows
grant git, gh, python3 and scripts/check.sh, a list CLAUDE_ALLOWED_TOOLS
replaces; in tag mode (@claude) the action's own prompt also forbids
rebasing and merging, which a custom prompt does not. With a custom prompt
the action refuses a run whose actor is a bot unless allowed_bots names
it, and runs dispatched by GITHUB_TOKEN act as github-actions[bot], merges
the Claude app turned on as claude[bot], so both workflows name both.
GitHub keeps one pending run per concurrency group, so the groups sit on
the jobs, per worker and per epic, never on the whole workflow.
docs/agents/WORKERS.md has the whole of it.

Source: docs/agents/WORKERS.md, the workflows named above,
symphony-protocol 0.4.0 (labels.py, workers.py, coordinator.py, team.py),
read 2026-10-12, and its F18 (symphony-protocol#32: team.py and
spec/PROTOCOL.md), vendored 2026-10-15 at 53e232f ahead of its release and since 2026-10-16 as part of 0.5.0; cooperbench/CooperBench at 63b9d44
(team_harness/prompt.py, runner/team.py) and anthropics/claude-code-action
at 2dca132 (src/create-prompt/index.ts, src/entrypoints/run.ts,
docs/faq.md), read 2026-10-09.
