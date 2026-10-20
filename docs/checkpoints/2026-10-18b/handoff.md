# Symphony handoff, 2026-10-18b

Source: the thread "Organize a whole OneDrive", 2026-10-18 at about 22:10 UTC, on the owner's ask at 21:59 UTC to checkpoint every thread so he can continue in another account. It is written from the reports of the threads Protocol fixes toward 0.5.1, Control panel sign-in and Add token faults, this thread's own work, and the Project memory. This file replaces docs/checkpoints/2026-10-18/handoff.md as the place to start. Beside it: memory.md (the Project memory at the handoff, 10.4 KB, which imports whole) and topic-memories/ (the seven topic memories). Each open pull request's first line, "Checkpoint 2026-10-18b: ...", is newer than this file where they differ.

Every block below is copied whole, without the fence lines.

## 1. Project instructions

Where: claude.ai, the new account's Project, Settings, the Instructions field. Paste and press Save.

```
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
Commit what you find, intermediate or final, under docs/research/ in symphony-template with its line in docs/research/README.md, by pull request, before you stop.
Put every manual step for me in the reply's own text, numbered, never only on a card, in a widget or in a file.
```

## 2. Project goal

Where: the same Settings, the Goal (or Topic) field. Paste and press Save.

```
Build Symphony, OpenSpineConsortium's open coordination product for Claude Code, and prove that it works. Symphony lets many Claude sessions, routines and GitHub Actions workers share one repository without stepping on each other: the claim protocol as a library (symphony-protocol), the template that keeps a Claude project as files in a repository (symphony-template), the two GitHub Apps and the one-press front door, the plugin, and the control panel on openspineconsortium.com, which now also organizes a person's OneDrive into projects. The proof is measured: replicate CooperBench's curse of coordination and remove it with Symphony's protocol (coordbench), benchmark agentic workflows (flowbench), and go beyond cooperation against MAST's failure modes. This Project also carries my related work: the AIDaS spine grant (spine-program), the Beethoven extension and Symphony on the WSU grid. Done for now means the protocol fixes released as 0.5.1 and vendored into the template, the open pull requests landed, and the full coordination run recorded with its results.
```

## 3. Memory

Where: in a new account's Project the memory starts empty. Open memory.md beside this file at https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-18b/memory.md, press the copy-raw button, and paste it into the first message after the block in part 5, saying "save this as the project's MEMORY.md". Save the files in topic-memories/ the same way, one each, when a thread needs one. Two lines of memory.md are older than this file: the control panel's "privacy versions (next 24)" is now next 27 (25 merged, 26 held as a draft), and "Add token fixes thread" is done (part 6.4).

## 4. Repositories to add

Where: the Project's Settings, Repositories, Add. The Project needs only the first; threads attach the others with push access as their work needs them.

```
OpenSpineConsortium/symphony-template
OpenSpineConsortium/symphony-protocol
OpenSpineConsortium/coordbench
OpenSpineConsortium/flowbench
OpenSpineConsortium/symphony-app
OpenSpineConsortium/symphony-start
OpenSpineConsortium/symphony-extension
OpenSpineConsortium/symphony-marketplace
OpenSpineConsortium/openspineconsortium.github.io
OpenSpineConsortium/hpcworker
OpenSpineConsortium/spine-program
OpenSpineConsortium/beethoven-extension
```

A new account first connects GitHub: open https://claude.ai/connect-github, sign in as Gregory-Schwing-MD-PhD and press Authorize. The Claude GitHub App is already on every OpenSpineConsortium repository. For the OneDrive work, connect Microsoft 365 too: claude.ai, Settings, Connectors, Microsoft 365, Connect, and sign in with the Wayne State account.

## 5. First message for a new coordinator

Where: the new Project's chat, as the first message.

```
Pick up Symphony where the last Project stopped on 2026-10-18 at about 22:10 UTC, when every thread checkpointed. Read docs/checkpoints/2026-10-18b/handoff.md in OpenSpineConsortium/symphony-template first, then memory.md beside it (save memory.md as this Project's MEMORY.md and the files in topic-memories/ as topic memories). Each open pull request begins with "Checkpoint 2026-10-18b: ..."; that line is newer than the handoff.

Start nothing that spends: no bench run, pilot, batch, drive walk or Claude run without my word and number. The OneDrive work (template #227 and symphony-start #65) is paused until I say resume. Merge template #229 once its check is green. Then start one thread per workstream in part 6 when I ask for it, at most three at once. The rest wait on me (part 7).
```

## 6. Restart briefs, one per unfinished workstream

Each block is a thread's whole brief: start a thread on it from the project chat.

### 6.1 Protocol fixes toward 0.5.1 (symphony-protocol)

```
Protocol fixes toward 0.5.1, in OpenSpineConsortium/symphony-protocol (attach with push access). State on 2026-10-18b: 0.4.1 is the latest published release; 0.5.0 is merged and waits for my approval of its release run. F22 to F32 are merged; F32 (#54 at 1c58d5c, the guard reading text handed to another shell: bash -c, eval, trap, here-strings, echo or printf or cat piped into a shell) is unreleased and rides 0.5.1, with validate.yml's mutants job timeout at 90 minutes. Nothing is open of this thread's. The research note is docs/research/protocol-fixes-after-0-5-0/ in symphony-template. After I publish 0.5.0, each its own pull request: vendor 0.5.0 into symphony-template; switch tools/guard_push.py to guard.refused_push, the library's full check (until then the template's hook reads none of F29 or F32); apply the Budgeted counts and the PROTOCOL.md Release text from that folder README's follow-up; check whether the rulesets' "check" must name its app; then raise symphony-protocol to 0.5.1 for my approval. Then on #45 (locks) and #51 (Dependencies): merge main into each, mark ready and merge once green. Left by design: texts the command does not spell (substitution output, a file, a variable) and wrappers such as sudo and xargs; known over-refusals are a here-document body line that hands a push, bash -n -c, trap ... - and echo >/dev/null | bash. Never approve, publish or change a release or its approval gate.
```

### 6.2 Control panel sign-in (site, symphony-app, symphony-start)

```
Control panel sign-in, in OpenSpineConsortium/openspineconsortium.github.io, symphony-app and symphony-start (attach with push access). You own the sign-in and its Worker (https://symphony-signin.openspineconsortium.workers.dev, secrets only in Cloudflare), what each console section does, symphony-app's checks and manifests, the Dependencies, Folders and Explore tabs, and the privacy statement versions. Merged on 2026-10-18: the Explore tab (site #64, symphony-app #32, template #225) and the "Ask in claude.ai" button (site #66, symphony-app #33, privacy version 25, symphony-start #64). Open: symphony-start #65, privacy version 26 (the Folders tab reads the drive organizer's catalog.json from the branch drive-catalog when no drive is connected), a draft held for my "resume"; template #229, docs/setup/folders-admin-consent.md, the letter I send Wayne State C&IT for SymphonyBoard Folders (client id 463afc21-8bbd-429b-a93d-3d3617966f0b), draft, green, merge any time. On my "resume": write the Folders tab's catalog read in assets/js/symphony-panel.js (catalog.json from drive-catalog through the GitHub token, the same explorer, no Track in that mode, a connected drive taking over), add its panel checks in symphony-app, merge #65, then the code. The catalog's shape is in docs/research/drive-organizer.md (template #227). Not started: the Dependencies tab tabbed per epic and more graphical. Never build a route that borrows a signed-in Wayne State or OneDrive session from a page or an extension. Each feature needs its privacy statement version live first, the next after main's (27 next), with symphony-app's manifest.json and manifest-setup.json matching; every signed-in page must be a SymphonyBoard Callback URL, which is my click, given with its exact link.
```

### 6.3 Organize a whole OneDrive, and several lenses on one Word file (symphony-template)

```
The drive organizer and lens review, in OpenSpineConsortium/symphony-template. Merged: #221 and #223, the workflow drive-organize.yml (catalog, organize, accept), tools/drive_organize.py and tools/file_digest.py. Open: #227 (branch claude/project-thread-owq15w), green, paused on my word until I say resume: tools/drive_connector.py walks my OneDrive through the Microsoft 365 connector from a Claude session (no Wayne State consent needed), writes the same catalog.json for drive-catalog with dates and web links from the connector's search, proposes projects (some with a Symphony repository of their own that students join on their own Claude accounts), opens them through the workflow's new step open, and plans moves into "Symphony projects/" that run one connector call at a time only after approve, every one undoable, nothing deleted, Microsoft 365's app folders never moved; and tools/docx_review.py panel, several reviewer lenses each writing tracked changes and comments under its own author name. The procedures are .claude/skills/drive-organize and .claude/skills/lens-review; the notes docs/research/drive-organizer.md and docs/research/lens-review.md. On my "resume": merge main into #227, run the check, mark it ready and merge once green, and tell the Control panel sign-in thread. A walk of my drive spends my usage and waits for my word; nothing in the drive moves or is renamed until I have read MOVES.md and said go. The connector reads a Word file only as text, so a lens review works on a .docx the sync brings in or I attach. Pooling students' Claude accounts is not built: it waits on my answer to the decision card (recommended: each on their own account).
```

### 6.4 Claude tokens and agents (symphony-template, site)

```
Claude tokens and importable agents. Built and merged: tokens with an id and owner, a pool of 32 slots (organization secrets SYMPHONY_CLAUDE_1-32 and CLAUDE_CODE_OAUTH_TOKEN, renew by 2027-10-17), Add a Claude account minted on an Actions runner, the Tokens tab, the Leaderboard and agents (.claude/agents/ reviewer, developer, tester). On 2026-10-18 site #65 made Add Token read token.yml first and explain a 404 (merge the adoption pull request first, SymphonyBoard not on the repository, or the workflow off), remember a sign-in under way, and poll past GitHub's 60 s cache; template #224 is docs/research/token-add-faults.md; issue #222 is closed. Open, on my word: token.yml runs 2, 5 and 6 took the code and printed nothing in 60 s. Proposed: set TERM: xterm-256color in token.yml's step, since a runner sets none and claude then draws changed cells with cursor moves that could split a token past tokens.Masker, and have tools/token_run.py report counts alone on failure (bytes after Enter, whether claude still runs, whether the mask holds back a tail). Ashley's aschehr/OpenSpineToolbox-S1fix-2Dprojection needs its adoption pull request merged before Add Token works there. TILE_MODELS in symphony-panel.js must equal KNOWN_MODELS in tools/pool.py. Any real token run is mine.
```

### 6.5 Native git locks (symphony-protocol #45)

```
Native git locks, symphony-protocol#45 (branch claude/native-git-locks, draft). Held until 0.5.1 is cut. Then merge main in, run the checks, mark ready and merge once green; then one symphony-template pull request wires the claim skill, the board sweep, the protocol check and a ruleset on the branch locks. The note is docs/research/native-git-locks.md; the facts are the native-git-locks topic memory. A coordbench locks arm waits for my word and the run count.
```

### 6.6 Experiments (coordbench, flowbench, beyond cooperation)

```
Experiments, held. coordbench's curse-of-coordination full run is recorded (215 runs, coordbench#28, template note #146); research on it is held until I say I understand why the curse exists, though explaining it from PARITY.md and the recorded run is welcome. flowbench's pilot is recorded (24 runs, flowbench#2, note #157); its 96-run stage waits for my word. Beyond cooperation steps 1-4 are merged (epics #127-#130, tasks #131-#144 in symphony-template, in the open queue); each task's first PR builds its arm under docs/research/beyond-cooperation/arms/ and stops. No run that spends tokens without my word and number.
```

### 6.7 The AIDaS grant (spine-program)

```
The AIDaS seed grant in OpenSpineConsortium/spine-program. Read the aidas-grant topic memory and RECORD.md in 01_carm_level_detection/grants/aidas_2027/ before anything. What is left is mine (part 7 of the handoff); help only when I ask. No adversarial reviews on spine-program.
```

## 7. Waiting on greg, numbered

1. Approve symphony-protocol 0.5.0: open https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117, press "Review deployments", tick "release", press "Approve and deploy".
2. Say "resume" for the OneDrive work when you want it: template #227 (https://github.com/OpenSpineConsortium/symphony-template/pull/227) and privacy version 26 (https://github.com/OpenSpineConsortium/symphony-start/pull/65).
3. Wayne State consent for SymphonyBoard Folders: once template #229 merges, open docs/setup/folders-admin-consent.md at https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/setup/folders-admin-consent.md, copy the letter and send it to C&IT from Outlook.
4. Answer the decision card on students pooling Claude accounts (recommended: each on their own account).
5. Tokens: say whether to try TERM: xterm-256color in token.yml (6.4); in https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions delete any hand-made SYMPHONY_CLAUDE_ACCOUNTS.
6. Grant: in Outlook (https://outlook.office.com/mail/drafts) open the draft to Han and Schwiebert, attach the final PDF, press Send; send the same PDF to aidas@wayne.edu; fill the real values; decide allowability; do the disclosure audit; update Overleaf.
7. Delete stale branches (sessions cannot): https://github.com/OpenSpineConsortium/beethoven-extension/branches (claude/update-check), https://github.com/OpenSpineConsortium/symphony-template/branches (symphony-locks/probe), https://github.com/OpenSpineConsortium/hpcworker/branches (claude/grid-gate-scaffold); press the trash icon on each row.
8. Until 0.5.0 is published, Monday's "Vendor symphony-protocol 0.4.1" pull request in symphony-template opens red: close it at https://github.com/OpenSpineConsortium/symphony-template/pulls with "Close pull request".
9. Say which autonomous-software-agent repository you meant.
10. Grid: say whether hpcworker's rule on "a token held as a secret" covers the grid's ssh gate key.
11. Control board: the issue-type and Projects v2 clicks in docs/research/control-board-graph.md.
12. Your word for any real drive organizer, lens review or Word revision run, and for any benchmark run.
13. Curse of coordination: say whether the explanation answers why it exists.
14. Optional: install Symphony Setup on symphony-start only at https://github.com/apps/symphony-setup/installations/new.

## 8. Open pull requests, 2026-10-18 22:10 UTC

Read by the REST API for symphony-template, and from the threads' reports for the others (symphony-protocol was not attached to this session).

| Pull request | State | Next step |
| --- | --- | --- |
| symphony-template#227 OneDrive through the connector, lenses on one Word file | draft, check green | paused until greg says resume (6.3) |
| symphony-template#229 Wayne State consent letter | draft, green | merge any time (6.2) |
| symphony-template (this handoff) | ready | merge once green |
| symphony-start#65 privacy version 26 | draft | held for greg's resume (6.2) |
| symphony-protocol#51 Dependencies | draft | hold until 0.5.1 (6.1) |
| symphony-protocol#45 locks | draft | hold until 0.5.1 (6.5) |
