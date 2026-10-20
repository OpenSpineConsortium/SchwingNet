# Symphony handoff, 2026-10-18

Source: the thread "Checkpoint and handoff", 2026-10-18 at about 13:15 UTC, on the owner's ask at 13:02 UTC to checkpoint every thread at once with 3% of his usage left, then stop all work. This file replaces docs/checkpoints/2026-10-16/handoff.md and docs/checkpoints/2026-10-18-control-panel/HANDOFF.md as the place to start. Beside it: memory.md (the Project memory, compressed under 12 KB so it imports), memory-full.md (the memory verbatim at the handoff, 15.9 KB) and topic-memories/ (the seven topic memories). Each open pull request's own description and its thread's last reply are newer than this file where they differ.

Every block below is copied whole, without the fence lines.

## 1. Project instructions

Where: claude.ai, the Project's settings, the Instructions field. Paste over what is there and press Save.

```
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
Commit what you find, intermediate or final, under docs/research/ in symphony-template with its line in docs/research/README.md, by pull request, before you stop.
Put every manual step for me in the reply's own text, numbered, never only on a card, in a widget or in a file.
```

## 2. Project goal

Where: the Project's settings, the Goal (or Topic) field. Paste and press Save.

```
Build Symphony, OpenSpineConsortium's open coordination product for Claude Code, and prove that it works. Symphony lets many Claude sessions, routines and GitHub Actions workers share one repository without stepping on each other: the claim protocol as a library (symphony-protocol), the template that keeps a Claude project as files in a repository (symphony-template), the two GitHub Apps and the one-press front door, the plugin, and the control panel on openspineconsortium.com. The proof is measured: replicate CooperBench's curse of coordination and remove it with Symphony's protocol (coordbench), benchmark agentic workflows (flowbench), and go beyond cooperation against MAST's failure modes. This Project also carries my related work: the AIDaS spine grant (spine-program), the Beethoven extension and Symphony on the WSU grid. Done for now means the protocol fixes released as 0.5.1 and vendored into the template, the open pull requests landed, and the full coordination run recorded with its results.
```

## 3. Memory

Where: in the same Project, nothing to do; the memory stays. In a new Project or account: open memory.md beside this file at https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-18/memory.md, press the copy-raw button, and paste it into the first message after the block in part 5, saying "save this as the project's MEMORY.md". The topic memories in topic-memories/ are saved the same way, one file each, only when a thread needs one.

## 4. Repositories to add

Where: the Project's settings, Repositories, Add. The Project needs only the first; threads attach the others with push access as their work needs them.

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

A new account first connects GitHub: open https://claude.ai/connect-github, sign in as Gregory-Schwing-MD-PhD and press Authorize. The Claude GitHub App is already on every OpenSpineConsortium repository.

## 5. First message for a new coordinator

Where: the project chat, as the first message.

```
Pick up Symphony where the last Project stopped on 2026-10-18 at about 13:15 UTC, when every thread checkpointed and all work stopped. Read docs/checkpoints/2026-10-18/handoff.md in OpenSpineConsortium/symphony-template first, then memory.md beside it (if this Project's memory is empty, save memory.md as MEMORY.md and the files in topic-memories/ as topic memories). Each open pull request begins with "Checkpoint 2026-10-18: ..."; that line is newer than the handoff.

Start nothing that spends: no bench run, pilot or batch without my word and number. First merge symphony-protocol#53 (F29) by hand once its CI is green, with the head sha from git, and check template #185 and #211 merged. Then start one thread per workstream in part 6 of the handoff, at most three at once, each from its brief there, in this order: the protocol fixes, the control panel sign-in, then whichever I ask for. The rest wait on me (part 7).
```

## 6. Restart briefs, one per unfinished workstream

Each block is a thread's whole brief: start a thread on it from the project chat.

### 6.1 Protocol fixes toward 0.5.1 (symphony-protocol)

```
Protocol fixes toward 0.5.1, in OpenSpineConsortium/symphony-protocol (attach with push access). State on 2026-10-18: 0.4.1 is the latest published release; 0.5.0 is merged and waits for my approval of its release run. F22 to F28, F30 (#50) and F31 (#52) are merged. F29 (#53, branch claude/owner-decisions-f29-words-built) is ready with both reviews answered and main merged in; merge it by hand once CI is green (auto-merge is off there), with the head sha copied from git, and check main's tree after. The thread's research note is symphony-template#211. Next, each its own pull request: the push guard's misses (git push origin $'main', git pu$(true)sh origin main, here-documents). After I publish 0.5.0: vendor it into symphony-template, move the template's guard onto the library's full check, check whether the rulesets' "check" must name its app, then raise to 0.5.1 for my approval. Drafts #45 (locks) and #51 (Dependencies) stay drafts until 0.5.1 is cut; then merge main into each, mark ready and merge once green. Never approve, publish or change a release or its approval gate.
```

### 6.2 Control panel sign-in (site, symphony-app, symphony-start)

```
Control panel sign-in, in OpenSpineConsortium/openspineconsortium.github.io, symphony-app and symphony-start (attach with push access). You own the sign-in and its Worker (https://symphony-signin.openspineconsortium.workers.dev, secrets only in Cloudflare), what each console section does, symphony-app's checks and manifests, and the Dependencies and Folders tabs. Open drafts: site #36 (the Dependencies section, branch claude/graph-section), symphony-app #19 (its checks, claude/graph-checks), symphony-app #21 (the Folders page's checks, claude/folders-checks), and the Folders tab's site #37; symphony-protocol #51 (Dependencies in the protocol) is held until 0.5.1. Read each one's "Checkpoint 2026-10-18" line first and carry on from it. Each feature needs its privacy statement version in symphony-start PRIVACY.md live first, the next version after main's when it merges, with symphony-app's manifest.json and manifest-setup.json matching; tell the coordinator and rebuild the site. Every signed-in page must be a SymphonyBoard Callback URL; adding one is my click, given with its exact link.
```

### 6.3 Native git locks (symphony-protocol #45)

```
Native git locks, symphony-protocol#45 (branch claude/native-git-locks, draft, CI green at e66578b). Held until 0.5.1 is cut. Then merge main in, run the checks, mark ready and merge once green; then one symphony-template pull request wires the claim skill, the board sweep, the protocol check and a ruleset on the branch locks. The note is docs/research/native-git-locks.md; the facts are the native-git-locks topic memory. A coordbench locks arm waits for my word and the run count.
```

### 6.4 Claude tokens and agents (symphony-template, site)

```
Claude tokens and importable agents. Built and merged on 2026-10-18: tokens with an id and owner, a pool of 32 slots (organization secrets SYMPHONY_CLAUDE_1-32 and CLAUDE_CODE_OAUTH_TOKEN), Add a Claude account minted on an Actions runner, the Tokens tab's tiles with a gear and side panel, per-repository switches, the Leaderboard tab, and agents (.claude/agents/ reviewer, developer, tester; site Agents tab; accounts.json "workers" mapping agents to slots). Nothing is open. Next only on my word: an organization App for members' changes; other runtimes; importing a folder or a plugin's agents; an agents leaderboard once benchmark results exist. TILE_MODELS in symphony-panel.js must equal KNOWN_MODELS in tools/pool.py. Nothing spends until an agent is run, and no run without my word.
```

### 6.5 Experiments (coordbench, flowbench, beyond cooperation)

```
Experiments, held. coordbench's curse-of-coordination full run is recorded (215 runs, coordbench#28, template note #146); research on it is held until I say I understand why the curse exists, though explaining it from PARITY.md and the recorded run is welcome. flowbench's pilot is recorded (24 runs, flowbench#2, note #157); its 96-run stage waits for my word. Beyond cooperation steps 1-4 are merged (epics #127-#130, tasks #131-#144 in symphony-template, in the open queue); each task's first PR builds its arm under docs/research/beyond-cooperation/arms/ and stops. No run that spends tokens without my word and number.
```

### 6.6 The AIDaS grant (spine-program)

```
The AIDaS seed grant in OpenSpineConsortium/spine-program. Read the aidas-grant topic memory and RECORD.md in 01_carm_level_detection/grants/aidas_2027/ before anything. What is left is mine (part 7 of the handoff); help only when I ask. No adversarial reviews on spine-program.
```

## 7. Waiting on greg, numbered

1. Approve symphony-protocol 0.5.0: open https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117, press "Review deployments", tick "release", press "Approve and deploy".
2. Grant: in Outlook (https://outlook.office.com/mail/drafts) open the draft to Han and Schwiebert, attach the final PDF, press Send; send the same PDF to aidas@wayne.edu; fill the real values for the approximations; decide allowability (B, C3, D, F); do the disclosure audit (rule 8); update Overleaf.
3. Tokens: on https://openspineconsortium.com/symphony/control/ open Tokens and press "+ Add Token" once more; in https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions delete any hand-made SYMPHONY_CLAUDE_ACCOUNTS; answer the Tokens thread's card on an organization App for members' changes.
4. Delete stale branches (sessions cannot): https://github.com/OpenSpineConsortium/beethoven-extension/branches (claude/update-check), https://github.com/OpenSpineConsortium/symphony-template/branches (symphony-locks/probe, claude/festive-edison-al7xu2 if merged), https://github.com/OpenSpineConsortium/hpcworker/branches (claude/grid-gate-scaffold); press the trash icon on each row.
5. Say which autonomous-software-agent repository you meant.
6. Until 0.5.0 is published, Monday's "Vendor symphony-protocol 0.4.1" pull request in symphony-template opens red: close it at https://github.com/OpenSpineConsortium/symphony-template/pulls with "Close pull request".
7. Grid: say whether hpcworker's rule on "a token held as a secret" covers the grid's ssh gate key.
8. Control board: the issue-type and Projects v2 clicks in docs/research/control-board-graph.md; whether to use Linear; graph hosting.
9. Word revisions: the Microsoft Entra app registration clicks once the Folders tab exists; your word for real runs.
10. Curse of coordination: say whether the thread's explanation answers why it exists.
11. Optional: install Symphony Setup on symphony-start only at https://github.com/apps/symphony-setup/installations/new.
12. Share: grant SymphonyBoard repository Administration at https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard/permissions (Repository permissions, Administration: Read and write, Save), then accept it at https://github.com/organizations/OpenSpineConsortium/settings/installations.
13. Agents: your word on the unbuilt options in 6.4 and on any benchmark run.

## 8. Open pull requests, 2026-10-18 13:15 UTC

Read by the REST API for symphony-template and symphony-protocol, and by the Project's pull request list for the others (which misses some; a thread reads its repository's list itself before acting).

| Pull request | State | Next step |
| --- | --- | --- |
| symphony-protocol#53 F29 | ready, CI running | merge by hand once green (6.1) |
| symphony-protocol#51 Dependencies | draft | hold until 0.5.1 (6.1, 6.2) |
| symphony-protocol#45 locks | draft, green at e66578b | hold until 0.5.1 (6.3); its Checkpoint line was not written, since this session's write to that repository was refused |
| symphony-template#185 new-user settings note | ready, main merged in, auto-merge on | merges by itself once check passes |
| symphony-template#211 protocol fixes note | ready, auto-merge on | merges by itself once check passes |
| symphony-template (this handoff) | ready | merge once green |
| openspineconsortium.github.io#36 Dependencies section | draft | Control panel sign-in (6.2) |
| openspineconsortium.github.io#37 Folders tab | draft or open | Control panel sign-in (6.2) |
| symphony-app#19 Dependencies checks | draft | Control panel sign-in (6.2) |
| symphony-app#21 Folders checks | draft | Control panel sign-in (6.2) |

Unchecked from this session (no access attached): coordbench, flowbench, symphony-start, symphony-extension, symphony-marketplace, hpcworker, spine-program, beethoven-extension; the threads that worked there were idle with nothing open by their last replies.
