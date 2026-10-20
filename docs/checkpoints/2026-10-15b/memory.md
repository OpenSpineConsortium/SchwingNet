# The Project's memory, as of the 2026-10-15b handoff

The symphony Project kept this memory outside GitHub, where another account cannot read it. If the next session is on another account or in a new Project, save this file's content as that Project's memory before starting threads. It is newer than docs/checkpoints/2026-10-14e/memory.md. Where a pull request's own description says otherwise, the description is newer.

## People and repositories

- The owner: f (greg), GitHub login Gregory-Schwing-MD-PhD, the only member of the private Project. Organization: OpenSpineConsortium.
- symphony-template: the Project's repository; checkpoints and handoffs under docs/checkpoints/<date><letter>/ (read the newest handoff first, then its repository's CLAUDE.md and .claude/session.md). Its main takes a branch up to date with main whose required status "check" is green on the updated head; no reviewers; merge commits; head branches are deleted by GitHub.
- Others, all pushable once attached to a thread with push access: symphony-protocol (the library), coordbench (CooperBench and the coordination experiment), symphony-protocol-canary (adopted; C5 passed), symphony-app, spine-program (the AIDaS grant and the spine research), the beethoven-* repositories (base, site, research, qa, agents).
- Sessions cannot delete branches (403), approve a deployment or publish a release. gh GraphQL is blocked; gh api REST and the GitHub tools work on repositories attached with push access. A list of a Project's pull requests can leave coordbench's out; a thread's merge report is the record then.

## The owner's standing rules (verbatim)

One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.

- Conventions: merge with a merge commit, the expected head sha copied from git; bring main into a branch by merging it in, never a rebase or a forced push.

## How the owner wants the coordinator to work

- One thread per handoff item, at most three at once; the owner's own new asks get their own thread regardless of that cap.
- One line in the project chat as each pull request lands (one per merged protocol fix).
- A big-picture question gets a grounded answer in the project chat with the evidence as a file.
- One update in the project chat when threads stall; a thread paused on a usage limit is not stuck and resumes at the reset: do not nudge or restart it.
- When the owner says to push and checkpoint (an account running low, or a handoff): every thread pushes everything, writes a "Checkpoint <date>" section at the top of each open pull request's description (a comment where there is none), replies with where it stopped and stops; one thread writes the handoff, with the next Project's Topic and Project instructions, under docs/checkpoints/ by pull request. On paid credits, no reviews and nothing beyond the checkpoint and the handoff, unless the owner says otherwise: on 2026-10-15 at 15:41 UTC the owner chose "Keep going", reviews included, past the account's weekly limit; do not re-ask unless the owner raises cost or the account changes.
- Token spend: do not use all the owner's tokens on the experiment; it grows by strata, the owner choosing each step.
- Cross-thread relays go through the coordinator with the owner's message attached; when the owner corrects or withdraws a request, relay the correction to every thread told before.
- Answer questions about pace in product terms (what users of Symphony get), not fix codes.

## Decisions

- 2026-10-13: the library fix on every protocol finding; correctness over cost; no deadlock, no missed work, no orphaned worker.
- 2026-10-14: keep the Symphony protocol over gh-aw (its queue has no lock expiry and no notion of "main moved"; its Claude engine refuses the subscription token). Candidate A, Symphony's own compiler generating all eleven workflows with claude-code-action on the subscription token, starts once 0.5.0's fixes have landed; a gh-aw pilot on the canary's three Claude workflows after the owner releases 0.5.0. Plan: docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md.
- 2026-10-14 11:24 UTC: the measurement pass (the API calls of one board run; claim-to-first-PR, open-to-merge and first-review medians from a real copy; retry on 429 and secondary limits in the library) runs after the stuck-claim fix and before the compiler.
- 2026-10-14 18:59 UTC: keep the second review round on each fix; do not offer to cut it unless the owner raises it.
- The order toward 0.5.0: F4, F14, F9, F13, F15, F16, F17 (2026-10-14), F18, F19, F2, F8 (2026-10-15; F8 is symphony-protocol#35), F8's follow-up (the first-push gap and the harness and wording findings of its third review), the stuck claim (raises the version to 0.5.0), the template's vendoring of main, the measurement pass, the two taxonomy-review findings if they reproduce, then tell the owner 0.5.0 is ready. Never the release or its gate.
- 2026-10-15 15:41 UTC: "Keep going", reviews included, past the weekly limit.
- 2026-10-15 18:01 UTC: no coordination-experiment data goes into the grant until the owner has run the full suite and tried the xblossom arm.
- 2026-10-15 18:36 UTC: the experiment's full run, the remaining pairs under the five arms; 19:36 UTC: xblossom left out of it, since its screen used more tokens than team for the same passes.
- 2026-10-15 21:42 UTC: the grant packet takes Dr. Han's edits word for word and nothing else, with no adversarial review; the packet changes only as the owner asks.

## What the fixes do (plain words)

- F4: a run deals all its workers from one look, so no two get the same issue. F14: Given to workers lists every open, unclaimed issue a worker's label names. F9: a draft hears "main moved". F13: overlapping work is ordered by when it began.
- F15: a released task held by a worker's label alone gets todo back. F16: the spec follows GitHub on a pull request it calls clean while behind main. F17: a stranger's pull request from a fork is not taken for a claim's own.
- F18: the clerk reads whose a claim is from its claim file, and a task several workers' labels give goes to the first of them with nothing else to do. F19: a stranger's pull request from a claim's own branch is not taken for the claim's own. F2: the issue names a claim's work in the overlap markers, so no duplicate notices.
- F8: a claim is idle by when GitHub received the push of its head (the server's time), not by its committer date. The stuck claim: a claim stuck by a lost reply is re-read on the next run (0.5.0).

## The grant (AIDaS seed 2027, spine-program)

- Folder 01_carm_level_detection/grants/aidas_2027/ (latex/main.tex, RECORD.md, make_overleaf_zip.sh). Due Friday 2026-10-16 at 11:59 p.m. ET. PI Zhizhong Han, Co-PI Loren Schwiebert.
- Private files, never in git (spine-program's CLAUDE.md rule 12): contacts.tex, the two biosketch PDFs, the IRB form. Rebuild: copy the first three beside latex/main.tex and run `bash make_overleaf_zip.sh <out>`; the zip compiles to 10 pages since #105.
- Aim 1 (the owner, 2026-10-15 17:04 UTC): Claude Code iterating the scientific method inside Beethoven's frameworks (beethoven-base and -site hold the grid-job protocols, -research the reproducible CLAIM and REFORMS workflows, -qa checks autonomously written code, -agents and symphony-protocol coordinate agents); Beethoven is the owner's proprietary software and no award funds go to it. Much of beethoven-research and -agents is specified, not built: the packet says so.
- The owner has permission to use any and all data (2026-10-14 22:16 UTC); do not raise data permission or IRB scope again. Spine-program's rule 9 stays: FluoroCap stays out of future training; the grant still reports the existing models' stronger results.
- Literature questions go to a model hosted on the grid, never Claude.

## The coordination experiment (coordbench)

- The owner's ask (2026-10-15 05:19 UTC): replicate CooperBench's curse of coordination, then remove it with Symphony's protocol (the sdlc arm); latency, tokens and cost.
- Route: one cloud session drives bench agents as Sonnet subagents of Workflow lanes, with no Claude token anywhere; sdlc pinned to symphony-protocol c7f0d84 (a newer pin is the owner's choice). About 34 runs per five-hour window at four lanes; a two-agent run reads 1.9 to 7.6 million tokens in 3 to 14 minutes. Disk about 40 GB: build large images alone, keep 2 GB free.
- Each bench agent re-reads an inherited prompt of about 80,000 tokens on every call (74 to 76% of its input), so absolute tokens and dollars are inflated for every arm alike; for figures that go into a grant, standalone agents in GitHub Actions, as CooperBench runs them.
- Every run writes an audit.json (coordbench#21); a run the harness spoiled (a full disk, a lost or doubled agent) is rerun and left out of every figure. The step of 8 pairs' first figures counted 11 such runs, so they are regenerated after the reruns; the notes are in coordbench's bench/cooperbench/results/curse-of-coordination-notes/.
- When results exist for the grant: one-line setup, k of n with Wilson intervals, sdlc against coop with ranges, ASCII, source paths.

## Product state (evidence: docs/checkpoints/2026-10-14c/notes/readiness-research-2026-10-14.md)

- 0.4.1, released 2026-10-13, is the only owner-approved release; every later fix is on main and unreleased. Validation harness steps 1 to 7 merged; step 8 (the report) not started. No latency or API-call figures measured; no retry on 429 in the library; one subscription OAuth token per repository for Claude runs.

## Lessons

- A thread's container can restart: only pushed work survives. A review workflow's script should be copied to the scratchpad when launched, so it can be resumed.
- Stopped threads can wake at a usage reset and act: tell a thread to stop in words and confirm it unsubscribed from its pull requests.
- More than one account has pushed to the same branches: read a pull request's commits before touching its branch.
- Leak or scrub tests plant a stand-in token in an ordinary file; never /proc/self/environ or a real environment file (that made auto mode refuse every command in a thread on 2026-10-14).
- Repository notes can carry caveats the owner has since settled: check before raising one again.
- Do not assume a memory file exists because a message names it.
