# The Project's memory, as of the 2026-10-16 handoff

The symphony Project keeps its memory outside GitHub, as a store of files that another account cannot read. This file is that store copied verbatim at 19:05 UTC on 2026-10-16, one section per file, each file's text in a fence: MEMORY.md, the index every session loads, first, then the other files by name. The one change is that two e-mail address fragments in aidas-grant-2027.md are left out of git; the Outlook draft holds them. If the next session is on another account or in a new Project, save each file below under its name as that Project's memory before starting threads (MEMORY.md as the index, the others as files beside it), dropping the fence lines. It is newer than docs/checkpoints/2026-10-15b/memory.md, which the four project-memory-2026-10-15b-* files below were saved from. Where a pull request's own description or a thread's checkpoint of 2026-10-16 says otherwise, that is newer.

## MEMORY.md

````markdown
# symphony project memory
Coordinator index; fuller 2026-10-15b memory in the four project-memory-2026-10-15b-* memory files and symphony-template's docs/checkpoints/2026-10-15b/ (handoff.md, memory.md, owner-todo.md). A pull request's own description is newer where they differ. Keep this file under 15 KB (the store's cap is 16,384 bytes).

## People and repositories
- Owner and only member: greg (GitHub Gregory-Schwing-MD-PhD); organization OpenSpineConsortium.
- symphony-template is the Project's repository: handoffs in docs/checkpoints/<date><letter>/ (read the newest, then CLAUDE.md and .claude/session.md), research notes in docs/research/. Main takes a branch up to date with main whose required "check" is green; merge commits; head branches auto-deleted.
- Threads attach with push access as needed: symphony-protocol (the library), coordbench, symphony-protocol-canary, symphony-app, spine-program (grant and spine research), beethoven-* (greg's proprietary software), openspineconsortium.github.io (the website), hpcworker (the grid runner), flowbench (new 2026-10-16).
- Sessions cannot delete branches, approve deployments or publish releases; gh GraphQL is blocked, REST works. The coordinator starts with no repository attached. The Project's PR list can miss coordbench's and flowbench's.
- Threads have greg's Claude Docs, Microsoft 365 (WSU Outlook) and Google Drive connectors, no Gmail; sending mail asks his permission, and no connector can send or upload a file, so an e-mail with a file is a thread's draft that greg attaches to and sends.
- Switching accounts needs no local pull: threads clone fresh; only the Project's chat and memory stay behind.

## Rules and conventions
- greg's standing rules are the Project's instructions, verbatim since 2026-10-15 23:16 UTC.
- Merge commit with the head sha copied from git; bring main into a branch by merging, never rebase or force-push.
- Research notes live in git (greg, 2026-10-16 00:20 UTC): every thread commits its findings under docs/research/ before checkpointing, each PR adding its line to the index docs/research/README.md; .claude/rules/research.md loads the rule into every session (symphony-template#99). Every brief says so.
- Manual steps for greg go in the reply's own text, numbered, each with its exact link and what to click; never only on a card, widget or file (2026-10-16 09:58: he saw no card and angrily asked for the steps reprinted with links). Every brief says so.

## How greg wants the coordinator to work
- One thread per handoff item, at most three at once; greg's own asks get their own thread regardless.
- One line in the project chat as each pull request lands; big-picture answers grounded, with the evidence as a file; pace in product terms. Merges may not wake the coordinator (threads reply at milestones): on each wake check list_project_prs and thread checklists against the last line.
- Cross-thread relays carry greg's message attached; a correction goes to every thread told before. A decision card's tap has no message id and the card itself is refused as context: relay the choice in words and check the result says delivered.
- Usage limits: a thread at a limit is not stuck while it lasts, but one whose notice says "Send another message after that to continue" does not resume alone: at the reset time it gives (arm send_later), nudge it. After an outage or a recycle, read the timeline's tail for unanswered messages.
- "Push and checkpoint": every thread pushes, writes a "Checkpoint <date>" section atop each open PR's description, replies and stops; one thread writes the handoff under docs/checkpoints/ with memory.md and owner-todo.md.
- greg chose "Keep going" past the weekly limit (2026-10-15); don't re-ask unless he raises cost. Never all his tokens on the experiment; it grows by strata, his choice at each step.
- He wants work running, not parked: never put a thread's work off to spare the usage window unless he says so (2026-10-16: he un-paused the bench 39 minutes after pausing it, and wrote "wtf push this" at a rebuild deferred past the grant deadline). New spend that is his call (a pilot, a new batch) still waits for his word.
- Threads reply with results, blockers or decisions only; step progress goes in update_status.
- greg often dictates: expect sound-alikes ("ADIS" for AIDaS, "Warren" for Loren) and check names against the record before acting on them.

## Decisions
- Protocol: the library fix for every finding; correctness over cost; no deadlock, missed work or orphaned worker. Keep Symphony's protocol over gh-aw; Candidate A (Symphony's compiler generating the eleven workflows with claude-code-action on the subscription token) after 0.5.0; a gh-aw pilot on the canary after greg releases 0.5.0 (docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md).
- 0.5.0: symphony-protocol#36 (F8's follow-up) and #37 (the stuck claim; it raises the version) merged 2026-10-16; the release run waits for greg's approval at https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117 ("Review deployments", tick "release", "Approve and deploy"). Since merged: symphony-protocol#38 (board-run API calls), #39 (F21), #40 (429 retry), a template note timing claims, symphony-template#110 (medians). In review for 0.5.1, two reviews each: #41 (F23), F22, guard gaps F24-F26; then vendoring main into the template. Never the release or its gate.
- Grant: VinDr and FluoroCap results stay in; greg has permission and signed data use agreements for all data, so never raise data permission or IRB scope; spine-program's rule 9 stays (nothing retrained). The packet takes Dr. Han's edits word for word and changes only as greg asks; no adversarial reviews on spine-program (greg, 2026-10-16 10:17: "literally just make the fine tweaks that I'm asking for and regenerate"). Framing (greg, 2026-10-16 02:30 UTC): SpineAI is the case example of what the AI-assisted tool does in a short time; the goal is a customizable multimodal spine RAG-LLM on his X-ray detector and his Scopus and ScienceDirect text, image and multimedia corpus, fine-tuned on images paired with clinical charts under the IRB (amended as needed), compared with or augmenting the OpenEvidence plugin for Claude.
- Experiment: no coordination data in the grant until greg has run the full suite and tried xblossom. The full run is the remaining pairs under five arms, no xblossom; its four batches run back to back, stopping only at a limit or greg's word, no re-ask per batch. Bench agents at xhigh effort. Running since greg's "Just continue" (2026-10-16 09:37): the 12 reruns ran clean (coordbench#24, #25); the step of 8 merged as coordbench#26 (passes of 8: solo 5, coop 7, sdlc 7, coop-git 6, team 7, no curse; sdlc 1.5x coop's wall time, 1.4x its tokens); 9-16 and 17-24 done by 17:28 UTC (80 runs, clean), then 25-32, 33-43; one PR records all 175 runs.
- Outside code bases: no integration code until greg chooses. The assessment (symphony-template#98, docs/research/outside-code-bases.md) recommends no library or copied code, and DeLM's check receipts and Claim Plane's pre-write admission (with its serial baseline) as coordbench arms after the full run, each on greg's go-ahead; protocol changes only after 0.5.0, where an arm gains.

## The grant (AIDaS seed 2027, spine-program)
- 01_carm_level_detection/grants/aidas_2027/ (latex/main.tex, RECORD.md, APPROXIMATIONS.md, make_overleaf_zip.sh). Due 2026-10-16 11:59 p.m. ET (03:59 UTC on the 17th), a PDF e-mailed to aidas@wayne.edu. PI Zhizhong Han, Co-PI Loren Schwiebert. 10 pages.
- Private, never in git: contacts.tex, the two biosketch PDFs (uploaded here 2026-10-14 20:03 UTC), the IRB form; rebuild by copying the first three beside latex/main.tex and running `bash make_overleaf_zip.sh <out>`.
- Aim 1: Claude Code iterating the scientific method inside Beethoven's frameworks; no award funds to Beethoven; what is specified but not built is said so. Literature questions go to a grid-hosted model, never Claude.
- State at 10:45 UTC on 2026-10-16: spine-program#107, #109, #111 and #113 merged; the 17 fill-ins are approximations tracked in APPROXIMATIONS.md with who can confirm each; greg's $1,500 Claude-subscription reimbursement is line C3, payable once his adjunct appointment starts; $19,987 requested, under the $20,000 cap. Final PDF: /mnt/project-files/grant/AIDaS_SEED_2027_proposal_2026-10-16.pdf. The e-mail to Han and Loren Schwiebert (greg plans, pending their approval and his adjunct appointment, to submit today to AIDaS, Anthropic's AI for Science program and other fits, with them as PI and co-PIs) is a draft in greg's Outlook: he attaches that PDF and presses Send, and attaches it to the aidas@wayne.edu submission too.

## The coordination experiment (coordbench)
- Replicate CooperBench's curse of coordination, then remove it with Symphony's protocol (the sdlc arm): latency, tokens, cost. One cloud session drives bench agents as Sonnet subagents of Workflow lanes, no Claude token; sdlc pinned to symphony-protocol c7f0d84. About 34 runs per five-hour window at four lanes, sharing that window with every thread; disk about 40 GB, keep 2 GB free.
- Agents re-read an inherited prompt of about 80,000 tokens per call, inflating every arm alike; grant figures need standalone agents in GitHub Actions. Every run writes audit.json; spoiled runs are rerun and left out. Notes: bench/cooperbench/results/curse-of-coordination-notes/ (its README's "The next steps, in order"). Grant format: one-line setup, k of n with Wilson intervals, sdlc against coop with ranges, ASCII, source paths.

## Product state
- 0.4.1 (2026-10-13) is the latest approved release. Harness steps 1 to 7 merged (c7f0d84), step 8 not started. One subscription OAuth token per repository. Readiness: docs/checkpoints/2026-10-14c/notes/readiness-research-2026-10-14.md.
- Control panel https://openspineconsortium.com/symphony/control/ and cost page https://openspineconsortium.com/symphony/cost.html are live. Sign in with GitHub is their first button (greg's choice, 2026-10-16 09:09 UTC, the fine-grained token only a fallback; site #22), greyed out until greg does the six steps (the control website thread's 09:18 UTC reply; symphony-app signin/README.md) and sends his Worker address and Client ID; then one small site PR switches it on.
- Token wizard (symphony-template#100, fix #105, 2026-10-16): greg runs scripts/tokens.py from his WSL clone after a git pull to put each Claude account's token into an Actions secret unseen (docs/setup/claude-tokens.md; commands in the wizard thread's reply of 09:19). A hand-made SYMPHONY_CLAUDE_ACCOUNTS variable on coordbench must go (https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions).
- Beethoven 21.0.0 (beethoven-extension#17, 2026-10-16): the main button opens the student's named Claude project (research note symphony-template#101); site terms v15, privacy v16 and support pages merged (openspineconsortium.github.io#21). Once greg sets the five store secrets (the Beethoven thread's reply of 09:59; values only on GitHub's secrets page), the release workflow submits 21.0.0, then every merge to beethoven-extension main, to the Chrome Web Store; "Cancel review" in the store dashboard withdraws one before Google approves.
- Grid runner (hpcworker#13, symphony-template#103, 2026-10-16): greg's three steps (a CI line in hpcworker, start the runner from the grid's shell, an ssh key test from off the VPN) are in /mnt/project-files/grid/your-grid-steps.md and the grid thread's reply; he sends the test's output, then the ssh gate's PR follows.
- Beyond cooperation (symphony-template#94): docs/research/beyond-cooperation/README.md (MAST's 14 failure modes as the outcome side, a seven-step loop, one PR per step) and tools/profile.py (measures a session from its transcript, no tokens). Step 1, the Symphony-Profile commit trailer, merged as #104, its usage-hook fixes as #107 (2026-10-16); step 2, summing profile lines per PR, next.
- flowbench: design, pre-registered plan, SWE-bench parity table and harness now live in OpenSpineConsortium/flowbench (greg's README 2026-10-16 18:22 UTC, then the thread's scaffold, 114 tests green); symphony-template#115 dropped the moved copies and points docs/research/flowbench/ at it; no tokens spent yet. The pilot (8 issues, 3 workflows, 24 runs, one to two five-hour windows) waits for his "run the pilot".

## This Project
- Every thread runs in cloud environment env_01QDsuE2x1HyEQtSVLLzpyFY, never on greg's PC.
- Threads (2026-10-15 23:40 UTC, one per 15b handoff item; item 4, taxonomy, parked): [Protocol fixes toward 0.5.0](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5S2uzbropCvbexxKMRBLBvW) (0.5.0 waits on greg's approval); [AIDaS seed grant](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5ReL4gqweYbk3fU61Spjs9m) (the e-mail waits on greg); [Curse-of-coordination runs](#cmsg_01JV1B5DpVW16Xd9rDo7wKF528RgMxWjsrU6W3nd1dToYW) (running); [Symphony beyond cooperation](#cmsg_01JV1B5DpVW16Xd9rDo7wKF59CAHYLAgAvqpiVVAYrErre) (step 2); [Agentic workflow benchmarks](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5Ai2DPBtG4KbNNknSdb5xDF) (waits on greg's "run the pilot"); [Symphony control website](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5PCdfxH72p1rTxmkv35X1Cf) (sign-in waits on greg's six steps); [Symphony on the WSU grid](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5GBoY6vc7K6ByhYb9iEGoQy) (waits on greg's three steps); [Beethoven worker opening](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5LiXyHY4w2vHXyyxvJZDrxE) (store secrets with greg). Done: Integrating outside code bases (#98; asks which autonomous-software-agent repository greg meant), Claude token setup wizard (#100, #105), the competitors and research-notes threads (#97, #99).
- Threads of 2026-10-14 are finished and not to be reused.
- Reminder 2026-10-17 04:05 UTC "Check on the coordination bench" fires into the bench thread, which owns it; harmless if the bench runs.

## Watch for
- Until 0.5.0 is published, the Monday 06:17 UTC sync (next 2026-10-19) opens a symphony-template PR "Vendor symphony-protocol 0.4.1", a downgrade with a red check; greg closes it at https://github.com/OpenSpineConsortium/symphony-template/pulls (open it, "Close pull request"); don't fix it.
- Threads can stop on a WebSearch permission prompt: tell greg in one line where to approve it.
- From 2026-10-16 04:47 UTC each thread's own model sits at its weekly limit (reset 2026-10-22 21:00 UTC); sessions go on on their fallback model.

## Lessons
- Stopped threads can wake at a usage reset and act: tell a thread to stop in words and confirm it unsubscribed from its PRs.
- Repository notes can carry caveats greg has settled (the D1/IRB caveat annoyed him twice): check before raising one.
- Do not assume a memory file exists because a message names it. Auto mode refused a coordinator helper's write to /mnt/project-files.
- A new repository's first commit is greg's: the sessions' push guard refuses any push to a default branch, even an empty repository's first. When a thread asks greg to create a repository, it tells him to tick "Add a README" in the same step.
- Thread-level lessons (containers restart, accounts sharing branches, scrub tests, merging into a busy main) are in the project-memory-2026-10-15b-lessons memory file.
````

## aidas-grant-2027.md

````markdown
---
name: aidas-grant-2027
description: The AIDaS seed grant packet in spine-program (#107 to #113 merged 2026-10-16): state, holds, greg's rules for it and what he still owes before the 2026-10-16 11:59 p.m. ET deadline
metadata:
  type: project
  modified: 2026-10-16T10:44:55.472Z
---

Folder: spine-program 01_carm_level_detection/grants/aidas_2027/. Due 2026-10-16 11:59 p.m. ET (03:59 UTC on the 17th), one PDF to aidas@wayne.edu. Thread: [AIDaS grant](#cmsg_01JV1B5DpVW16Xd9rDo7wKF5ReL4gqweYbk3fU61Spjs9m). Merged 2026-10-16: #107 (RAG-LLM framing), #109, #111 (one figure panel), #113 (10379a7: every red mark now an approximation in APPROXIMATIONS.md; line C3 repays $1,500 of greg's Claude subscriptions once his pending WSU adjunct appointment begins; $19,987 under the $20,000 cap).

**State.** 10 pages, no red mark. The final PDF, the Overleaf zip and a note for greg are in /mnt/project-files/grant/; the copy to attach is AIDaS_SEED_2027_proposal_2026-10-16.pdf. The e-mail to Zhizhong Han ([address left out of git]) and Loren Schwiebert ([address left out of git]; greg's dictated "Warren") is an Outlook draft, "AIDaS seed grant: final PDF for your approval". No connector can attach it: Outlook refuses attachments, greg's account has no Gmail connector, and the OneDrive and Google Drive uploads take the file inline in one call, too large at 362 KB. greg attaches and sends, and the same holds for the submission.

**Why:** every number carries its file (rule 2); an approximation carries its row in APPROXIMATIONS.md.

**How to apply:**
- greg, 10:17 UTC: no adversarial reviews on spine-program; make only the tweaks he asks and regenerate.
- Holds: no coordbench data until greg runs the full suite; VinDr and FluoroCap results stay; never raise data permission or IRB scope; rule 9 stays; never name SchwingNet, FluoroCap or XRSpinoPelvic1K; never "provenance"; captions at most 60 words; no personal phone or e-mail in a repository file. Elsevier content never trains a model or reaches an outside AI service.
- greg owes: the e-mail; real values for the approximations; the allowability question (B, C3, D, F) to aidas@wayne.edu; the disclosure audit (rule 8); Overleaf; the submission. Anthropic's AI for Science program and other fits are his plan too.
- Rebuild: contacts.tex (the PI's second number labelled "cell") and both biosketches are in the Overleaf zip; put them beside latex/main.tex and run `bash build_pdf.sh` for the 10-page PDF; without them it builds the tracked 8-page draft.

Related: [[greg-working-style]], [[symphony-project-threads]].
````

## beethoven-project-route.md

````markdown
---
name: beethoven-project-route
description: Beethoven 21.0.0 opens the student's Claude project (merged 2026-10-16); the site's texts and the store submission
metadata:
  type: project
  modified: 2026-10-16T09:27:37.909Z
---

Beethoven 21.0.0 merged 2026-10-16 09:24 UTC (beethoven-extension#17, merge 87e06c8): with a project's address in Settings, the main button is *Open my project* and the open-on-connect tab is the project's page, because a Claude project cannot take the session the worker starts itself and reaches the worker only through its own *Work locally* (+ menu, then *Allow once*). Agreement 15, privacy 16. The research note is docs/research/beethoven-worker-opening.md in symphony-template (#101, merge 635a44f), with what is not yet measured (the successor job's --continue against a project's thread, --spawn worktree, which folder the card offers).

**Why:** greg's item 9 of 2026-10-15 and his 00:28 UTC goal of one grid session with projects, cloud sessions and the grid's hardware.

**How to apply:**
- Done on greg's "wtf push this" (2026-10-16 09:41 UTC): the site's terms.html and privacy.html show 15 and 16, with a projects paragraph on support.html (site openspineconsortium.github.io #21, merge 07200e6; its build needs beethoven-extension, beethoven-vscode, symphony-extension and symphony-start cloned beside it); the scheduled rebuild was cancelled.
- The 21.0.0 release run was started by hand on main with upload and publish ticked (release.yml, 21.0.0.108); auto mode then refused reading the run ([Create Public Surface]). greg asked how to set the store secrets, so its store step most likely said "Not configured". At 09:59 UTC the thread gave him eight steps with links: Google's OAuth client and refresh token, the publisher and item ids, the five CWS_ secrets, CWS_ON_PUSH=publish, then Run workflow with upload and publish to send 21.0.0.
- Once those are set, every merge to beethoven-extension main is a Chrome Web Store submission (upload plus submit for review), so a merge there is a release to students.
- Steps greg must do go in the reply's text with links, never only on a card: his app showed no step card.
- hpcworker needed no change; the grid runner is the separate thread "Symphony on the WSU grid".

Related: [[aidas-grant-2027]].
````

## cloud-environment-unreachable-hosts.md

````markdown
---
name: cloud-environment-unreachable-hosts
description: Which web hosts a cloud thread of this project cannot reach (DNS or policy), checked 2026-10-16, so a thread does not spend calls on them
metadata:
  type: project
---

From the project's cloud environment (env_01QDsuE2x1HyEQtSVLLzpyFY), WebFetch fails with ENOTFOUND (no DNS) for huggingface.co, datasets-server.huggingface.co, www.alphaxiv.org, neurips.cc, sites.google.com, mlanthology.org, dev.to, grith.ai and web.archive.org; arxiv.org (ar5iv and export too), cooperbench.com, cursor.com and docs.github.com are blocked by policy; api.github.com answers WebFetch 403 and github.com's HTML pages 403, while raw.githubusercontent.com serves public files and WebSearch works. Checked on 2026-10-16 by the beyond-cooperation thread while reading MAST (arXiv:2503.13657, dataset mcemri/MAST-Data).

**Why:** a paper on arXiv or a dataset on Hugging Face cannot be read from a thread; what it needs is fetched by the owner or a local session, or read through a secondary copy on GitHub (raw) and WebSearch quotations, and the page that cites it says so.

**How to apply:** before reading a paper or dataset, try a raw GitHub mirror or WebSearch first; do not retry these hosts; ask the owner for a file only when the work needs its content, with the exact link. See [[symphony-project-memory]].
````

## coordbench-bench-agents-effort-is-pinned.md

````markdown
---
name: coordbench-bench-agents-effort-is-pinned
description: coordbench's session lanes pin the bench agents' reasoning effort (curse-1 runs at xhigh); a subagent otherwise inherits the orchestrating session's effort, which differs by account
metadata:
  type: project
---

A Workflow subagent thinks at the orchestrating session's effort unless the agent() options name one. The curse-1 pilot, step of 8 and xblossom screen (2026-10-15) ran from a session at xhigh; the rerun session of 2026-10-16 ran at max, and its first solo rerun of outlines 1655 f6_f7 passed at max where the xhigh redo failed. Since coordbench#22 (merged 2026-10-16 04:38 UTC as a491803) lane.js takes args.effort and every curse-1 lane is started with effort "xhigh"; audit.json records each agent's efforts per run.

**Why:** a run carried on from another session would otherwise mix budgets across arms and sessions, and the difference changes pass rates.

**How to apply:** every lane of a curse-1 run names effort "xhigh" (the notes README's step 3); a new experiment picks one effort and names it on every lane; check audit.json's efforts when comparing runs from different sessions. See [[project-memory-2026-10-15b-grant-and-experiment]].
````

## coordbench-curse-1-how-to-run.md

````markdown
---
name: coordbench-curse-1-how-to-run
description: How the curse-1 bench run is driven between batches, which pairs run alone, when a timed-out suite is scored again, and how a fresh container restores the run
metadata:
  type: project
  modified: 2026-10-16T17:28:39.285Z
---

The bench runs at effort xhigh from /home/user/coordbench, detached at main. Move that checkout only while images-full.sh is stopped, since bash reads a running script from its file. A lane ends when no item is pending, and a lane still alive takes newly released items, so check the queue before starting another. The thread's scratchpad batch-boundary.sh PAIRS does a boundary: checks nothing is open, checkout to main, requeue --harness-only, timeout scan, archive refresh, resume, image loop with its pid.

Heavy pairs run alone: typst (10 GB image, two-agent workspaces about 11 GB) and outlines 1655 (image 13 GB, evaluation 7 to 10 GB more) are held paused (queue.py set Q ID status=paused, one at a time, never pause-all while lanes run) until the batch's light pairs finish; then the image loop (restarted, pid recorded) removes other images and one lane runs them, outlines before typst.

Timed-out suites are scored again (PARITY.md row 23, narrowed in #26) only where the time plainly went outside the tests (the runner has its own `timeout 300`: outlines 1655, dspy 8394, go_chi 26/56, datasets 6252; or the cascade's run of the same patch finished the suite), once; skip a run that has eval.first-scoring.json. The notes README's step 6 gives the commands. Done once: sdlc outlines 1655 f6_f7.

State: the logs, transcripts included, workspaces left out, in /mnt/project-files/coordbench/curse-1-logs-2026-10-16.tar.gz (refreshed at each boundary, last 17:25 UTC). A fresh container: bench/cooperbench/setup.sh, untar that archive in ~/cooperbench (it holds logs/), else run/restore-bundles.py over the three bundles plus the notes' queue; requeue --harness-only; resume the batch in progress; images-full.sh from main with its pid; three lanes at effort xhigh. The check-in trig_01N5QFH5dH3WvwK9U3JB7a7c at 04:05 UTC on 2026-10-17 restarts it if it stopped. Progress: [[coordbench-curse-1-progress]].
````

## coordbench-curse-1-progress.md

````markdown
---
name: coordbench-curse-1-progress
description: Where the curse-1 bench run stands on 2026-10-16 (reruns done, step figures merged, full run batch by batch with each batch's figures) and what is left
metadata:
  type: project
  modified: 2026-10-16T18:40:52.942Z
---

greg paused the bench at 08:58 UTC on 2026-10-16 and lifted the pause at 09:37 ("Just continue"). The 12 reruns are done and clean. The full run goes batch 9-16, 17-24, 25-32, 33-43 back to back on greg's "All batches" (00:56 UTC), stopping only at a limit or his word.

- Step of 8: merged as coordbench#26 (83933e8, 12:45 UTC): solo 5/8, coop 7, sdlc 7, coop-git 6, team 7; greg told.
- Batch 9-16: done 13:03 UTC, 40 runs, all clean, none timed out, 22 passed (solo 6/8, each two-agent arm 4/8: pillow 25 f1_f5 and dspy 8394 f3_f5 only solo solved).
- Batch 17-24: done 17:25 UTC, 40 runs, all clean, none timed out, 39 passed (sdlc 7/8: on typst f1_f9 the naive merge conflicted and its lead submitted only its own feature; agent2's patch alone passes both). greg told of both batches at 17:30, as interim and not for the grant.
- Batch 25-32: done 18:39 UTC, 40 runs, all clean, none timed out, 24 passed (coop 4/8, the rest 5/8). Over the 33 pairs then done (step of 8 included): solo and team 24 passed, coop, sdlc, coop-git 23; greg's 17:30 reply was edited to say so (no new notifying reply).
- Batch 33-43: from 18:40 on three lanes, 50 runs (click 2068 f2_f10 was done before), image loop pid 16178, archive refreshed 18:40 (45M); no heavy pair, so three lanes throughout.

Then record the full run in coordbench by PR (subset, report, summary, bundle; adversarial review; check.sh; merge once green). No coordination data goes into the grant until then. How to run and restore it: [[coordbench-curse-1-how-to-run]]. See also [[coordbench-bench-agents-effort-is-pinned]] and [[project-memory-2026-10-15b-grant-and-experiment]].
````

## greg-data-permission-all-data.md

````markdown
---
name: greg-data-permission-all-data
description: greg has permission and signed data use agreements for all datasets (VinDr, FluoroCap included); never flag data directive D1 or IRB HPR 2026-269 scope as a reason to drop results
metadata:
  type: feedback
  modified: 2026-10-14T22:17:40.409Z
---

greg, 2026-10-14 22:16 UTC, in the AIDaS grant thread: "wtf is my data directive and supposed IRB scope? I've gotten
permission to use any and all data and filled out all data use agreeement forms". Earlier (22:05 UTC): "I don't
understand why I would exclude vindr amd fluorocap. Just do whatever gets better results".

**Why:** a thread had offered "clean" numbers because spine-program's notes (01_carm_level_detection/docs/handoff/
RESULTS_CATALOG.md A3 header, DATASET_USAGE.md section 5, root CLAUDE.md rule 9) say the C-ArmLSpine fold models
"break directive D1 and the IRB scope". D1 is greg's own data-quality order of 2026-09-23 (FluoroCap out of training,
being mostly copies of published figures); the IRB note was that VinDr's PhysioNet agreement put it outside the public-
data umbrella HPR 2026-269, which greg told a session on 2026-09-25 to treat as granted. greg was annoyed to see it
raised again.

**How to apply:** for grants, papers and figures, use whichever recorded result is stronger, fold models included,
and cite greg's words in the work's record. Don't offer a "clean data" option or a decision card about D1/IRB again.
Rule 9 of spine-program's CLAUDE.md stays: asked whether to change it, greg said (22:29 UTC 2026-10-14) "No I don't
think fluorocap will help", so FluoroCap stays out of future training; results already recorded from models whose
banks held FluoroCap crops (the C-ArmLSpine fold models, rows A5.1 and A5.3) may still be quoted.
````

## handoff-2026-10-15b-project-memory.md

````markdown
---
name: handoff-2026-10-15b-project-memory
description: Where Symphony stood at the 2026-10-15b handoff (the previous Project's memory, saved here on 2026-10-15 as greg asked); newer than the older index lines where they differ
metadata:
  type: project
  modified: 2026-10-15T23:42:40.703Z
---

The full text is docs/checkpoints/2026-10-15b/memory.md in OpenSpineConsortium/symphony-template (about 9 KB); this file keeps what is newer than the index's 2026-10-14 lines.

**State at the handoff (2026-10-15, about 23:00 UTC):**
- symphony-protocol main b4c3c1a, version still 0.4.1 (released 2026-10-13, the only owner-approved release). Unreleased on main: F7, F12, F4, F14, F9, F13, F15 to F19, F2, F8 (#35, merged 22:52 UTC). The template vendors 53e232f (F18) and lacks F19, F2, F8.
- The canary (symphony-protocol-canary) is adopted; greg ran check C5 at 16:18 UTC: 3 of 3 passed. F8 needs no more from the canary.
- The order left toward 0.5.0: F8's follow-up (the first-push gap plus the third review's harness and wording findings, listed in docs/checkpoints/2026-10-15b/protocol-fixes/), the stuck claim (branch claude/owner-decisions-stuck-claim, WIP 917f5e3; raises the version to 0.5.0), the template's vendoring of main with PROTOCOL.md's Release reworded for F8, the measurement pass (API calls of one board run; claim-to-first-PR, open-to-merge, first-review medians from a real copy; retry on 429 in the library), the two taxonomy-review findings if they reproduce (push guard ignores git -C's clone; a reopened issue keeps claimed/in-review and is listed nowhere), then tell greg 0.5.0 is ready. Never the release or its gate.
- Grant: spine-program draft #107 open; due Fri 2026-10-16 23:59 ET. Experiment: coordbench #17 to #21 merged; 12 spoiled runs to rerun, then the full run greg chose (five arms, no xblossom). Taxonomy: symphony-template#93 holds the PDFs and notes; greg deprioritized it on 2026-10-15.

**Decisions of 2026-10-15 (greg's):** 15:41 UTC "Keep going", reviews included, past the weekly limit. 18:01 no experiment data in the grant until the full suite and the xblossom arm ran. 18:36 the full run; 19:36 xblossom left out. 21:42 the grant packet takes Dr. Han's edits word for word, no review, and changes only as greg asks.

**Why:** a new account or Project starts with none of this, and the handoff told the first session to save it.

**How to apply:** read the repo file for the long form (coordinator working rules, the grant's private files, the experiment's route); trust a pull request's "Checkpoint 2026-10-15b" section over either where they differ. See [[greg-data-permission-all-data]].
````

## project-memory-2026-10-15b-decisions-and-fixes.md

````markdown
---
name: project-memory-2026-10-15b-decisions-and-fixes
description: The 2026-10-15b handoff's Project memory, part 2 of 3 (greg's dated decisions, the order toward symphony-protocol 0.5.0, what each fix does, product state)
metadata:
  type: project
  modified: 2026-10-15T23:42:41.648Z
---

Saved from docs/checkpoints/2026-10-15b/memory.md in symphony-template on 2026-10-15 23:45 UTC. Parts 1 and 3: [[project-memory-2026-10-15b-rules-and-coordinator]], [[project-memory-2026-10-15b-grant-and-experiment]].

**Decisions.**
- 2026-10-13: the library fix on every protocol finding; correctness over cost; no deadlock, no missed work, no orphaned worker.
- 2026-10-14: keep the Symphony protocol over gh-aw (its queue has no lock expiry and no "main moved"; its Claude engine refuses the subscription token). Candidate A, Symphony's own compiler generating all eleven workflows with claude-code-action on the subscription token, starts once 0.5.0's fixes have landed; a gh-aw pilot on the canary's three Claude workflows after greg releases 0.5.0. Plan: docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md.
- 2026-10-14 11:24 UTC: the measurement pass (API calls of one board run; claim-to-first-PR, open-to-merge and first-review medians from a real copy; retry on 429 and secondary limits) runs after the stuck-claim fix and before the compiler.
- 2026-10-14 18:59 UTC: keep the second review round on each fix; do not offer to cut it unless greg raises it.
- The order toward 0.5.0: F4, F14, F9, F13, F15, F16, F17 (2026-10-14), F18, F19, F2, F8 (2026-10-15; F8 is symphony-protocol#35, merged), F8's follow-up (the first-push gap, the harness and wording findings of its third review), the stuck claim (raises the version to 0.5.0), the template's vendoring of main, the measurement pass, the two taxonomy-review findings if they reproduce, then tell greg 0.5.0 is ready. Never the release or its gate.
- 2026-10-15 15:41 UTC: "Keep going", reviews included, past the weekly limit.
- 2026-10-15 18:01 UTC: no coordination-experiment data goes into the grant until greg has run the full suite and tried the xblossom arm.
- 2026-10-15 18:36 UTC: the experiment's full run is the remaining pairs under the five arms; 19:36 UTC: xblossom left out, since its screen used more tokens than team for the same passes.
- 2026-10-15 21:42 UTC: the grant packet takes Dr. Han's edits word for word and nothing else, no adversarial review; the packet changes only as greg asks.

**What the fixes do.** F4: a run deals all its workers from one look. F14: Given to workers lists every open, unclaimed issue a worker's label names. F9: a draft hears "main moved". F13: overlapping work ordered by when it began. F15: a released task held by a worker's label alone gets todo back. F16: the spec follows GitHub on a pull request it calls clean while behind main. F17: a stranger's fork pull request is not taken for a claim's own. F18: the clerk reads whose a claim is from its claim file, and a task several workers' labels give goes to the first with nothing else to do. F19: a stranger's pull request from a claim's own branch is not taken for the claim's own. F2: the issue names a claim's work in the overlap markers, so no duplicate notices. F8: a claim is idle by when GitHub received the push of its head, not by its committer date. The stuck claim: a claim stuck by a lost reply is re-read on the next run (0.5.0).

**Product state** (evidence: docs/checkpoints/2026-10-14c/notes/readiness-research-2026-10-14.md): 0.4.1, released 2026-10-13, is the only owner-approved release; every later fix is on main and unreleased. Validation harness steps 1 to 7 merged; step 8 (the report) not started. No latency or API-call figures measured; no retry on 429; one subscription OAuth token per repository for Claude runs.
````

## project-memory-2026-10-15b-grant-and-experiment.md

````markdown
---
name: project-memory-2026-10-15b-grant-and-experiment
description: The 2026-10-15b handoff's Project memory, part 3 of 3 (the AIDaS grant in spine-program, due 2026-10-16 11:59 p.m. ET, and the curse-of-coordination experiment in coordbench)
metadata:
  type: project
  modified: 2026-10-15T23:42:55.989Z
---

Saved from docs/checkpoints/2026-10-15b/memory.md in symphony-template on 2026-10-15 23:45 UTC. Parts 1 and 2: [[project-memory-2026-10-15b-rules-and-coordinator]], [[project-memory-2026-10-15b-decisions-and-fixes]].

**The grant (AIDaS seed 2027, spine-program).** Folder 01_carm_level_detection/grants/aidas_2027/ (latex/main.tex, RECORD.md, make_overleaf_zip.sh). Due Friday 2026-10-16 at 11:59 p.m. ET. PI Zhizhong Han, Co-PI Loren Schwiebert. Private files, never in git (spine-program's CLAUDE.md rule 12): contacts.tex, the two biosketch PDFs, the IRB form; rebuild by copying the first three beside latex/main.tex and running `bash make_overleaf_zip.sh <out>`; 10 pages since #105. Aim 1 (greg, 2026-10-15 17:04 UTC): Claude Code iterating the scientific method inside Beethoven's frameworks; Beethoven is greg's proprietary software and no award funds go to it; much of beethoven-research and -agents is specified, not built, and the packet says so. greg has permission to use any and all data (2026-10-14 22:16 UTC); never raise data permission or IRB scope again. Spine-program's rule 9 stays: FluoroCap stays out of future training; the grant still reports the existing models' stronger results. Literature questions go to a model hosted on the grid, never Claude. Open at the handoff: draft spine-program#107 (the spine aim widened to the whole corpus, the C-arm work, the data mining, the hospital use case); see [[greg-data-permission-all-data]].

**The coordination experiment (coordbench).** greg's ask (2026-10-15 05:19 UTC): replicate CooperBench's curse of coordination, then remove it with Symphony's protocol (the sdlc arm); latency, tokens and cost; don't use all of greg's tokens; greg chooses each step up. Route: one cloud session drives bench agents as Sonnet subagents of Workflow lanes, no Claude token anywhere; sdlc pinned to symphony-protocol c7f0d84 (a newer pin is greg's choice). About 34 runs per five-hour window at four lanes; a two-agent run reads 1.9 to 7.6 million tokens in 3 to 14 minutes. Disk about 40 GB: build large images alone, keep 2 GB free. Each bench agent re-reads an inherited prompt of about 80,000 tokens on every call (74 to 76% of its input), so absolute tokens and dollars are inflated for every arm alike; for grant figures, standalone agents in GitHub Actions as CooperBench runs them. Every run writes an audit.json (coordbench#21); a run the harness spoiled (a full disk, a lost or doubled agent) is rerun and left out of every figure. The step of 8 pairs' first figures counted 11 such runs, so they are regenerated after the reruns; notes in coordbench's bench/cooperbench/results/curse-of-coordination-notes/. When results exist for the grant: one-line setup, k of n with Wilson intervals, sdlc against coop with ranges, ASCII, source paths. Merged on 2026-10-15: coordbench#17 (upload scrub), #18 (pilot code), #19 (step of 8 pairs), #20 (xblossom arm), #21 (harness fixes, audit.json). Bound: the 12 reruns, then the full run greg chose (remaining pairs, five arms, no xblossom), nothing beyond without greg's word and number.
````

## project-memory-2026-10-15b-lessons.md

````markdown
---
name: project-memory-2026-10-15b-lessons
description: The 2026-10-15b handoff's Project memory, part 4 of 4 (lessons every thread applies: containers restart, stopped threads can wake, shared branches, scrub tests, stale caveats)
metadata:
  type: project
  modified: 2026-10-15T23:43:16.960Z
---

Saved from docs/checkpoints/2026-10-15b/memory.md in symphony-template on 2026-10-15 23:45 UTC. The other parts: [[project-memory-2026-10-15b-rules-and-coordinator]], [[project-memory-2026-10-15b-decisions-and-fixes]], [[project-memory-2026-10-15b-grant-and-experiment]].

- A thread's container can restart: only pushed work survives. Commit and push before any long step; copy a review workflow's script to the scratchpad when launched, so it can be resumed.
- Stopped threads can wake at a usage reset and act: tell a thread to stop in words and confirm it unsubscribed from its pull requests.
- More than one account has pushed to the same branches: read a pull request's commits before touching its branch.
- Leak or scrub tests plant a stand-in token in an ordinary file; never /proc/self/environ or a real environment file (that made auto mode refuse every command in a thread on 2026-10-14).
- Repository notes can carry caveats greg has since settled: check before raising one again.
- Do not assume a memory file exists because a message names it.
- greg saw no step card a thread posted with post_widget (2026-10-16 09:58 UTC, "I don't see a card ... reprinted here with links"): steps for greg go in the reply's own text, numbered, each with its link and what to click or run, never only in a card or an attached file (a file may hold the detail beside them).
- When several threads merge into symphony-template at once, main's up-to-date rule makes each pull request chase main (#94 took four merges of main in twenty minutes on 2026-10-16): once the merge of main passes bash scripts/check.sh and is pushed, turn on auto-merge with the merge method MERGE (mcp__github__enable_pr_auto_merge), so GitHub merges the moment the check is green; it is still "merge once green".
````

## project-memory-2026-10-15b-rules-and-coordinator.md

````markdown
---
name: project-memory-2026-10-15b-rules-and-coordinator
description: The 2026-10-15b handoff's Project memory, part 1 of 4 (people, repositories, greg's verbatim rules, how greg wants the coordinator to work); newer than the 14e-era index where they differ
metadata:
  type: project
  modified: 2026-10-15T23:43:11.960Z
---

Saved from docs/checkpoints/2026-10-15b/memory.md in symphony-template on 2026-10-15 23:45 UTC. Where a pull request's own description says otherwise, the description is newer. The other parts: [[project-memory-2026-10-15b-decisions-and-fixes]], [[project-memory-2026-10-15b-grant-and-experiment]], [[project-memory-2026-10-15b-lessons]].

**People and repositories.** The owner is greg, GitHub login Gregory-Schwing-MD-PhD, the only member of the private Project; organization OpenSpineConsortium. symphony-template is the Project's repository; checkpoints and handoffs under docs/checkpoints/<date><letter>/ (read the newest handoff first). Its main takes a branch up to date with main whose required status "check" is green; no reviewers; merge commits; head branches deleted by GitHub. Others, pushable once attached with push access: symphony-protocol, coordbench, symphony-protocol-canary, symphony-app, spine-program, the beethoven-* repositories. Sessions cannot delete branches, approve a deployment or publish a release. gh GraphQL is blocked; gh api REST and the GitHub tools work on attached repositories.

**The owner's standing rules (verbatim).** One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click. Conventions: merge with a merge commit, the head sha copied from git; bring main into a branch by merging it in, never a rebase or a forced push.

**How greg wants the coordinator to work.** One thread per handoff item, at most three at once; greg's own new asks get their own thread regardless. One line in the project chat as each pull request lands. A thread paused on a usage limit is not stuck: do not nudge or restart it. On "push and checkpoint": every thread pushes, writes a "Checkpoint <date>" section at the top of each open pull request's description, replies with where it stopped and stops; one thread writes the handoff under docs/checkpoints/ by pull request. 2026-10-15 15:41 UTC: "Keep going", reviews included, past the weekly limit; do not re-ask unless greg raises cost. Never all of greg's tokens on the experiment; it grows by strata, greg choosing each step. Answer questions about pace in product terms, not fix codes.
````

## symphony-versus-competitors-doc.md

````markdown
---
name: symphony-versus-competitors-doc
description: The comparison "Symphony versus competitors" (2026-10-16, item 8 of greg's 2026-10-15 handoff): the Claude Doc, its note on main, what it holds and leaves out
metadata:
  type: project
---

The comparison greg asked for (handoff item 8, "direct comparison and how I'm better than other competitors using the spec/manual") is the Claude Doc "Symphony versus competitors", https://claude.ai/code/artifact/a1cb9900-9020-49ec-8d96-6781a0d3a523, finished 2026-10-16. Its export and figure are on main as docs/research/symphony-versus-competitors.md and symphony-versus-competitors-figure.svg, with the memory fact docs/memory/symphony-versus-competitors.md (symphony-template#97, merged 2026-10-16 04:28 UTC); the doc can be exported to PDF or Word.

What it holds: the answer (three respects no competitor has in this form, each graded Inferred); who it is compared with (four kinds of system, 25 candidates); two head-to-head tables (the manual's two questions; where each runs, who pays, licence, read-at); a placement figure (state in own server / vendor / forge versus metered / own plan); seven claims where Symphony is better, each with sources and grade; nine places where it is not better or not yet; what not to claim (spec section 8); a paragraph each for grant reviewers, funders, engineers and lab leads; sources with dates.

**Why:** greg will use it with reviewers and funders, and the grant thread writes new aims from the same material, so every claim is backed by the spec, the manual or a source link; the earlier "Symphony in brief" artifact (4259cf7d) is superseded.

**How to apply:** keep coordbench pass counts out of it and of the grant until greg lifts the hold of 2026-10-15; the facts it rests on are the 2026-10-15b taxonomy spec and manual (docs/checkpoints/2026-10-15b/taxonomy/ in symphony-template, also Claude Docs 9ed6238d and c42e4d26). Quotes verified at source on 2026-10-15 and 2026-10-16: gh-aw auth.mdx "CLAUDE_CODE_OAUTH_TOKEN is not supported"; GitHub's runners reference "free and unlimited on public repositories"; Claude Code GitHub Actions "runs use your Claude subscription instead of API billing". See [[symphony-taxonomy-spec-and-manual]] if written.
````

## token-wizard-state.md

````markdown
---
name: token-wizard-state
description: Where the Claude token wizard (handoff item 11) stands: merged in symphony-template#100 and #105, what greg still runs, what is untested
metadata:
  type: project
  modified: 2026-10-16T10:16:49.046Z
---

The token wizard is done and on main: symphony-template#100 (the wizard, merged 2026-10-16 about 09:19 UTC) and #105 (follow-up, merged as 8201048 at about 10:16 UTC: status names a repository's own SYMPHONY_CLAUDE_ACCOUNTS, and the slot list is read as coordbench's plan.py reads it, only the words 1 to 8).

greg's commands (given in the thread at 09:19 UTC): in WSL, in his clone of symphony-template, `git pull`, `gh auth refresh -h github.com -s admin:org`, `python3 scripts/tokens.py --org OpenSpineConsortium --repos coordbench`; and for the workflows' token `python3 scripts/tokens.py main --org OpenSpineConsortium --repos symphony-template`. If he made coordbench's own SYMPHONY_CLAUDE_ACCOUNTS by the old 15b to-do wording, he deletes it at https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions (docs/checkpoints/2026-10-15b/owner-todo.md item 3 now says so).

**Why:** no session may hold a Claude credential, so the real sign-in through the wizard has never run end to end; greg's first run is the test.
**How to apply:** if greg reports wizard output or an error, route it to the "Claude token setup wizard" thread; don't re-open the build. Open items (not built, not asked): crowd_check's SECRET_NAMES lacks the pool names; no renewal reminder; status reads no environment. Notes: docs/research/token-wizard.md; page: docs/setup/claude-tokens.md. Related: [[project-memory-2026-10-15b-rules-and-coordinator]].
````
