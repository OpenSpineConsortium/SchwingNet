# Workers and the coordinator

There is one way of working here, whoever and whatever does the work: one person alone, one person running several sessions with helpers, routines running on their own in the cloud, several people with their own sessions and routines, or workers running in GitHub Actions. Everyone and everything that claims an issue is a worker, every worker follows the claim protocol (PROTOCOL.md) under a name of its own, and the coordinator keeps them out of each other's way.

## Workers

A worker is one of three kinds:

- A person's sessions, local or cloud, with whatever helpers (subagents) the session starts. The sessions take the person's GitHub login as their name, unless the session's environment sets `SYMPHONY_WORKER` to another; a person needs no file to work here. Several sessions of one person each claim their own issue: the branch `claude/<issue>` is the lock, so two can never hold the same one.
- A routine on someone's Claude account, which runs on its own schedule in the cloud, on that account's plan.
- A worker in GitHub Actions, which .github/workflows/workers.yml runs on this repository's Claude token, the secret CLAUDE_CODE_OAUTH_TOKEN (docs/setup/claude-action.md), on that account's plan.

Each worker has a name, unique in the repository. Its label is `worker:<name>`, which it puts on the issues it claims, and its claim files say `- Worker: <name>`; an issue a worker's label names is that worker's alone, so the board leaves it out of the Queue and shows it under "Given to workers" until the worker claims it; one that the labels of several workers name is given to each of them, and the first of them to claim it holds it. Labels from before workers had one name, `account:<name>` and `agent:<name>`, are read the same way. A routine and a worker in Actions are registered by one small file each, `.github/symphony/workers/<name>.json`, which says where it runs, what it is for, the area it prefers, how its pull requests land and, in Actions, the model and the turns and rounds it may take; .github/symphony/workers/README.md lists the settings, and `bash scripts/check.sh` holds every file to them. Name a routine or a worker in Actions after its job, never after a person's login, so it never shares a name with that person's sessions. A person may register too, with `"runs": "session"`, to give their sessions an area.

A worker in Actions may run under an agent, a set of instructions and tools under .claude/agents/ that .github/symphony/agents.json gives it (docs/agents/AGENTS.md), the worker prompt still its task.

Add a worker with the "Add a worker" issue form: .github/workflows/add-worker.yml checks the answers, opens the pull request that adds the file, and answers on the issue with what to do next (for a routine, the prompt to paste, its name filled in). Or add the file by hand in a pull request of its own. Every routine and every worker in Actions runs the same prompt, docs/agents/routines/worker.md, which differs from one worker to the next only in the name: carry on with its own claim, else take what it was given, else the next issue in its area, and land as its file says.

The workers in Actions run in parallel, one run per worker, every six hours, whenever an issue is queued or given to one of them (given to several, every worker runs, since the deal may give it to one the new label does not name), and again while a worker still has work, up to its rounds in a row. Before any Claude session starts, tools/team.py deals the open work among them on the repository's own token, once for the whole run from one look at the repository, in the run's first job: each takes its own claim that needs work, else the task it was given, one given to it alone first and one the labels of several workers give going to the first of them, in the order the registry lists the workers in Actions, with nothing else to do (symphony-protocol's F18), else the next unclaimed blocker or queued issue whose "Files likely touched" fit its area, so no two legs of one run race for one claim or are dealt one issue from looks taken at different moments; a worker with nothing to do costs seconds of a runner and no Claude usage. A leg that waited for an earlier run of its worker looks again before its session, and keeps from that look only its worker's own work: its own claim that needs work, or an issue given to it alone; an issue of the queue, or one shared with other workers, it takes only as the run dealt it. A copy made from the template before symphony-template#77 (2026-10-14) runs an older workers.yml, in which each leg asks for itself, as before, whatever library the copy vendors, until the copy takes the template's .github/workflows/workers.yml; one made between #77 and #78, the same day, whose library has no `team deal` yet, does the same until symphony-protocol 0.5.0, the first release that carries it, reaches the copy, by hand as docs/start/protocol.md's step 7 says, with the template's tests/fixtures/board-STATE.md, since the copy's protocol.yml brings only tools/ and 0.5.0 changes the Given to workers heading that file pins.

## The coordinator

The coordinator is two things, neither of them a person's job.

In the board's own run, on the repository's own token and with no Claude usage, it releases every claim whose branch has gone a day without a commit (unless its pull request is marked ready or its issue is labelled in-review), with a comment that says why, whose the claim was, what the branch holds and what its plan was, so the next worker can carry the work on or start over; and it tells each piece of open work about the other work that changes the same files, once, with the order the work should land in. The board shows the same overlaps, and what is given to whom, at the start of every session.

What needs judgement is Claude's, in .github/workflows/coordinator.yml, on the repository's Claude token:

- Planning. Label an issue `epic` and Claude plans it, the way the best-scoring arm of CooperBench's own later ablation did: a team with a lead, a shared task list and a shared scratchpad (62%, against 56% for coop on a shared git remote, 48% solo and 26% for agents that could only message each other; one model, 50 task pairs, one seed, not peer reviewed). It divides the epic into tasks that each own a disjoint set of files, writes the interfaces where two tasks meet into both, and gives each task to a registered worker whose area fits; tools/team.py, not Claude, writes the plan into the epic and opens the tasks, labelled todo and `worker:<name>`, or todo alone for the open queue when no worker is registered, and starts the workers in Actions.
- Settling. When a worker labels its task `blocked`, Claude settles what it needs on the epic, or moves the task to another worker, then takes the label off and starts the task's worker again; what only the repository's owner can settle, it says on the epic and leaves blocked.
- Integrating. When the last task of an epic closes, Claude checks the default branch as a whole (`bash scripts/check.sh` and the tests the epic names), fixes on its own claim branch what the pieces broke together, and closes the epic: every task can pass alone while the whole fails.
- Tidying, weekly. Claude runs the coordinator prompt, docs/agents/routines/coordinator.md: it splits requests that ask for more than one piece of work into issues, or labels them epic, and keeps the shared memory under its limits and true.

A repository that holds no Claude token, as one in crowd mode never does (docs/setup/crowdsourcing.md), runs the same coordinator prompt as a routine on a maintainer's own account instead, and there an epic is split into tasks by people, since no workflow plans it; the board's own run does the rest either way.

| CooperBench team mode | Here |
| --- | --- |
| The lead's PLAN.md: who owns which files, the interfaces between them | The plan the coordinator writes into the epic issue |
| A task list pre-seeded with one task per member | Sub-issues of the epic, labelled todo and worker:<name> |
| Claiming a task | Pushing its branch claude/<issue>, as for any claim |
| The shared scratchpad and messages | Comments on the epic, which every worker's prompt reads |
| The lead unblocking or reassigning a stuck task | The label blocked, which calls the coordinator |
| The shared git remote: fetch and merge each other's branches | Every claim branch is on origin; finished work merges to the default branch on a green check |
| The lead's integration checklist | The coordinator's last pass over the integrated default branch |

## A worker on a planned task

A worker given a task of an epic:

1. reads the epic's plan first and stays inside the files its task owns;
2. claims its task as PROTOCOL.md says, with its name on the claim file's Worker line;
3. looks at its peers' branches on origin while it works, so its code meets theirs at the agreed interfaces instead of colliding with them;
4. brings the default branch in when it has moved, by merging it, which needs no forced push, or by rebasing its own claim branch;
5. when stuck on something only a peer or the coordinator can settle, says what it needs on the epic and labels its task `blocked`, which calls the coordinator;
6. finishes as PROTOCOL.md says, and lands as its file says: by the owner's merge, or by auto-merge once the check named "check" passes.

## What it costs

A worker with nothing to do costs no Claude usage: the dealing, the releases and the overlaps are code. Every Claude run in Actions, the workers' and the coordinator's alike, draws on the plan of the account whose token is CLAUDE_CODE_OAUTH_TOKEN, so three workers in Actions spend it about three times as fast as one; a routine draws on its own account's plan; a person's sessions on that person's. A Max plan suits several workers in Actions better than Pro.

What it costs is measured where the field metrics are on (docs/setup/metrics.md, What the work cost): every session puts what it spent on its commits, and every Claude run in Actions keeps a record of its own, so the daily metrics give the tokens, the estimated price at API rates and the time each merged pull request took, and set work done alone beside work done in parallel, with ratios over 1 where working in parallel did better.
