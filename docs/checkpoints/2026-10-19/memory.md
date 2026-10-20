Compressed 2026-10-18 from memory-full.md beside this file (symphony-template docs/checkpoints/2026-10-18/); a PR or newer checkpoint wins. History lives in git and the handoff.

## Project and environment
- Owner and only member: greg (GitHub Gregory-Schwing-MD-PhD), organization OpenSpineConsortium. He dictates; expect sound-alikes ("ADIS" = AIDaS, "Warren" = Loren).
- symphony-template is home: handoffs in docs/checkpoints/<date><letter>/, findings in docs/research/ with a README line. Main needs a branch up to date with main and a green "check"; merge commits; head branches auto-deleted.
- Repositories: symphony-protocol(-canary), coordbench, flowbench, symphony-app, symphony-start, symphony-extension, symphony-marketplace, spine-program (grant), beethoven-* (greg's proprietary), openspineconsortium.github.io (site), hpcworker (grid), onedrive (private; drive-catalog branch holds catalog.json and notebooks.json, 2026-10-19).
- Sessions can't delete branches, approve deployments, publish releases, change rulesets or see secrets; gh GraphQL is blocked, REST works; other repositories need add_repo first. list_project_prs is incomplete. New org repos default to Internal: check visibility.
- Connectors: Claude Docs, Microsoft 365 (WSU Outlook), Google Drive; no Gmail, so mail is a draft greg sends. greg's PC only through the desktop app's folder access.
- WebFetch can't reach github.com, docs.github.com, arXiv or Hugging Face: use raw.githubusercontent.com, a clone or WebSearch.
- Containers restart: push before long steps. Several accounts push to the same branches: read a PR's commits first. A new repository's first commit is greg's.
- Topic memories: aidas-grant, experiments, control-board-graph-research, control-panel-signin, native-git-locks, curse-of-coordination-hold, beyond-cooperation-step-4 (copies in topic-memories/).

## greg's standing rules (verbatim)
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
Also: merge commits with the head sha from git; bring main in by merging, never rebase. Briefs say to commit findings under docs/research/ with a README line and to number manual steps in the reply's own text with exact links. No adversarial reviews on spine-program; keep the second review round on protocol fixes. When greg is low on usage he says to skip adversarial review; obey.
- 2026-10-19: greg amended the no-API-key rule for Elsevier: an Elsevier API key is allowed. He wants the Elsevier API key and insttoken stored as GitHub secrets (his clicks; sessions never see them). Other API keys stay case by case on his word.

## How greg wants the coordinator to work
- One thread per handoff item, at most three at once; greg's own asks get their own thread.
- One project-chat line per landed PR, in product terms; a worker's bare clone listing each default branch's merge commits is the complete record. Auto-merge stalls on a PR behind main: merge main in.
- Relay greg's messages attached; corrections go to every thread told before. One owner per shared file; others hand changes over through the coordinator. A card tap can't be attached: attach his message and point the thread at the tap. A thread's permission check may refuse a rule change relayed from another thread: greg must say it in that thread.
- A usage-limit stop needs a send_later nudge at the reset. "Push and checkpoint": every thread pushes, writes "Checkpoint <date>" atop each open PR, replies and stops; one writes the handoff. "Stop all work" means nothing starts after the checkpoint.
- New spend (pilots, batches, runs) waits for his word and number. greg often does his steps without saying so: ALWAYS verify live state (run status, tags, settings) before listing any step as his; never re-list clicks he already did (he gets angry). He hates per-person manual steps: anything for collaborators must be self-serve.
- Repeatable setup is a button (SymphonyBoard site or Beethoven's extension) with as few manual settings as possible; App permissions, callback URLs and accepting them stay greg's clicks. Every settings change must be recorded and reproduced by Symphony Setup for new repos, including org-level settings when an org owner runs it (greg 2026-10-19).
- Control panel never scrolls (greg 2026-10-19): every tab fits the screen whole, zoom (pinch/wheel) instead of scroll, buttons sized to the screen, tap a chart node to focus it with its neighbours and swipe (control-panel-no-scroll).
- greg wants no forms on the control panel: every new thing uses the + tile style (like Tokens), every card has gear, X and click-for-status; panel sizes and text size saved in browser (site #60-62, 2026-10-18). He is "big into visuals": pretty and intuitive.

## Decisions
- Protocol: the library fix for every finding; correctness over cost; no deadlock, missed work or orphaned worker. Symphony's protocol over gh-aw; a gh-aw canary only after 0.5.0 (now out). Candidate A (Python compiler to YAML) + gh-aw canary pilot: plan in docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md; start only on greg's word.
- Experiments grow by strata, greg's choice each step. No coordination data in the grant or competitors doc until he has run the full suite and tried xblossom. Curse of coordination: no more research until greg understands why it exists (explaining it is allowed).
- No API key, including public browser keys (amended for Elsevier, see above).
- Future, on greg's word: a like template for Claude Cowork desktop projects. He values trackable history, shareability, visualization and extensibility.
- Outside code bases: no integration code until greg chooses (docs/research/outside-code-bases.md). 2026-10-19: greg chose the Mendeley app (OAuth secret would sit in the Worker); Word citations use Word's built-in sources (URL + DOI) plus Zotero fields; Mendeley for capture. He wants references traceable to their source.
- Control board: no bespoke graph code; Linear optional, never a dependency; no Jira or Zenhub. Mobile pass and a native iOS app proposal asked 2026-10-19.
- Claude tokens: a usage reading costs a tiny call only on Refresh or Run workflow, never scheduled. The panel may take a Claude token.
- Tokens (greg 2026-10-19): one setup token per person, owned by their GitHub login, not a repo. Add Token acts on the repo focused in the command board: mint via the Actions sign-in if they have none, else lend their existing one. Org repos: an org secret whose repository list is the lend list; personal repos: a repo secret, a second sign-in per repo. They lend and revoke any time; only they or the org owner change it. Org/enterprise members with write work; others Ask to join (site #77) or lend with no say via an issue on the org's public front repo (greg approved anyone-can-open-an-issue trigger 2026-10-19 02:54); a standing owner list says which private repos lent tokens serve; extension gets Lend/Ask buttons. Each repository assigns tokens to agents (review, development, testing); agents are importable, so Symphony is also an agent benchmark (coordbench, flowbench). Issues a token closes credit it and its owner on one leaderboard.
- Notebooks (greg 2026-10-19): like NotebookLM; groups of OneDrive files never moved, each a private repo (notebook.json, references.bib, research/, drafts/) where Claude works in the background and writes tracked edits back to OneDrive. notebooks.json shape fixed (tools/notebook.py, template #239 merged; five drafts on onedrive). Must switch to direct Graph access the day WSU consents, with one code base. Drive organizer owns data; Control panel sign-in owns the Notebooks view.
- 2026-10-19 20:55 (greg): Wayne State APPROVED SymphonyBoard connecting to OneDrive natively. Direct Graph switch is unblocked. Next: modernize the Explorer (modern look, takes most of the panel while in use, new features); planned in the 2026-10-19 handoff only, not built yet.
- Symphony Setup stays installed after an adoption, acting only during adoption runs (greg card 2026-10-19; symphony-start #69, privacy v29).
- Grid gate: the world-writable university folders are a note, not a refusal; no Grid page unless greg asks.
- Symphony Setup may hold organization Administration, only to let Actions create and approve PRs. SymphonyBoard may hold repository Administration, used only by the Share tab (a "make private" toggle would widen this: needs greg's word).
- Taxonomy parked (docs/checkpoints/2026-10-15b/taxonomy/).
- Session/cookie ride-along to OneDrive rejected; never build it.

## Owners and state
- Who owns what and where each workstream stood on 2026-10-19 03:00 UTC: [[project-state-2026-10-19]] (owners of the control panel, Folders/OneDrive, drive organizer, tokens, agents, website, grid, Chrome Web Store, Word documents).
- 2026-10-19 20:56: greg asked push and checkpoint; Control panel sign-in writes the project handoff for all threads.

## Waiting on greg
1. Grant: values; allowability; disclosure audit; Overleaf; IRB amendment (draft at /mnt/project-files/grant-irb/, never in git). Proposal was submitted Oct 16 (spine-program #119).
2. Tokens: delete hand-made SYMPHONY_CLAUDE_ACCOUNTS in coordbench if still there (#222 is closed).
3. Delete symphony-template symphony-locks/probe and hpcworker claude/grid-gate-scaffold (beethoven-extension claude/update-check is gone, checked 2026-10-19).
4. Which autonomous-software-agent repository he meant.
5. Grid: whether hpcworker's rule covers the grid key.
6. Control board: issue-type and Projects v2 clicks.
7. Word runs; drive project proposals go-ahead; Elsevier key, insttoken and Zotero key into GitHub secrets (and cloud environment).
8. Curse of coordination explanation.
9. Optional: Symphony Setup on symphony-start.
10. Agents: unbuilt options; his word for any benchmark run; student-pooling decision card.
11. (Done 2026-10-19: WSU approved SymphonyBoard OneDrive access.)
12. spine-program #198 (CAMS-Knee licence) and #199 (CathAction form) are his.
13. Go-ahead for the YAML compiler (Candidate A) / gh-aw canary.

## The grant (AIDaS seed 2027, spine-program)
Read the aidas-grant memory and RECORD.md in 01_carm_level_detection/grants/aidas_2027/ before any grant work. Critical: Dr. Han's edits word for word, changes only as greg asks; never name SchwingNet, FluoroCap or XRSpinoPelvic1K, never "provenance"; never raise data permission, directive D1 or IRB scope (HPR 2026-269); contacts.tex, the two biosketch PDFs and the IRB form never go in git; Elsevier insttoken and API key stay server-side and private, never in git, browser code or a URL, and Elsevier text is never made public; no model is trained on Elsevier content.
- 2026-10-19 (greg): the WSU library AND Elsevier itself confirmed Claude may read Elsevier text for academic use as long as the token and text are not made public. Recorded in spine-program (#209). Training on it stays off.
- 2026-10-18: Elsevier granted ScienceDirect and Scopus. Program folder 13_aidas_program merged (spine-program #183): goal #121, ten epics, 50 tasks, Ashley's labelled. 21 fluoroscopy video datasets are issues #186-#206 under epic #185 (plan PR #207).
