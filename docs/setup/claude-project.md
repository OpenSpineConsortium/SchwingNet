# Making the thin Project for an account

A claude.ai Project belongs to one account. Each account that works here makes its own Project on this same repository. The Projects are thin on purpose: a link to the repository and nothing more; the instructions, the description and the memory stay blank. The goal, the memory, the board, the rules and the protocol live in the repository, and Claude Code loads them from the clone at the start of every session, so every account's sessions see the same thing and nothing is copied between them. The Project's own memory is private to its account, and it is written only when memory is turned on in the account's claude.ai settings; the template needs neither the Project's memory nor that setting, since a fact worth keeping goes to docs/memory/ by pull request (.claude/skills/remember).

Projects are in public beta on Pro and Max plans and are reaching accounts gradually; Team and Enterprise plans do not have them yet. If Projects is missing from the sidebar at claude.ai/code, the rollout has not reached the account.

## Steps, once per account

1. Install the Claude GitHub App on the repository if docs/setup/github.md has not been done yet; every thread of the Project needs it. The installation starts from claude.ai/code: when you link the repository in step 2, Claude sends you to GitHub to install the app and pick this repository.
2. In claude.ai, make a new Project and link the repository {{REPO}}. Make the repository the Project's only resource: a thread then starts from a fresh clone of {{DEFAULT_BRANCH}}, reads CLAUDE.md and is shown the board at the start of every session.
3. Leave the Project's instructions, description and memory blank. Nothing else happens when a repository is linked; the Project's page stays as it was, because the goal, the memory and the board are read from the repository inside every thread, not copied into the Project, and a thread loses nothing by it. Only if people will also chat in the Project outside a code session, paste the pointer text below into the instructions, as it stands: a chat has no clone and would otherwise know nothing of the project. The pointer never changes, so it never needs updating.
4. Choose the model and effort for this project if docs/project.md does not record them yet, set them in the Project's settings (General), and record the choice in docs/project.md under "Model and effort" by pull request, so every later Project copies it from there.
5. Name the Project after the repository and the account, so an account with several Projects tells them apart.

## Why the fields stay blank

A Project's fields and a session's context are two different planes. The fields (instructions, description, memory) are stored per account on claude.ai and written through its pages. The context is assembled by Claude Code from the clone at the start of every session: CLAUDE.md with what it imports (docs/project.md, docs/agents/PROTOCOL.md, docs/memory/MEMORY.md), the rules, the skills and the session hook that prints the board. The second plane is the one the model works from, it is the same for a thread of a Project and for a cloud session opened on the repository, and a merged pull request changes it for every account at once. Copying the repository into the first plane would need each account's own credentials, which this repository never holds, would go stale between copies, and would differ quietly from one account to the next; so the fields stay blank and the repository does the work. The Project's own memory is at most a private cache of its account; a fact worth keeping goes to docs/memory/ by pull request (.claude/skills/remember).

## A Project with several repositories

Keep this repository the Project's only resource. Claude Code runs a repository's hooks, permission rules and environment only in a session with that one repository; a thread of a Project with several, or one that adds another repository to itself, runs none of them. What stands on GitHub still holds there, and what stands on the session's hooks does not.

Still holds: the default branch's ruleset, so nothing reaches {{DEFAULT_BRANCH}} but a pull request; the claim lock, GitHub's refusal of the second push of a branch `claude/<issue>`; the required check, which holds every pull request to the protocol; and the board through /board and the claim skill, which load in every repository and fetch the board by the form that works in a clone made for one branch (CLAUDE.md, "Read first").

Does not hold: the push guard (tools/guard_push.py), so only the rules in .claude/rules/board.md and GitHub stand between the session and a push they forbid; the board printed at the start of the session, so the session reads it itself, with /board; and the usage trailer, so the session's commits carry no Symphony-Usage line and the cost metrics count its pull requests as unmeasured, outside pull_requests_measured and outside the cost per measured merge (docs/memory/field-metrics.md).

## The pointer text

```
This Project works on {{REPO}}. Read CLAUDE.md first. The shared memory is docs/memory/ (read MEMORY.md); the board is the file STATE.md on the branch board, read with: git fetch origin +refs/heads/board:refs/remotes/origin/board && git show origin/board:STATE.md; work is claimed as docs/agents/PROTOCOL.md says: one issue, one branch claude/<issue>, one pull request. A fact worth keeping goes to docs/memory/ by pull request, not only into this Project's memory. A chat here has no clone: start a thread on the repository for anything that needs its files.
```

## The main account and routines

The main account is the Claude account whose token the repository holds, the secret CLAUDE_CODE_OAUTH_TOKEN (docs/setup/claude-action.md): @claude, the workers in GitHub Actions and the coordinator workflow run on its plan. It needs no label and no coordinator routine: the board's own run releases idle claims and tells open work that overlaps, and the coordinator workflow does what needs judgement on that token (docs/agents/WORKERS.md). Only a repository that holds no Claude token runs the coordinator prompt as a routine on one account (docs/agents/routines/coordinator.md).

Every account's Project is made the same way, and a person needs no file to work in its threads: their sessions take their GitHub login as their name. A routine is a worker with a name of its own, after its job, registered by a file under .github/symphony/workers/ that says "runs": "routine"; the "Add a worker" issue form opens the pull request that adds the file and answers with the short prompt to paste, the name filled in (docs/agents/routines/worker.md). Any account may run routines, each under its own name, so they never mistake each other's claims. A routine is made inside the account's Project: paste its short prompt into the Project's own conversation and ask for the schedule, rather than making it on the routines page, so the routine runs as threads of the Project and shows on its Routines tab. The short prompt reads the full one from the repository on every run, so a change to it, merged by pull request, reaches the routine with nothing pasted again.
