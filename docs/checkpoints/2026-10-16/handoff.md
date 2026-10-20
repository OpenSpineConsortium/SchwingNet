# Symphony handoff, 2026-10-16 (paste the three blocks in paste-into-new-account.md beside this file)

At 18:54 UTC on 2026-10-16 the owner asked to checkpoint every thread at once, wrote "PLEASE CHECKPOINT NOW AND UPDAET HANDOFF" in five threads, and at 18:58 UTC asked for the handoff to be updated "so all threads can continue on another account", with every piece of work, intermediate or final, research and state included, pushed to git. Each thread was told to push every branch, commit its findings under docs/research/, put a section titled "Checkpoint 2026-10-16" at the top of each open pull request's description, reply in its thread with a self-contained checkpoint, unsubscribe from its pull requests and stop. The thread "Checkpointing all threads" wrote this file and folds each thread's checkpoint in as it lands; the threads' own Checkpoint sections and replies are newer than this file where they differ, and where a workstream below says its checkpoint had not landed yet, its branch's last commit and its pull request are the state.

This file replaces docs/checkpoints/2026-10-15b/handoff.md as the place to start. Two files beside it carry what lives outside GitHub: memory.md, the Project's memory at the handoff, copied verbatim (save it as the next Project's memory if the next session is on another account or in a new Project), and owner-todo.md, the owner's own steps with every link and what to click, which replaces docs/checkpoints/2026-10-15b/owner-todo.md for everything it lists.

## 0. The first message to paste

The first message, brought up to 19:40 UTC after this file merged, is now part 1 of paste-into-new-account.md beside this file, with the Project's instructions (its part 2) and goal (its part 3); paste those, not the block that stood here.

## 1. Before the paste

### Continuing in the same Project (symphony, on the same account)

Nothing to set up: the Project memory, the shared folder and the artifacts stay. Paste part 1 of paste-into-new-account.md in the project chat. Since 04:47 UTC on 2026-10-16 each thread's own model has been at its weekly limit, which resets on 2026-10-22 at 21:00 UTC; sessions go on on their fallback model.

### Moving to another account or a new Project

Nothing outside GitHub carries over: this Project's memory, threads, shared folder (/mnt/project-files), artifacts, Claude Docs and connectors stay with this account. Part 3 lists what lives only there; none of it is needed to carry on, since the work is in git and the grant's current copy is the owner's Overleaf project (owner-todo.md, item 2, has the one optional download). Then:

1. GitHub: signed in to the new Claude account, open https://claude.ai/connect-github, sign in to GitHub as Gregory-Schwing-MD-PhD and press Authorize. The Claude GitHub App is already installed on every repository of OpenSpineConsortium (2026-10-13); if the page asks where to install it anyway, pick OpenSpineConsortium and All repositories.
2. The Project: open https://claude.ai/code, make a new Project named symphony, pick OpenSpineConsortium/symphony-template as its repository, and set:
   - Goal (or Topic), exactly: part 3 of paste-into-new-account.md.
   - Project instructions, exactly: part 2 of paste-into-new-account.md (your instructions word for word, with your two conventions of 2026-10-16 on lines of their own).
3. The cloud environment: the default one is enough. Add no environment variable and no secret: no Claude token, no API key.
4. Connectors: the grant thread used your Microsoft 365 connector (WSU Outlook) to write e-mail drafts. If a new thread should do that again, connect Microsoft 365 in the new account (https://claude.ai/settings/connectors). No connector can attach a file to an e-mail; you attach and send.
5. Send part 1 of paste-into-new-account.md as the first message. Allow the repository prompts the threads raise when they attach symphony-protocol, coordbench and the others with push access.

## 2. Where each workstream stopped

Times are UTC on 2026-10-16 unless they say otherwise. Every repository below is in the OpenSpineConsortium organization.

### 2.1 Protocol fixes toward 0.5.0, then 0.5.1 (symphony-protocol; thread "Protocol fixes toward 0.5.0")

Merged on 2026-10-16 in symphony-protocol: #36 (F8's third review: the first-push gap, the harness gaps and the wording), #37 (F20, the stuck claim: a release that cannot read whether its comment stands leaves the labels for the next run; it raised the version to 0.5.0), #38 (what a board run costs: the calls GitHub answered, a table from the fake), #39 (F21: the push guard judges each push in the clone it runs in) and #40 (rate limits: the client waits as GitHub asks and makes the call again). In symphony-template: #106 (vendors symphony-protocol 0.5.0 ahead of its release, with docs/agents/PROTOCOL.md in line; tools/VENDORED says 0.5.0 a8e0e56), #108 (how long a claim waits, measured in a real copy: docs/research/claim-waits-in-a-real-copy.md) and #110 (the coordination block's medians round half up).

The release: 0.5.0's release run waits for the owner's approval at https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117 (owner-todo.md, item 3). 0.4.1 of 2026-10-13 is still the latest published release. No session approves or publishes a release, or changes its gate, and none touched it.

Open at the thread's checkpoint of 19:12 UTC, four drafts in symphony-protocol, each with a "Checkpoint 2026-10-16" section at the top, the workers' unfinished trees committed and every branch pushed:
- #42, F22 (a reopened issue keeps the labels claimed and in-review, so the board lists it nowhere): every check green, the mutation lane included; it still needs its adversarial review. It comes first.
- #41, F23 (a release comment GitHub may have written leaves the labels for the next run; branch claude/owner-decisions-f23-late-comment): green, but its first review's finding 3 is only half done.
- #43, F25 (the push guard misses a push after a here-document's apostrophe) and #44, F26 (it misses a wrapper's shortened options, as env --uns): unfinished, and each conflicts with main until main is merged in.
- F24 (a push inside $( ) or <( )) and F27 are reproduced in the thread's notes, with no pull request yet.
0.5.1 will carry #38, #39 and #40 and each of these as it merges. The template's follow-up (vendor main, count the metrics client's retries, switch the push guard's shim) waits until the owner has approved 0.5.0. Then tell the owner 0.5.1 is ready; only the owner approves a release.

Where the state lives in git: the thread's whole state is docs/research/protocol-fixes-after-0-5-0/README.md in symphony-template on branch claude/protocol-fixes-0-5-0-p0yrit, with the reviews, the draft commit messages and the probe scripts beside it, in the docs-only symphony-template#119 (green, unmerged); it lists the rest in order. Beside it: symphony-protocol's validation/ (DESIGN.md, GUARANTEES.md, the findings), each fix's branch and draft, and docs/checkpoints/2026-10-15b/protocol-fixes/ here.

Brief for a new thread: "Attach OpenSpineConsortium/symphony-protocol and OpenSpineConsortium/symphony-template with push access. Read docs/checkpoints/2026-10-16/handoff.md part 2.1, then docs/research/protocol-fixes-after-0-5-0/README.md on symphony-template's branch claude/protocol-fixes-0-5-0-p0yrit (pull request #119; merge it once its check is green, docs only), and the Checkpoint 2026-10-16 section of each open symphony-protocol draft (#41, #42, #43, #44). Review #42 and take it to merge; then the rest in the README's order: #41, #43 and #44 with main merged in, then F24 and F27, one pull request each, two adversarial reviews each, the library fix on every finding, correctness over cost; merge each once green. Once I have approved 0.5.0: the template's follow-up (vendor main, count the metrics client's retries, switch the push guard's shim). Then tell me 0.5.1 is ready. Never approve, publish or change a release or its gate."

### 2.2 The AIDaS seed grant (spine-program; thread "AIDaS seed grant"), due tonight

Due Friday 2026-10-16 at 11:59 p.m. ET (03:59 UTC on Saturday the 17th), one PDF e-mailed to aidas@wayne.edu. PI Zhizhong Han, Co-PI Loren Schwiebert. The owner sent them the final PDF at 7:51 a.m. ET; Dr. Schwiebert approved at 11:19 a.m. ET, updating both investigators' addresses, most likely in the owner's Overleaf project, and Dr. Han at 11:54 a.m. ET ("good to go"). At the thread's checkpoint of 19:10 UTC only the owner's submission was left: his mail showed nothing sent to aidas@wayne.edu yet.

Merged on 2026-10-16 in spine-program: #107 (the spine RAG-LLM as the goal and the spine program as its case, 71acc6b), #109 (the cover's contact lines, e664bd2), #111 (one readable figure panel, bda329d), #113 (every red mark an approximation listed in APPROXIMATIONS.md; line C3 repays $1,500 of the owner's Claude subscriptions once his adjunct appointment starts; $19,987 requested, under the $20,000 cap; 10379a7) and #115 (the grant's own handoff and the day's scripts). Nothing is open, and the thread has unsubscribed and stopped.

Where the state lives in git, in spine-program under 01_carm_level_detection/grants/aidas_2027/: HANDOFF_2026-10-16.md (the state, the owner's steps and how a thread on another account carries on; read it first), latex/main.tex, RECORD.md (sections 3 and 4: what was asked, answered and defaulted), APPROXIMATIONS.md (the 17 estimates to replace later), build_pdf.sh, make_overleaf_zip.sh and review/2026-10-16/ (the day's one-shot scripts). The private files, contacts.tex, both biosketches and the IRB form, never go into git; the owner's Overleaf project holds the first three with Dr. Schwiebert's update (Menu, then "Source" under Download). The PDF and the zip in this Project's shared folder predate that update, so the PDF to submit is the one Overleaf builds now.

What waits on the owner (owner-todo.md, item 1): the PDF from Overleaf, the disclosure audit, and the submission tonight; later, the allowability question to aidas@wayne.edu, the 17 approximations, and the other submissions he plans (Anthropic's AI for Science program and other fits).

Holds that stand: no coordbench data in the grant until the owner has run the full suite and tried xblossom; VinDr and FluoroCap results stay; never raise data permission or IRB scope; spine-program's rule 9 stays; the packet changes only as the owner asks and takes no adversarial review (the owner, 10:17 UTC); never commit contacts.tex, the biosketches or the IRB form.

Brief for a new thread, only if the owner asks for changes: "Attach OpenSpineConsortium/spine-program with push access. Read docs/checkpoints/2026-10-16/handoff.md part 2.2, then 01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-16.md in spine-program and what it says to read. Ask me for contacts.tex and the two biosketches (I download them from my Overleaf project: Menu, then Source under Download). Make only the changes I ask for, as I word them, with no adversarial review; work by an issue, its claude/<issue> branch and one pull request; rebuild by bash build_pdf.sh and bash make_overleaf_zip.sh <a path outside the tree>, and give me the PDF and the zip. Never commit the private files."

### 2.3 The curse of coordination (coordbench; thread "Curse-of-coordination runs")

The owner's ask of 2026-10-15: replicate CooperBench's curse of coordination, then remove it with Symphony's protocol (the sdlc arm), measuring latency, tokens and cost. The full run is the remaining pairs under the five arms (solo, coop, sdlc, coop-git, team), no xblossom, its batches back to back on the owner's "All batches" (00:56 UTC) and "Just continue" (09:37 UTC), stopping only at a limit or the owner's word.

Merged in coordbench on 2026-10-16: #22 (lanes pin the agents' effort, xhigh), #24 and #25 (the 12 reruns, all clean) and #26 (the step of 8 regenerated over its 40 clean runs: solo 5 of 8, coop 7, sdlc 7, coop-git 6, team 7, no curse; sdlc 1.5 times coop's wall time and 1.4 times its tokens). Batches 9-16 (40 runs, 22 passed), 17-24 (40 runs, 39 passed) and 25-32 (40 runs, 24 passed) ran clean; over the 33 pairs then done, solo and team passed 24, coop, sdlc and coop-git 23 (interim, not for the grant). Batch 33-43 (50 runs, three lanes) started at 18:40; at the checkpoint 36 runs were left paused and 3 in flight were let finish. The thread deleted its 2026-10-17 04:05 UTC reminder so nothing restarts the bench, and was saving every finished run and the queue to coordbench by pull request, with the notes' "The next steps, in order" brought up to date.

Where the state lives in git: coordbench's bench/cooperbench/results/curse-of-coordination-notes/ (README with "The next steps, in order", run/ with the queue, the 43-pair order, the batches and the image loop), with each run's audit.json under its results folder. The run logs and transcripts are in the shared folder only (part 3); a fresh container restores the queue from the bundles in git (run/restore-bundles.py) when it cannot read that archive. At the thread's checkpoint, 179 of the full run's 215 runs were finished and 36 paused; the finished runs, the interim tallies, the queue, its scripts and the notes went into draft coordbench#27, which merges once green. That pull request and the notes' "The next steps, in order" are the state to trust, and they name the runs left to do.

Brief for a new thread: "Attach OpenSpineConsortium/coordbench with push access. Read docs/checkpoints/2026-10-16/handoff.md part 2.3, then bench/cooperbench/results/curse-of-coordination-notes/README.md in coordbench, its 'The next steps, in order' first. Restore the run in a fresh container as that README says, rerun only the runs it lists as in flight or spoiled, finish batch 33-43 at effort xhigh on three lanes, then record the full run by pull request (subset, report, summary, bundle; adversarial review; check.sh; merge once green). Launch nothing beyond the full run I chose. No coordination data goes into the grant."

### 2.4 Symphony beyond cooperation (symphony-template; thread "Symphony beyond cooperation")

The programme is docs/research/beyond-cooperation/README.md: what one agent spends (context, tool calls, reading, time), measured from the transcript by tools/profile.py with no tokens spent, MAST's 14 failure modes as the outcome side, a seven-step loop, one pull request per step. Step 1, the Symphony-Profile commit trailer, merged as #104, its usage-hook fixes as #107.

Step 2, summing the profile lines per pull request into a new file, PROFILE.json (per pull request, by work setting, alone against parallel), is draft #116 (branch claude/symphony-beyond-cooperation-guc8hl, head 08f2715 at the thread's checkpoint of 19:07 UTC), pushed, green and not merged. Its adversarial review found nine points, none fixed yet: the change to the stored run records would drop some runs from the shared metrics for up to 60 days, and eight smaller ones. Nothing waits on the owner.

Where the state lives in git, all on that branch: the code and tests (tools/, tests/ and the metrics workflow); docs/research/beyond-cooperation/step-2-review/ (the review's findings, the steps for a session on another account and the scripts that reproduce the findings); docs/research/beyond-cooperation/scripts/ (the scripts behind earlier figures). #116's Checkpoint 2026-10-16 section lists every step.

Brief for a new thread: "Read docs/checkpoints/2026-10-16/handoff.md part 2.4 and the Checkpoint 2026-10-16 section of symphony-template#116. Check out its branch claude/symphony-beyond-cooperation-guc8hl, merge main into it, read docs/research/beyond-cooperation/step-2-review/README.md and fix the review's findings in order, the 60-day gap in the shared metrics first; run bash scripts/check.sh, mark #116 ready and merge once green. Then step 3 of docs/research/beyond-cooperation/README.md's loop, one pull request per step. No run that spends tokens without my word."

### 2.5 Agentic workflow benchmarks (flowbench; thread "Agentic workflow benchmarks")

Done, nothing open (the thread's checkpoint of 18:57 UTC): symphony-template#96 (flowbench's design, plan, parity table and tested scaffold), flowbench#1 (everything moved to OpenSpineConsortium/flowbench, 114 tests, a7fce3c) and symphony-template#115 (the old copies removed; docs/research/flowbench/README.md points at the repository; 49da1b3). No tokens spent yet.

Waiting on the owner: the pilot, 8 SWE-bench Verified issues under solo, script and symphony, 24 runs, Sonnet 5.5 at medium effort unless the owner names others, about one to two five-hour windows of one account (an estimate until measured), no API billing; until the symphony workflow's merge gate is wired its results show only its shape. The owner writes "run the pilot" to start it (owner-todo.md, item 9).

Since then symphony-template#121 (docs/research/flowbench/scaffold-review.md, the scaffold review's 31 findings with their answers) merges once green; the resumable state is docs/research/flowbench/README.md on main. The owner's two documents attached in the thread are this Project's uploads, not in git.

Next for a session, spending no tokens: wire the symphony arm's merge gate from coordbench's sdlc arm (flowbench's PARITY.md row 15), close the review's open items where code can, and survey the first 32 issues' gold patches to confirm their images grade.

Brief for a new thread: "Attach OpenSpineConsortium/flowbench with push access. Read docs/checkpoints/2026-10-16/handoff.md part 2.5 and flowbench's DESIGN.md, PLAN.md and PARITY.md. Read docs/research/flowbench/README.md and scaffold-review.md here. Wire the symphony arm's merge gate from coordbench's sdlc arm (PARITY.md row 15), close the review's open items where code can, and survey the first 32 issues' gold patches to confirm their images grade, each by pull request, spending no tokens. Run the pilot only on my 'run the pilot'."

### 2.6 Symphony control website (the site, symphony-app, symphony-start; thread "Symphony control website")

The control panel https://openspineconsortium.com/symphony/control/ and the cost page https://openspineconsortium.com/symphony/cost.html are live (site #20). Sign in with GitHub is their first button, the fine-grained token folded under it (site #22, the owner's choice of 09:09 UTC), with the fifth review's fixes (site #23, master 009109c); the sign-in service is symphony-app's signin/worker.js, with its setup steps in signin/README.md (symphony-app #15); the privacy statement is at version 9 (symphony-start #44, #45). The 112 browser checks of the sign-in, the 79 mutants (each caught against master 009109c) and the five adversarial reviews' scripts and reports are in symphony-app's signin/panel-checks/, with a README on running them (symphony-app #16, main eeed037); CI does not run them. The notes are docs/research/control-panel.md and docs/memory/the-control-panel.md (symphony-template #109, #114 and #120, all merged; main f7585b5). Nothing of the thread is unpushed or unmerged, and it has no open pull request.

The button stays greyed out until the owner finishes the six sign-in steps (owner-todo.md, item 4): at 18:54 UTC he was at step 1, and the thread told him to generate the App's client secret, not to change the webhook secret, and to leave "Request user authorization (OAuth) during installation" unticked and the Setup URL as it is. The two values the button waits for are the empty `var SIGNIN_SERVICE = '';` and `var CLIENT_ID = '';`, lines 38 and 39 of the site's assets/js/symphony-panel.js. The thread's checkpoint reply of 19:10 UTC gives the same steps and the same next moves.

Brief for a new thread, once the owner sends the Worker's address and the Client ID: "Attach OpenSpineConsortium/openspineconsortium.github.io, OpenSpineConsortium/symphony-app and OpenSpineConsortium/symphony-template with push access. Read docs/checkpoints/2026-10-16/handoff.md part 2.6 and docs/research/control-panel.md. With the Worker address and Client ID I give: check that the address answers {"service":"symphony-signin",...}; set SIGNIN_SERVICE and CLIENT_ID in assets/js/symphony-panel.js in one site pull request, checked in a local render; in symphony-app, change the configured line near the top of signin/panel-checks/e2e2/signin.test.mjs to the new lines and run the checks as its README says; merge each once green; try Sign in with GitHub on https://openspineconsortium.com/symphony/control/; and update the notes."

### 2.7 Symphony on the WSU grid (hpcworker, symphony-template; thread "Symphony on the WSU grid")

Done, nothing open (the thread's checkpoint of 19:00 UTC): hpcworker#13 (the runner, tools/grid_runner.sh, a self-hosted runner served as a chain of Slurm jobs, merge d8a03e7) and symphony-template#103 (.github/workflows/grid.yml, docs/setup/grid.md and the research note, merge d669562), with the review's eleven fixes. Everything the thread found is docs/research/wsu-grid-and-github-actions.md, to which symphony-template#118 adds where it stands, the ssh gate's plan and the proofs. Waiting on the owner's three steps (owner-todo.md, item 6): one CI line in hpcworker (a session may not write workflow files there), starting the runner from the grid's shell, and the test of whether a key alone signs in from outside the VPN, with C&IT's word on such a key if it has come.

Next for a session, once the owner sends the test's output: the ssh gate's pull request, a key on the grid that can run only one fixed command, kept as a GitHub environment secret, so the owner's password is never stored.

Brief for a new thread, once the owner sends the test's result: "Attach OpenSpineConsortium/hpcworker and OpenSpineConsortium/symphony-template with push access. Read docs/checkpoints/2026-10-16/handoff.md part 2.7, docs/research/wsu-grid-and-github-actions.md and docs/setup/grid.md. Open the ssh gate's pull request for the result I give, with an adversarial review, and merge once green."

### 2.8 Beethoven worker opening (beethoven-extension; thread "Beethoven worker opening")

Done, nothing open (the thread's checkpoint of 18:58 UTC): beethoven-extension#17 (Beethoven 21.0.0, the main button opens the student's named Claude project, 87e06c8), symphony-template#101 (docs/research/beethoven-worker-opening.md, 635a44f) and site #21 (terms 15, privacy 16, the support page's paragraph on projects, 07200e6); symphony-template#122 (32c9335) keeps 21.0.0's two review rounds and its release state in git. The owner set the store secrets; the release run of 18:49 UTC uploaded 21.0.0.108, which the Chrome Web Store holds as Beethoven's new draft, not yet submitted for review (owner-todo.md, item 5). Not yet measured, as the note says: whether the worker's next job keeps a project's thread connected, and the worker with --spawn worktree.

### 2.9 Finished threads

- Claude token setup wizard: symphony-template#100 and #105 merged; docs/research/token-wizard.md, docs/setup/claude-tokens.md. Nothing open; the owner's run of scripts/tokens.py is owner-todo.md, item 7.
- Integrating outside code bases: symphony-template#98, docs/research/outside-code-bases.md; no integration code until the owner chooses.
- Symphony versus competitors: symphony-template#97, docs/research/symphony-versus-competitors.md (and its Claude Doc).
- Research notes in git: symphony-template#99, .claude/rules/research.md.
- The taxonomy spec and manual are parked where the 2026-10-15b handoff left them (docs/checkpoints/2026-10-15b/taxonomy/).
- The threads of 2026-10-14 and 2026-10-15 are finished and not to be reused.

## 3. What lives outside GitHub

In this Project's shared folder (/mnt/project-files), which a new account cannot read:

- grant/: the 10-page PDF of 10:44 UTC (twice, as AIDaS_SEED_2027_proposal_2026-10-16.pdf and AIDaS_SEED_2027_draft_2026-10-16.pdf), AIDaS_SEED_2027_overleaf.zip (holds contacts.tex and both biosketches, personal data, never committed) and AIDaS_where_it_stands_2026-10-16.md (the thread's note to the owner, carried into spine-program's HANDOFF_2026-10-16.md and RECORD.md). All of them predate Dr. Schwiebert's update of the addresses; the owner's Overleaf project is the current copy and holds the private files, so nothing here needs keeping.
- coordbench/curse-1-logs-2026-10-16.tar.gz (about 45 MB): the bench's logs with the agents' transcripts, the workspaces left out; transcripts stay out of git by the research rules. A new account restores the queue from what the bench thread committed to coordbench (part 2.3); the owner may download the archive to keep the transcripts (owner-todo.md, item 2).
- grid/your-grid-steps.md: the grid steps, the same as docs/setup/grid.md and owner-todo.md, item 6.
- control-panel/: the sign-in's screenshots and an archive of its checks, with a README; the same checks are in git, in symphony-app's signin/panel-checks/ (symphony-app #16), so a new account needs nothing from here.
- uploads/hearth/: the owner's uploads (the biosketches, the IRB form, Dr. Han's edits); personal data, never committed.

Also outside GitHub: the owner's Overleaf project for the grant (its link is only in his e-mail of 7:51 a.m. ET, since anyone who holds it may edit the project); this account's Claude Docs ("Symphony versus competitors", https://claude.ai/code/artifact/a1cb9900-9020-49ec-8d96-6781a0d3a523, whose copy is docs/research/symphony-versus-competitors.md); and the Project's memory, copied verbatim in memory.md beside this file.

## 4. Watch for

- Until symphony-protocol 0.5.0 is published, its weekly sync (Mondays 06:17 UTC, next 2026-10-19) opens a symphony-template pull request "Vendor symphony-protocol 0.4.1", a downgrade from the 0.5.0 the template already vendors; its check stays red. The owner closes it (owner-todo.md, item 8); no session fixes its check. Once 0.5.0 is published the sync carries 0.5.0 instead.
- Once CWS_ON_PUSH is publish, every merge to beethoven-extension main is a Chrome Web Store submission, so a merge there is a release to students.
- Three Dependabot pull requests opened in symphony-template on 2026-10-16 (#111 upload-artifact 4 to 7, #112 setup-python 5 to 7, #113 create-github-app-token 1 to 3); no thread owns them.
- A thread can stop on a WebSearch permission prompt: tell the owner in one line where to approve it.
- A thread's container can restart: only pushed work survives. Stopped threads can wake at a usage reset and act: tell a thread to stop in words and confirm it unsubscribed from its pull requests.
- When several threads merge into symphony-template at once, main's up-to-date rule makes each pull request chase main: once the merge of main passes bash scripts/check.sh and is pushed, turn on auto-merge with the merge method MERGE.

## Rules

One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
