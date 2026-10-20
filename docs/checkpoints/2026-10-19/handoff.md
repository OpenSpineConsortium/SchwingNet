# Symphony handoff, 2026-10-19

Source: the thread "Control panel sign-in", 2026-10-19 at about 21:00 UTC, on the owner's ask at 20:55 UTC to push everything and write a handoff so he can continue every thread exactly. It is written from the checkpoint replies of the threads Add token fixes, Drive organizer, Grant final review and submission, and C&IT consent email draft (all at 20:56 UTC), the last replies of the resolved threads Protocol fixes toward 0.5.1 and Rust coordinator research, this thread's own work, and the Project memory. It replaces docs/checkpoints/2026-10-18b/handoff.md as the place to start. Beside it: memory.md (the Project memory at the handoff, 12 KB, which imports whole), topic-memories/ (the fourteen topic memories) and plans/fit-every-tab.md (the plan for making every control panel tab fit the screen, which lived only in the Project's files).

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
Build Symphony, OpenSpineConsortium's open coordination product for Claude Code, and prove that it works. Symphony lets many Claude sessions, routines and GitHub Actions workers share one repository without stepping on each other: the claim protocol as a library (symphony-protocol), the template that keeps a Claude project as files in a repository (symphony-template), the two GitHub Apps and the one-press front door, the plugin, and the control panel on openspineconsortium.com, which also organizes a person's OneDrive into projects and notebooks. The proof is measured: replicate CooperBench's curse of coordination and remove it with Symphony's protocol (coordbench), benchmark agentic workflows (flowbench), and go beyond cooperation against MAST's failure modes. This Project also carries my related work: the AIDaS spine grant (spine-program), the Beethoven extension and Symphony on the WSU grid. Done for now means every control panel tab fitting the screen with no scroll, the explorer modernized, the OneDrive work on direct Microsoft Graph now that Wayne State has consented, and the full coordination run recorded with its results.
```

## 3. Memory

Where: in a new account's Project the memory starts empty. Open memory.md beside this file at https://github.com/OpenSpineConsortium/symphony-template/blob/main/docs/checkpoints/2026-10-19/memory.md, press the copy-raw button, and paste it into the first message after the block in part 5, saying "save this as the project's MEMORY.md". Save the files in topic-memories/ the same way, one each, when a thread needs one. project-state-2026-10-19.md is a snapshot of 03:00 UTC; this file is newer where they differ.

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
OpenSpineConsortium/onedrive
```

A new account first connects GitHub: open https://claude.ai/connect-github, sign in as Gregory-Schwing-MD-PhD and press Authorize. The Claude GitHub App is already on every OpenSpineConsortium repository. For the OneDrive and Outlook work, connect Microsoft 365 too: claude.ai, Settings, Connectors, Microsoft 365, Connect, and sign in with the Wayne State account.

## 5. First message for a new coordinator

Where: the new Project's chat, as the first message.

```
Pick up Symphony where the last Project stopped on 2026-10-19 at about 21:00 UTC, when every thread checkpointed with nothing unpushed and no pull request open. Read docs/checkpoints/2026-10-19/handoff.md in OpenSpineConsortium/symphony-template first, then memory.md beside it (save memory.md as this Project's MEMORY.md and the files in topic-memories/ as topic memories).

News since the last handoff: Wayne State approved SymphonyBoard connecting to OneDrive natively, so the switch to direct Microsoft Graph is unblocked (part 6.3). The explorer looks janky: modernizing it is next work (part 6.2), not built yet.

Start nothing that spends: no bench run, pilot, batch, drive walk, move or Claude run without my word and number. Start one thread per workstream in part 6 when I ask for it, at most three at once. The rest wait on me (part 7).
```

## 6. Restart briefs, one per workstream

Each block is a thread's whole brief: start a thread on it from the project chat.

### 6.1 Control panel sign-in (site, symphony-app, symphony-start)

```
Control panel sign-in, in OpenSpineConsortium/openspineconsortium.github.io, symphony-app and symphony-start (attach with push access). You own the sign-in and its Worker (https://symphony-signin.openspineconsortium.workers.dev, secrets only in Cloudflare), what each console section does, symphony-app's checks and manifests, the Dependencies, Folders, Explore and Notebooks tabs, and the Apps' privacy statement versions (symphony-start PRIVACY.md and its site page /symphony/apps-privacy.html). State on 2026-10-19, all merged and live: privacy statement 35 (symphony-start #78, site #94: Google Fonts on the panel pages, what Sign in with GitHub keeps in the tab, the installed app's sign-in, sign-in by code shipped switched off, what Forget revokes, the Dependencies chart choice); all three panels resizable and the site bar hiding like a taskbar on the control page (site #93, checks symphony-app #47); the Dependencies tab on a zoom stage with no scroll, tap to focus a node with its neighbours (site #95, checks #49; stage functions stageMake to stageResized in assets/js/symphony-panel.js). Next, each its own pull request: (1) make the panel's own "What this page keeps and sends" (tools/pages/symphony/control/index/body.html, admin__lead) match statement 35: Google Fonts, the pending sign-in record, the stored chart choice. (2) Every other tab fits the screen with no scroll, per plans/fit-every-tab.md beside the handoff, with greg's card answer "Chips" (very long lists as numbered chips coloured by state, or a map of sections, that a pinch or tap opens); held until greg says go. (3) The explorer modernization, part 6.2. greg tests the usual Sign in with GitHub in the installed iPhone app; sign-in by code (CODE_SIGNIN) stays false unless that test fails, and then the Device Flow decision comes back to him. Mendeley: the plan is docs/research/mendeley-sign-in.md in symphony-template; no code until greg has registered the app (its "The owner's steps") and its two values are in the Worker. Each feature needs its privacy statement version live first, the next after main's (36 next), with symphony-app's manifest.json and manifest-setup.json matching; every signed-in page must be a SymphonyBoard Callback URL, which is greg's click, given with its exact link. Run the panel suites from symphony-app signin/panel-checks (signin, panel, hostile, app, assistant, graph, folders, explore, notebooks, code) and run-mutants.sh before each merge; the site has no CI, so build it with tools/build_site.py (SYMPHONY_START_REPO set to a symphony-start checkout) and expect 0 problems.
```

### 6.2 Modernize the explorer (site, symphony-app)

```
Modernize the control panel's explorer, in OpenSpineConsortium/openspineconsortium.github.io with its checks in symphony-app (attach both with push access); the Control panel sign-in thread owns these files, so this is its work or a thread it hands the files to. greg, 2026-10-19 20:55 UTC: "the exploreer looks janky so work on modernizing it and making it take up most of the panel when using it, and built out some features for it". The default reading is the Explore tab (tab-explore: the project as a map one level at a time, repository, goals and epics, tasks, pull requests or claim branch, Actions runs, jobs, steps, log lines with Claude's steps marked; code exDraw, exTile, exTree, exZoom and their companions near the end of assets/js/symphony-panel.js; checks e2e2/explore.test.mjs). The Folders tab's file explorer (site #63) is the other reading: ask greg in one line which he meant before building, and build the Explore tab meanwhile. What it needs: (1) a modern look in the panel's own tokens, cards with gear, X and click-for-status, the + tile style, no forms, as greg wants everywhere; (2) while it is in use it takes most of the panel: the side column and the foot shrink or fold away (the grips from site #93 keep working, and a press brings them back), on a phone the whole stage; (3) no scroll, on the Dependencies tab's zoom stage: pinch, wheel and +/- to zoom, tap to focus a node with its neighbours, swipe or arrows to move between them; (4) features, proposed to greg as a short list before they are built: a breadcrumb that jumps to any level, search across tasks, pull requests and runs, filters by state (open, failing, running, Claude's), a live view of a running job's log, a re-run or cancel button for a run where the token allows, and links out to GitHub at every level. Keep the read budget the tab has (it reads below a task only on entry and stops with 100 API calls left). If what it reads or keeps changes, the privacy statement's next version goes live first. Screenshots at 1440x900, 390x844 and 844x390 go in the reply.
```

### 6.3 OneDrive on direct Microsoft Graph (site, symphony-app, symphony-template)

```
Switch the OneDrive work from the Microsoft 365 connector to direct Microsoft Graph. greg, 2026-10-19 20:55 UTC: Wayne State approved SymphonyBoard to connect to OneDrive natively, so the C&IT admin consent the letter asked for (docs/setup/folders-admin-consent.md, template #229 and #255) is given and the switch is unblocked. The Entra app is "SymphonyBoard Folders", client id 463afc21-8bbd-429b-a93d-3d3617966f0b, with MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET in the sign-in Worker. First confirm it live: greg signs in on the Folders tab with his Wayne State account and it no longer asks for an administrator's approval (give him the exact link and button). Then, as greg asked, one code path for every reader: the Folders tab, the Notebooks tab and the drive walk (tools/drive_connector.py today, which writes catalog.json on the onedrive repository's branch drive-catalog) all read through Graph with the panel's sign-in, the connector kept only as the fallback where no sign-in exists. The Control panel sign-in thread owns the Folders and Notebooks tabs and the privacy statement; the Drive organizer thread owns the catalog's data (docs/research/drive-organizer.md, docs/research/notebooks.md, the control-panel-notebooks topic memory for the sha discipline). Each changes its own files and hands changes to the other through the coordinator. Privacy statement 36 goes live before any of it ships. Never build a route that borrows a signed-in Wayne State or OneDrive session from a page or an extension. Nothing on the drive moves or is renamed without greg's go.
```

### 6.4 Drive organizer and notebooks (symphony-template, onedrive)

```
The drive organizer, in OpenSpineConsortium/symphony-template and the private OpenSpineConsortium/onedrive. Merged: Word citations (tools/docx_cite.py, #244, notes #246 and #247; Word desktop filled the reference list), tools/notebook.py (#239). On onedrive's branch drive-catalog (27f1b2a): seven project proposals from 24 files read, plan.json, notebooks.json, each notebook's starting files under notebooks/, and MOVES.md. Nothing on the drive has moved. Next: (1) the switch to direct Graph, part 6.3, which you share with the Control panel sign-in thread; (2) when greg creates a notebook-* repository, copy its folder from notebooks/ into it by pull request (a new repository's first commit is his); (3) moves only after greg has read MOVES.md and said go, one call at a time, each undoable; (4) Zotero Refresh is still untested; (5) the test copies in the OneDrive folder "Symphony citation test" may be deleted on greg's word. A walk of the drive spends greg's usage and waits for his word.
```

### 6.5 Tokens and adopted repositories (symphony-template, symphony-start, site)

```
Claude tokens and the adopted repositories. Merged on 2026-10-19: the links-to-fixes change on the control panel (site #90, #91); new protocol-only adoptions get the Token workflow (symphony-start #76); the template offers every adopted repository its board, tidy, metrics and Token files by pull request from symphony/sync, on every change of those files and weekly (template #257, sync.yml, tools/sync_adopted.py); its first run, https://github.com/OpenSpineConsortium/symphony-template/actions/runs/39288858429, offered three repositories a pull request. Next: (1) greg checks that the organization's SDLC_APP_ID and SDLC_APP_PRIVATE_KEY are shared with All repositories, or lending a token in a protocol-only repository such as spine-program stops with a message (part 7); (2) the three symphony/sync pull requests: merge the ones in OpenSpineConsortium's repositories once green, on the standing permission, and leave the others to their owners; (3) Ashley's Add Slot on spine-program should work through the pool once spine-program's sync pull request is merged; the real test is greg's. If either merged change is edited so that what is read, written or logged changes, the Control panel sign-in thread writes the next privacy statement version (36). TILE_MODELS in symphony-panel.js must equal KNOWN_MODELS in tools/pool.py. Any real token run is greg's.
```

### 6.6 Protocol and the workflow compiler (symphony-protocol, symphony-template, symphony-start)

```
The protocol. symphony-protocol 0.5.1 was published on 2026-10-19 (greg approved it) and is vendored in symphony-template (tools/VENDORED). Merged: Dependencies (#51), native git locks (#45), the check pinned to GitHub Actions in setup-repo.sh and both live rulesets, symphony-start #69 (Symphony Setup stays installed) and #72 (the one settings list, settings.json, and organization token lending), privacy statement 32; actionlint and zizmor run in the required check (template #250). Nothing is open. Next, each its own pull request when greg says: Candidate A, the Python compiler to workflow YAML, with the gh-aw canary pilot (docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md; its PR 1a pins actions to commits), on greg's go only; close the mismatches between scripts/setup-repo.sh and symphony-start's setup.py listed in the setup-app-org-settings topic memory; correct docs/memory/protocol-changes-come-from-symphony-protocol.md and its MEMORY.md line, which still say the template vendors 0.5.0 waiting for approval. Never approve, publish or change a release or its approval gate without greg's own words.
```

### 6.7 Experiments (coordbench, flowbench, beyond cooperation)

```
Experiments, held. coordbench's curse-of-coordination full run is recorded (215 runs, coordbench#28, template note #146); research on it is held until greg says he understands why the curse exists, though explaining it from PARITY.md and the recorded run is welcome. flowbench's pilot is recorded (24 runs, flowbench#2, note #157); its 96-run stage waits for his word. Beyond cooperation steps 1-4 are merged (epics #127-#130, tasks #131-#144 in symphony-template, in the open queue); each task's first PR builds its arm under docs/research/beyond-cooperation/arms/ and stops. No run that spends tokens without greg's word and number.
```

### 6.8 The AIDaS grant and program (spine-program)

```
The AIDaS seed grant and program in OpenSpineConsortium/spine-program. Read the aidas-grant topic memory and RECORD.md in 01_carm_level_detection/grants/aidas_2027/ before anything. Merged: the program map 13_aidas_program (#183: goal #121, ten epics, 50 tasks), the 21 fluoroscopy video datasets as issues #186-#206 under epic #185 (#207), and the record that Claude may read Elsevier text for academic use while the token and the text stay private (#209); no model is trained on it. Open: the offer to draft the trainee study's exempt IRB application, task E2.3, on greg's word. The rest is greg's (part 7). No adversarial reviews on spine-program.
```

## 7. Waiting on greg, numbered

1. Check the organization's App values are shared with every repository: open https://github.com/organizations/OpenSpineConsortium/settings/variables/actions, press SDLC_APP_ID, and under Repository access make sure "All repositories" is chosen (press Update if you change it); then the same for SDLC_APP_PRIVATE_KEY at https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions.
2. Confirm Wayne State's consent works: open https://openspineconsortium.com/symphony/control/, press Sign in with GitHub, open the Folders tab, connect OneDrive and sign in with your Wayne State account; it should not ask for an administrator's approval. Say what you see, and the thread in 6.3 starts.
3. On the iPhone, open the installed Symphony app, press Sign in with GitHub and say whether it comes back signed in.
4. Say which explorer you meant: the Explore tab (the project map) or the Folders tab's file explorer (6.2).
5. Say go for the other tabs to fit the screen (6.1, plans/fit-every-tab.md) when your usage allows.
6. Mendeley: when you want it, register the app as docs/research/mendeley-sign-in.md, "The owner's steps", says.
7. Ashley's Add Slot test on spine-program, once its symphony/sync pull request is merged (6.5).
8. Drive: read MOVES.md at https://github.com/OpenSpineConsortium/onedrive/blob/drive-catalog/MOVES.md and say go or not; to start a notebook, make its private repository at https://github.com/organizations/OpenSpineConsortium/repositories/new with "Add a README file" ticked and Private chosen, press Create repository, and tell the thread its name.
9. Grant: the real values; allowability; the disclosure audit; Overleaf; the IRB amendment (the draft is in the old Project's files under grant-irb/, never in git); spine-program #198 (CAMS-Knee licence) and #199 (CathAction form); say whether to draft the exempt IRB application (E2.3).
10. The Elsevier API key, the insttoken and the Zotero key as GitHub secrets, if not done yet; the thread that first reads them gives the exact page and names.
11. Delete two stale branches (sessions cannot): https://github.com/OpenSpineConsortium/symphony-template/branches (symphony-locks/probe) and https://github.com/OpenSpineConsortium/hpcworker/branches (claude/grid-gate-scaffold, not checked from this session); press the trash icon on each row. beethoven-extension's claude/update-check is already gone.
12. In https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions delete a hand-made SYMPHONY_CLAUDE_ACCOUNTS if it is still there (sessions cannot read that page).
13. Go or no for Candidate A, the YAML compiler, and the gh-aw canary (6.6).
14. Say which autonomous-software-agent repository you meant.
15. Grid: say whether hpcworker's rule on "a token held as a secret" covers the grid's ssh gate key.
16. Control board: the issue-type and Projects v2 clicks in docs/research/control-board-graph.md.
17. Your word for any real drive walk, lens review or Word revision run, and for any benchmark run; the decision card on students pooling Claude accounts (recommended: each on their own account).
18. Curse of coordination: say whether the explanation answers why it exists.
19. Optional: install Symphony Setup on symphony-start only at https://github.com/apps/symphony-setup/installations/new.

## 8. Open pull requests, 2026-10-19 21:00 UTC

None of the threads has a pull request open. Read by the REST API: symphony-template, symphony-start, openspineconsortium.github.io, symphony-app, symphony-extension and beethoven-extension have none open but this handoff's. The other repositories were not attached to this session, and their threads report none open. Outside them, the three symphony/sync pull requests in adopted repositories wait as 6.5 says.
