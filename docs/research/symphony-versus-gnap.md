# Symphony versus GNAP

Written 2026-10-17 in the project thread opened by the owner's question about GNAP, answering the owner's question of that day, "how do i compare to this", about https://github.com/farol-team/gnap. GNAP was read in full at its only branch, main at 2571f55 (2026-03-17): README.md, ONBOARDING.md, CONTRIBUTING.md, CLAUDE.md, LICENSE, docs/article.md (docs/index.html is the same article as a page), docs/gnap-overview.svg and examples/.gnap/, 24 commits from 2026-03-12 to 2026-03-17, MIT. It is judged in the frame of "Symphony versus competitors" (symphony-versus-competitors.md beside this file): the manual's two questions, what stops a second agent taking the same work and what frees a claim nobody finishes, asked of the code and not the README. Grades are the spec's: Verified means read at the source on the date above, Inferred means it follows from what was read. No coordbench result is used, under the owner's hold.

## The answer

GNAP (Git-Native Agent Protocol) is a specification, not software: four JSON entities in a .gnap/ folder of any git repository, agents.json, tasks/, runs/ and messages/, and a loop each agent runs every heartbeat_sec seconds (default 300), pull, read, work, commit, push to the shared repository (README.md, How It Works). Its repository holds no code: the two scripts it had were removed on 2026-03-12, gnap-poll.sh in 8512633 ("Revert two-level heartbeat") and gnap.sh in e01b31d ("kanban CLI, not part of protocol"), and its own article says "GNAP currently is an RFC, not a tool" (docs/article.md). Verified.

It shares Symphony's premise, that git is the coordinator and there is no server, and differs in what it does with it. GNAP's work is assigned: any participant, person or agent, writes a task with assigned_to, and the agents named pick it up. Symphony has both: the coordinator gives tasks to workers by label, and any worker may also pull an unclaimed issue from the queue, under a claim that git refuses to make twice. GNAP leaves to an application layer (AgentHQ, in its CLAUDE.md) the two things Symphony's protocol is built around: "Operational concerns (budget enforcement, concurrency control, stall detection) belong in the application layer, not the protocol" (CONTRIBUTING.md). So of the manual's two questions, GNAP's protocol answers the first by assignment and a race settled by rebase, and the second not at all, leaving it to whatever is built on top. Verified.

Where GNAP is ahead: it runs on any git host, works offline, defines messages between agents and a per-attempt run record with tokens and cost, and is small enough to read in ten minutes. Where Symphony is ahead: a claim whose losing push cannot vanish and whose file names its holder, the release of idle claims with the work kept, file overlaps ordered before they land, a required check deciding what merges, workers in GitHub Actions on a flat-rate plan, a shipped library checked over every interleaving of a few workers, and code that runs.

## The manual's two questions

**What stops a second agent taking the same work.** In GNAP an agent claims by setting a task's state from ready to in_progress and pushing; when two race, "git's non-fast-forward rejection handles it. The loser retries" (docs/article.md), by "git pull --rebase, re-check, retry (max 3)" (ONBOARDING.md, Step 5). Mostly there is no race, because the operator names the agent in assigned_to; but assigned_to is an array and nothing forbids two names. The task file has no field for who took it: it records who it is assigned to. The holder is named only by the commit message, by convention ("{id}: checkout FA-42", ONBOARDING.md), and by a run file, which the schema lets an agent write with state running when it starts, though ONBOARDING.md's loop writes it after the work (steps 6 to 8). Verified.

That leaves a hole, shown in a scratch run on 2026-10-17 (git 2.43, a bare repository and two clones a and b, task FA-1 assigned to both, each following ONBOARDING.md step 6):

- When both change only the state line, b's push is refused, b's pull --rebase drops b's commit as a cherry-pick already upstream ("hint: use --reapply-cherry-picks to include skipped commits"), b's retried push says "Everything up-to-date", and b's re-check reads "state": "in_progress", with nothing in the file saying it is a's; only git log, reading "a: checkout FA-1", says so. Unless b's re-check reads the log or notices its own commit vanished, which the spec does not ask, both work the task.
- When each also sets updated_at, the optional field the spec lists, b's rebase stops with "CONFLICT (content): Merge conflict in .gnap/tasks/FA-1.json". That exposes the race rather than widening it: b learns it lost, though the spec says only "If conflict, pull + rebase + retry push", not to stand down.

Symphony's lock rests on the same git ref semantics, available on any git host; what differs is how it is used. A claim is a fresh branch claude/N from the default branch whose first commit is a claim file naming the worker, so two claims always differ, the second push is refused as a non-fast-forward, nobody rebases onto the winner, and the protocol tells the loser to delete its branch and pick another issue (PROTOCOL.md, Claim); the push guard refuses a forced push onto another worker's claim. Grade: Verified for the two runs; that the duplicate-work case arises in practice is Inferred, since it needs a task assigned to several agents.

The README names no branch; read plainly, every GNAP state change is a push to the branch the agents share, so that branch, usually the main one, carries every agent's bookkeeping, and a repository whose default branch takes only pull requests, as Symphony's does, cannot run GNAP there without a branch set aside for it. Inferred.

**What frees a claim nobody finishes.** Nothing in the protocol: stall detection is left to the application layer (CONTRIBUTING.md), there is no time-out, and a task left in_progress stays there until someone edits it. The heartbeat is the agent's poll interval, not a liveness signal anyone reads. Symphony's board run releases a claim after 24 hours without a commit, comments what the branch holds and keeps the work under released/N-sha (PROTOCOL.md, Release). Verified.

## Side by side

| | Symphony | GNAP |
| --- | --- | --- |
| What it is | A Python library with no dependencies, twelve workflow files, hooks, a template and two GitHub Apps; code that runs | A specification: four JSON schemas and a loop; no code in the repository |
| Queue | GitHub issues, labelled todo | .gnap/tasks/*.json on the shared branch |
| How work is taken | The coordinator gives tasks by label, or any worker pulls an unclaimed issue; either way it claims by creating claude/N; workers in Actions are dealt work so no two race | Any participant assigns it in assigned_to; the agent sets state to in_progress and pushes |
| What stops a second agent | The second push of the branch is refused; the claim file names the holder; the loser deletes its branch | Non-fast-forward then rebase; only the commit message names who took the task (above) |
| Idle claims | Released after 24 hours, work kept | Left to the application layer |
| Overlapping files | Listed with a landing order, each piece told once | Not addressed |
| What merges | A required check on a pull request | Nothing: agents push to the shared branch; a review state and a reviewer field exist, unenforced |
| Messages between agents | Issue and pull request comments; no message entity | A message entity with recipients, broadcast, channels, threads and read_by |
| Cost record | Symphony-Usage trailers and a usage artifact per Claude run, summed by the metrics workflow | A run entity with tokens and cost_usd, written by each agent |
| Who can be a worker | People's sessions, routines and agents in Actions, any number of accounts, one rule | Any agent or person with git write access, polling |
| Where it runs | GitHub only | Any git host, or offline |
| Inference paid by | Each person's plan; one Claude plan for Actions workers through the subscription token | Not addressed |
| Checked how | Every interleaving of a few workers to a set depth against an oracle, with mutants; a shallow search runs in the required check | Not checked; no code to check |
| Licence | MIT (library); the SymphonyBoard App is paid | MIT |
| Use shown | The project's own repositories; pre-release, 0.4.1 the last release | Farol Labs: "4 agents (2 AI + 2 human) sharing 50+ tasks" (README.md, not verified) |

## What GNAP gets right that Symphony lacks

- **Forge-neutral and offline.** Anything that can git push can take part, on GitHub, GitLab, Gitea or a bare repository over ssh. Symphony needs GitHub's issues, rulesets and Actions.
- **Messages as a first-class entity.** Directed, broadcast, threaded, with read receipts, versioned with everything else. Symphony agents talk through issue comments, which is the same transport with less structure; the competitors document lists live messaging among the places Symphony is behind.
- **A run per attempt.** Each attempt is its own record, so retries and their cost are kept even when the task's final state hides them. Symphony keeps cost per commit and per Actions run, and a released claim's branch, but has no attempt record of its own.
- **Humans as participants with roles.** agents.json lists people and agents alike, with roles and reports_to; Symphony registers routines and Actions workers in .github/symphony/workers/ and lets people work under their login with no file.
- **Small.** Four schemas fit on one page, and the article's honest reading of its own state ("people star working tools, not promising specs") is a lesson for how Symphony presents itself too.

## Where it lands against the competitors document

GNAP joins the first kind of system there, work-queue coordinators for coding agents, but like Orbi and aeon it has no claim between workers that the forge enforces, so it does not change the head-to-head tables' conclusions. It refutes none of the seven claims: claim 1 needs a forge-side claim for sessions and CI agents on a flat plan, and GNAP's claim is a state edit whose holder only a commit message names, with no CI worker; claim 3 needs an idle release, which GNAP leaves to an application layer; claims 4 and 6 need overlap ordering and checked code, which it has neither of. Inferred, as the document grades those claims. The nearest thing GNAP's article names, Swarm Protocol (phuryn/swarm-protocol), has claim, heartbeat and file-conflict tools but keeps its state in an MCP server; it was not read for this note.

Two cautions for anyone quoting GNAP's README. Its two comparison tables' "Symphony" entries ("Elixir daemon" in one, "Linear + Codex" and "Server required: Yes" in the other) are openai/symphony, not this project; the name clash the competitors document records under "The name" already reaches readers. And GNAP's "No servers" is true of the protocol, as it is of Symphony; neither needs a host of its own beyond the git forge.

## How to run the race again

In an empty directory, with any git: make a bare repository, commit .gnap/tasks/FA-1.json with "assigned_to": ["a", "b"] and "state": "ready", clone it twice as a and b; in each, change "ready" to "in_progress" and commit; push from a, then from b (refused), then in b run git pull --rebase and push again, and read the file and git log. For the second case, have each clone also add an "updated_at" line with its own time before committing. The scratch script that ran both is not kept, since it is these steps and nothing more.
