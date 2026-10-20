# Symphony handoff, 2026-10-15b (paste the block in part 0 as the next session's first message)

At 22:20 UTC on 2026-10-15 the owner asked every thread, and the project chat, to "identify a good point to push merge and handoff". Each of the four working threads named its stopping point and stopped there, or where it stood when the owner then said to checkpoint at once; each merged what was ready, wrote a section titled "Checkpoint 2026-10-15b" at the top of its last pull request's description (spine-program#107, symphony-protocol#35, coordbench#21) or, for the taxonomy thread, in docs/checkpoints/2026-10-15b/taxonomy/README.md, unsubscribed from its pull requests and stopped. Those sections are the state to trust: they are newer than this file where they differ, and where one is missing, the branch's last commit is the state.

This file replaces docs/checkpoints/2026-10-15/handoff.md as the place to start. Two files beside it carry what lives outside GitHub: memory.md, the Project's memory at the handoff (save it as the next Project's memory if the next session is on another account or in a new Project), and owner-todo.md, the owner's own steps with every link and what to click, which replaces docs/checkpoints/2026-10-14e/owner-todo.md for everything it lists.

## 0. The first message to paste

Paste this whole block as the first message in the next Project's chat. If it arrives cut short, the whole of this file is docs/checkpoints/2026-10-15b/handoff.md in OpenSpineConsortium/symphony-template.

```
Pick up Symphony where the last session stopped on 2026-10-15 at about 23:00 UTC. This message is a pointer: before anything else, read docs/checkpoints/2026-10-15b/handoff.md in OpenSpineConsortium/symphony-template, and the two files beside it: memory.md (the last Project's memory; save it as this Project's memory if it is not already there) and owner-todo.md (my own steps). The last pull request of each thread (spine-program #107, still open; symphony-protocol #35 and coordbench #21, merged) begins its description with a "Checkpoint 2026-10-15b" section saying exactly where its thread stopped; it is newer than the handoff where they differ.

Start one thread per item below, each reading its part of the handoff (part 2) first and attaching the repositories it needs with push access:
1. The AIDaS grant in spine-program (draft #107), due Friday 2026-10-16 at 11:59 p.m. ET. Its own thread at once, whatever the cap.
2. The protocol fixes in symphony-protocol toward 0.5.0, in the order of the handoff's part 2.1: F8's follow-up, the stuck claim (it raises the version to 0.5.0), the template's follow-up, the measurement pass, the two findings from the taxonomy review, then tell me 0.5.0 is ready. Never the release or its approval gate.
3. The curse-of-coordination experiment in coordbench: the 12 reruns, then the full run I chose, from bench/cooperbench/results/curse-of-coordination-notes/README.md there; no bench run beyond what I already chose without my word and number.
4. The taxonomy spec and manual: whatever its checkpoint says is left.

Rules
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
```

## 1. Before the paste

### Continuing in the same Project (symphony, on the same account)

Nothing to set up: the Project memory, the shared folder and the artifacts stay. Paste part 0 in the project chat. The account's weekly usage limit was reached at 14:14 UTC on 2026-10-15 and resets on 2026-10-22 at 02:00 UTC; the threads have run on claude-opus-5-5 since about 15:13 UTC, the default model for new threads since 17:47 UTC.

### Moving to another account or a new Project

Nothing outside GitHub carries over: this Project's memory, threads, shared folder (/mnt/project-files), artifacts and connectors stay with this account. Part 3 lists what lives only there and what to do about each before you switch. Then:

1. GitHub: signed in to the new Claude account, open https://claude.ai/connect-github, sign in to GitHub as Gregory-Schwing-MD-PhD and press Authorize. The Claude GitHub App is already installed on every repository of OpenSpineConsortium (2026-10-13); if the page asks where to install it anyway, pick OpenSpineConsortium and All repositories.
2. The Project: open https://claude.ai/code, make a new Project named symphony, pick OpenSpineConsortium/symphony-template as its repository, and set:
   - Topic, exactly: Finish Symphony, OpenSpineConsortium's coordination product for Claude Code agents, from where the 2026-10-15b handoff left it: land the open pull requests, finish the protocol fixes, ect
   - Project instructions, exactly (the Rules, verbatim, as this Project has them): Rules One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
3. The cloud environment: the default one is enough. Add no environment variable and no secret: no Claude token, no API key.
4. Connectors: the grant thread sent e-mail from your Gmail on 2026-10-15 at your request. If the new grant thread should do that again, connect Gmail in the new account (Settings, Connectors, at https://claude.ai/settings/connectors).
5. Paste part 0. Allow the repository prompts the threads raise when they attach symphony-protocol, coordbench and spine-program with push access. In the grant thread, attach the two biosketch PDFs and the cover's contact lines again (owner-todo.md, item 1).

## 2. Where each thread stopped

Read from the threads' final replies and from GitHub; the times are UTC on 2026-10-15.

### 2.1 Protocol fixes toward 0.5.0 (symphony-protocol)

Merged on 2026-10-15: symphony-template#87 (F18's template counterpart, 04:27, 7be1f1f) and #90 (the template vendors the library at 53e232f, F18, 09:51, 875563a); symphony-protocol#32 (F18, 0536cc3), #33 (F19, 1a79df9) and #34 (F2, a3a5b4d). The library's version is still 0.4.1 and the last release is v0.4.1 of 2026-10-13, so every fix since (F7, F12, F4, F14, F9, F13, F15 to F19, F2) is on main and unreleased. The owner ran the canary's check C5 at 16:18 UTC: 3 of 3 passed.

F8, symphony-protocol#35 (https://github.com/OpenSpineConsortium/symphony-protocol/pull/35, branch claude/owner-decisions-f8): a claim is idle by when GitHub received the push of its head, not by its committer date. Its head a6465a5 passed check.sh (1,432 tests), 109 of 109 mutants and the deep lane, and CI went green on every check. Its third adversarial review found no wrong rule in the shipped cases and one real gap: a claim's first push is the one most likely to be missing from the activity GitHub lists when the run it starts reads it, so if that push's commit is dated back, the claim can still be released in that same run. None of the review's findings makes main worse than 0.4.1, where the committer date always decided. At 22:52 UTC the owner wrote "NO WAY CHECKPOINT NOW", and the thread merged #35 green as it stood (main b4c3c1a, still 0.4.1 and unreleased), stopped the review it had started, and stopped at 22:54 UTC. Its "Checkpoint 2026-10-15b" is at the top of #35's description; the same text, and the stopped review's raw findings (unverified where the review was cut), are committed beside this file in protocol-fixes/.

Next, in the thread's order (the owner's decision of 2026-10-13 stands: the library fix on every finding, correctness over cost, no deadlock, no missed work, no orphaned worker):

1. F8's follow-up, by its own pull request: the first-push gap. The run's event names the branch and the sha it pushed (GITHUB_EVENT_NAME push or create, GITHUB_REF_NAME, GITHUB_SHA); cli passes that pair down to head_since, which dates that head no earlier than the run's start, for that run alone, where no read dates its push. With the spec's sentence, the oracle's reading, a trace step and a mutant.
2. The review's three harness gaps (two different older entries across the two reads; a fresh delete; Fault.then firing early) and its wording fixes, listed in protocol-fixes/protocol-fixes-2026-10-15b.md.
3. The stuck claim: a claim stuck by a lost reply is re-read on the next run. Draft branch claude/owner-decisions-stuck-claim, work in progress at 917f5e3: merge main in, then reconcile landed_release with F8's github.newer and board.release_counts. Its pull request raises the version to 0.5.0.
4. The template's follow-up: a symphony-template pull request that vendors the library's main ahead of the release (the template carries 53e232f, F18, and not F19, F2, F8 or what follows), with docs/agents/PROTOCOL.md's Release, which still says idleness is "by the committer date of its head", brought in line with F8.
5. The measurement pass (the owner's choice of 2026-10-14 11:24 UTC): the API calls of one board run, the claim-to-first-PR, open-to-merge and first-review medians from a real copy, and retry on 429 and secondary rate limits in the library, each by its own pull request.
6. The two findings the taxonomy thread's review passed on at 21:25 UTC (evidence: docs/checkpoints/2026-10-15b/taxonomy/research/verify/02-claim-lock.txt): the push guard reads claim files from the hook's working directory and ignores the clone a `git -C <dir>` push names; and a reopened issue keeps the labels claimed and in-review, so the board lists it nowhere and no worker is dealt it (tidy.yml runs only when an issue closes). Reproduce each on main; each that holds gets a finding entry and its own library-fix pull request; drop one that does not reproduce.
7. Tell the owner 0.5.0 is ready. Only the owner approves a release (owner-todo.md, item 6). Then the compiler (docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md, Candidate A, PR 1a to PR 7) and the harness's step 8 report.

### 2.2 The AIDaS grant (spine-program), due Friday 2026-10-16 at 11:59 p.m. ET

Merged on 2026-10-15: spine-program#97 (the Overleaf zip as a script), #99 (the Elsevier literature element; the IRB protocol named as pending, at the owner's 12:45 UTC "make the grant better!"), #101 (Aim 1 rewritten on the owner's 17:04 UTC correction: Claude Code iterating the scientific method inside Beethoven's frameworks, beethoven-qa and Symphony), #103 (Dr. Han's four edits word for word, at the owner's 21:42 UTC instruction to change nothing else and run no adversarial check) and #105 (two stray words trimmed and "a tenure-track" fixed, back to 10 pages).

Main holds every change to the packet: 10 pages with 16 red [DATA NEEDED] marks, and the zip and the PDF in the Project's shared folder are current. The thread stopped at 22:32 UTC, when the owner wrote at 22:30 to checkpoint at once.

Open: draft #107 (https://github.com/OpenSpineConsortium/spine-program/pull/107, branch claude/106), the owner's 21:56 UTC ask: do not limit the spine aim to the 802 CT scans; show the whole corpus in spine-program, the progress on the C-arm problem, the data mining, and a real use of AI in the hospital against wrong-level surgery, its never events and its legal costs. Only the gathered evidence is committed, at 01_carm_level_detection/grants/aidas_2027/evidence/spine-aim-facts-2026-10-15.md on claude/106; the packet's text is unchanged. Five of six evidence readers finished; the hospital-use-case reader and the final cross-check were stopped, and no fact has had its second check yet. Next, in the order of the "Checkpoint 2026-10-15b" section at the top of #107: gather the hospital use case; check each fact against its file; rewrite the abstract, section 1 and Aim 3 at 10 pages; build, merge, and rebuild the zip and the PDF. A 10-page build needs contacts.tex and both biosketches beside latex/main.tex; they stay out of git. One finding to keep: the repository's verified evidence does not support "billions a year" in legal costs; the figure it supports is $1.3 billion in US malpractice payments for all surgical never events over 1990 to 2010.

Holds and defaults that stand:
- The packet changes only as the owner asks; no review runs on an edit the owner said to apply as written.
- No coordination-experiment data goes into the grant until the owner has run the full suite and tried the xblossom arm (the owner, 18:01 UTC). The experiment's own cutoff for grant data was Friday 2026-10-16 at 12:00 p.m. ET.
- An office silent by 3 p.m. ET on Friday gets "estimate, quote requested" in the budget.
- Two calls wait for the owner in the thread: the Claude seats (budget line C1 buys Team seats, while Beethoven's decision D1 asks for a plan in each trainee's own name: amend D1, or switch C1 to Pro plans with a new amount) and CLAIM (beethoven-research only names the checklist as coming, so the packet says it "plans" CLAIM; back to "holds" if the owner points to the checklist).
- The e-mails asking Dr. Han and Loren Schwiebert for their details were sent from the owner's Gmail at 19:35 UTC at the owner's request; do not resend. Their answers arrive in the owner's inbox and the owner pastes them into the thread.
- Never commit contacts.tex, the biosketches or the IRB form: they hold personal data (spine-program's CLAUDE.md rule 12).

### 2.3 The curse of coordination (coordbench)

The owner's ask of 05:19 UTC: replicate CooperBench's curse of coordination, then remove it with Symphony's protocol, measuring latency, tokens and cost; don't use all the owner's tokens; the owner chooses each step up. Merged on 2026-10-15: coordbench#17 (the upload scrub, 5028999), #18 (the pilot's code, 7eb1fd9), #19 (the step of 8 pairs, 40 runs, fe2e245), #20 (the xblossom arm, 76706ac) and #21 (the harness fixes, c433d48, merged at about 22:48 UTC with every check green; its description opens with "Checkpoint 2026-10-15b"). The thread stopped at 22:49 UTC.

What #21 changed: the harness writes an audit.json for every run, and every report leaves out the runs the harness spoiled and names them. Run over the earlier runs, the audit flagged 12: eleven from the step of 8 pairs (ten hit a full disk, one pair of agents was spawned twice) and one solo pilot run where the harness lost the agent. All 12 are back in the queue. So the step's figures as first reported (solo 5 of 8, every two-agent arm 6 of 8, no curse) count 11 spoiled runs and must be regenerated after the reruns; the clean runs alone are too uneven to compare (solo 4 of 6, coop 5 of 6, sdlc 3 of 4, coop-git 5 of 6, team 6 of 7). The step also measured the sdlc arm as the slowest, with about a third of its agent time blocked waiting. The xblossom screen (12 runs) passed 4 of 4 like team but used 26% more tokens and 21% more dollars, so the owner chose at 19:36 UTC to leave it out of the full run. Every bench agent on this route re-reads an inherited prompt of about 80,000 tokens, so absolute tokens and dollars are inflated for every arm alike; arm comparisons hold.

Next, by "The next steps, in order" in coordbench's bench/cooperbench/results/curse-of-coordination-notes/README.md: start the image loop; rerun the outlines pair alone on one lane (it filled the disk at scoring); rerun the other seven; shuffle the arms; then resume the full run the owner chose at 18:36 UTC (the remaining pairs under the five arms, without xblossom) batch by batch on about three lanes. The owner chooses each step up: say the pair count and the expected usage windows before each batch. The disk allowance is about 40 GB: build the large images alone and keep 2 GB free while runs are in flight. The grant-data hold stands (part 2.2).

Files, in coordbench under bench/cooperbench/results/: curse-of-coordination-notes/ (the README with where things stand, trial-order.md, harness-review.md, the research notes, and run/ with the queue, the 43-pair order, the batches and the image loop), xblossom-screen/ (the screen's runs, summaries and figures), curse-1-step-8/ and curse-1-pilot/ (each run's audit.json under raw/; the step's README flags the 11 runs to redo). The run logs and transcripts were only in the thread's container, so the next session does not have them.

### 2.4 The taxonomy spec and manual

The owner's ask of 18:04 UTC: a SPEC and a MANUAL placing Symphony and Beethoven in a taxonomy of software (their fit, how they interoperate, the need they close, what is unique; their nativeness to GitHub Actions and its free minutes for public repositories). Both were written and reviewed at 21:24 UTC as Claude Docs of this account: the spec (https://claude.ai/code/artifact/9ed6238d-6b5e-4a7e-acb5-df360435c19c, rev 59) and the manual (https://claude.ai/code/artifact/c42e4d26-b238-4834-bb7b-318ae086152c, rev 30). Findings: only the combination is unique, and unsorry is the closest rival; gh-aw's work queue refuses the subscription token; the review's two protocol findings went to the protocol thread (part 2.1).

The thread stopped at 22:42 UTC, after the owner wrote at 22:29 to render the PDFs as they stood and checkpoint at once. Merged: symphony-template#93 (64f0bad), docs/checkpoints/2026-10-15b/taxonomy/: its README (the thread's handoff, with "The exact next step"), spec.pdf (36 pages) and manual.pdf (23 pages) as they stood at 22:30 UTC, Markdown copies spec.md and manual.md, research/ (the 13 notes and the three checks, as .txt) and refs-work/ (the citation work).

Open: the owner's 21:58 UTC ask, "I need pdfs with references". The PDFs carry inline links and the spec's "Sources" list but not yet the numbered reference lists. Citation drafts exist for 13 of 15 section groups, only spec-F's has had its second check, and spec sections 10 and 11 and manual sections 8 and 9 have none. Next, by the README's "The exact next step": draft and check the citations, run refs-work/apply.py for each document, apply its edits and add the reference sections, render both PDFs again. A session on another account cannot edit these Claude Docs; it rebuilds them from spec.md and manual.md. These files describe Beethoven's private repositories, and symphony-template is internal today: removing the folder leaves it in the history, so a public symphony-template would have to be a copy made without it (owner-todo.md, item 9). Deep research is optional and the owner's (owner-todo.md, item 8).

### 2.5 Finished threads

- CooperBench in Actions: done. coordbench#17 merged, the fake run (250 pair runs, five arms) clean, symphony-template#91 recorded it (15d3f22). The real run waits on the owner's steps (owner-todo.md, item 3).
- The deep lane, symphony-protocol#21: merged at 02:38 UTC as c7f0d84 (docs/checkpoints/2026-10-15/deep-lane.md).
- The 2026-10-14 threads are finished and must not be reused.

## 3. What lives outside GitHub

In this Project's shared folder (/mnt/project-files), which a new account cannot read:

- grant/: AIDaS_SEED_2027_overleaf.zip and AIDaS_SEED_2027_submission_draft.pdf (the current build), contacts.tex and biosketches/ (personal data, never committed). The zip and PDF rebuild from spine-program's main with those three private files beside latex/main.tex (`bash make_overleaf_zip.sh <out>`), so a new account needs only the biosketches and the contact lines again. grant/evidence/spine-aim-facts-2026-10-15.md is a copy of the file committed on #107's branch.
- uploads/hearth/: the IRB form of 2026-10-15 12:45 UTC (personal data; its facts are in spine-program's RECORD.md section 6) and Dr. Han's edited files of 21:42 UTC (folded in by #103).
- experiments/curse-of-coordination/: working copies of what coordbench now holds under bench/cooperbench/results/ (part 2.3); the step's and the pilot's reports there predate the audit and still count the spoiled runs.
- research/taxonomy/: the unfolded originals of what docs/checkpoints/2026-10-15b/taxonomy/ holds folded to ASCII (the research notes, the three checks, of which verify/02-claim-lock.md is the evidence for the two protocol findings, the citation work and the two PDFs).
- handoffs/: the protocol fixes thread's checkpoint and its stopped review's findings, committed as docs/checkpoints/2026-10-15b/protocol-fixes/.
- status/readiness-research-2026-10-14.md: also committed, as docs/checkpoints/2026-10-14c/notes/readiness-research-2026-10-14.md.

The two Claude Docs of part 2.4 belong to this account; their Markdown copies are committed beside the taxonomy README.

## 4. Watch for

- Until symphony-protocol 0.5.0 is published, its weekly sync (Mondays 06:17 UTC, next 2026-10-19) opens a symphony-template pull request "Vendor symphony-protocol 0.4.1". It is a downgrade that would undo every fix since; its check stays red. The owner closes it (owner-todo.md, item 2); no session fixes its check.
- A thread paused on a usage limit is not stuck; it resumes at the reset. Do not nudge or restart it.
- A thread's container can restart: only pushed work survives. Commit and push before any long step.
- More than one account has pushed to the same branches before: read a pull request's commits before touching its branch.
- When the owner says to push and checkpoint everything: every thread pushes, writes a "Checkpoint <date>" section at the top of each open pull request's description (a comment where there is none), replies with where it stopped and stops; one thread writes the handoff under docs/checkpoints/ by pull request.

## Rules

One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
