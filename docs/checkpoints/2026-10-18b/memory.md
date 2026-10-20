Compressed 2026-10-18 from memory-full.md beside this file (symphony-template docs/checkpoints/2026-10-18/); a PR or newer checkpoint wins. History lives in git and the handoff.

## Project and environment
- Owner and only member: greg (GitHub Gregory-Schwing-MD-PhD), organization OpenSpineConsortium. He dictates; expect sound-alikes ("ADIS" = AIDaS, "Warren" = Loren).
- symphony-template is home: handoffs in docs/checkpoints/<date><letter>/, findings in docs/research/ with a README line. Main needs a branch up to date with main and a green "check"; merge commits; head branches auto-deleted.
- Repositories: symphony-protocol(-canary), coordbench, flowbench, symphony-app, symphony-start, symphony-extension, symphony-marketplace, spine-program (grant), beethoven-* (greg's proprietary), openspineconsortium.github.io (site), hpcworker (grid).
- Sessions can't delete branches, approve deployments, publish releases or see secrets; gh GraphQL is blocked, REST works; other repositories need add_repo first. list_project_prs is incomplete.
- Connectors: Claude Docs, Microsoft 365 (WSU Outlook), Google Drive; no Gmail, so mail is a draft greg sends. greg's PC only through the desktop app's folder access.
- WebFetch can't reach github.com, docs.github.com, arXiv or Hugging Face: use raw.githubusercontent.com, a clone or WebSearch.
- Containers restart: push before long steps. Several accounts push to the same branches: read a PR's commits first. A new repository's first commit is greg's.
- Topic memories: aidas-grant, experiments, control-board-graph-research, control-panel-signin, native-git-locks, curse-of-coordination-hold, beyond-cooperation-step-4 (copies in topic-memories/).

## greg's standing rules (verbatim)
One pull request per change, from the thread's own branch. Run bash scripts/check.sh first where the repository has it. Run an adversarial review before each substantive pull request. Merge once green, on my standing permission. Never approve, publish or change a symphony-protocol release or its approval gate without my own words. Never push to or force-push a default branch. No API key and no Claude credential anywhere. If something you need is missing, say exactly what in your first message and stop. Ask me before anything marked mine. Every manual step you give me needs its exact link and what to click.
Also: merge commits with the head sha from git; bring main in by merging, never rebase. Briefs say to commit findings under docs/research/ with a README line and to number manual steps in the reply's own text with exact links. No adversarial reviews on spine-program; keep the second review round on protocol fixes. When greg is low on usage he says to skip adversarial review; obey.

## How greg wants the coordinator to work
- One thread per handoff item, at most three at once; greg's own asks get their own thread.
- One project-chat line per landed PR, in product terms; a worker's bare clone listing each default branch's merge commits is the complete record. Auto-merge stalls on a PR behind main: merge main in.
- Relay greg's messages attached; corrections go to every thread told before. One owner per shared file; others hand changes over through the coordinator. A card tap can't be attached: attach his message and point the thread at the tap.
- A usage-limit stop needs a send_later nudge at the reset. "Push and checkpoint": every thread pushes, writes "Checkpoint <date>" atop each open PR, replies and stops; one writes the handoff. "Stop all work" means nothing starts after the checkpoint.
- New spend (pilots, batches, runs) waits for his word and number. greg often does his steps without saying so: check before calling one open.
- Repeatable setup is a button (SymphonyBoard site or Beethoven's extension) with as few manual settings as possible; App permissions, callback URLs and accepting them stay greg's clicks.
- greg wants no forms on the control panel: every new thing uses the + tile style (like Tokens), every card has gear, X and click-for-status; panel sizes and text size saved in browser (site #60-62, 2026-10-18).

## Decisions
- Protocol: the library fix for every finding; correctness over cost; no deadlock, missed work or orphaned worker. Symphony's protocol over gh-aw; a gh-aw canary only after 0.5.0.
- Experiments grow by strata, greg's choice each step. No coordination data in the grant or competitors doc until he has run the full suite and tried xblossom. Curse of coordination: no more research until greg understands why it exists (explaining it is allowed).
- No API key, including public browser keys.
- Future, on greg's word: a like template for Claude Cowork desktop projects. He values trackable history, shareability, visualization and extensibility.
- Outside code bases: no integration code until greg chooses (docs/research/outside-code-bases.md).
- Control board: no bespoke graph code; Linear optional, never a dependency; no Jira or Zenhub.
- Claude tokens: a usage reading costs a tiny call only on Refresh or Run workflow, never scheduled. The panel may take a Claude token.
- Tokens: each belongs to a GitHub login and they accumulate across an organization; only its owner (or the organization owner) enables, disables, adds or removes it. Each repository assigns tokens to agents (review, development, testing); agents are importable, so Symphony is also an agent benchmark (coordbench, flowbench). Issues a token closes credit it and its owner on one leaderboard.
- Grid gate: the world-writable university folders are a note, not a refusal; no Grid page unless greg asks.
- Symphony Setup may hold organization Administration, only to let Actions create and approve PRs. SymphonyBoard may hold repository Administration, used only by the Share tab.
- Taxonomy parked (docs/checkpoints/2026-10-15b/taxonomy/).

## Owners and state, 2026-10-18 (evening)
- symphony-protocol: 0.4.1 latest approved; 0.5.0 merged, waiting for greg's approval; F22-F31 merged (F29 #53 at f6ac177; over-refusal fuzz done). F32 (#54, push handed to another shell as text) nearly merged; mutants job timeout raised to 45 min. After 0.5.0 is published: vendor into template, move guard to library full check, rulesets "check" app question, raise to 0.5.1. #45 and #51 drafts until 0.5.1. Thread: Protocol fixes toward 0.5.1.
- Control panel: Control panel UI overhaul thread did layout/+style/repo picker/Share (site #60-62, privacy v20, v22). Control panel sign-in owns sign-in, Worker, symphony-app checks/manifests, privacy versions (next 24), Dependencies (v19), Folders (v21) and the File Explorer-style Folders (site #63, v23; double-click opens in Office); now building a zoomable Explore tab (goal>epic>issue>PR>worker runs>Claude logs).
- Folders/OneDrive: Entra app "SymphonyBoard Folders" client id 463afc21-8bbd-429b-a93d-3d3617966f0b (multi-tenant + personal); Worker vars MICROSOFT_CLIENT_ID/SECRET in Cloudflare. Connect works with greg's personal Microsoft account. greg is NOT a WSU admin: WSU accounts still need C&IT admin consent (he may have filed the in-screen approval request). greg already uses OneDrive through Claude's Microsoft 365 connector and asked what can be built under WSU's approval of Claude.
- Drive organizer thread (started 2026-10-18): symphony-template#221, drive-organize.yml (catalog | organize | accept, dispatch only, private repos only); drive-catalog branch holds catalog.json; projects are epic+drive+project:<slug> issues. First real run waits for greg's word. OneDrive sync bugs fixed in #216.
- Add token fixes thread (started 2026-10-18): Tokens page and token.yml (Symphony beyond cooperation thread not running). Ashley (aschehr/OpenSpineToolbox-S1fix-2Dprojection) needs her adoption PR merged first; greg's Add token stuck disabled while polling; token.yml runs 1-6 failed "claude printed no token after the code".
- Claude tokens (tools/pool.py, tools/token_run.py, workers.yml): organization secrets SYMPHONY_CLAUDE_1-32 and CLAUDE_CODE_OAUTH_TOKEN, renew by 2027-10-17. TILE_MODELS in symphony-panel.js must equal KNOWN_MODELS in tools/pool.py.
- Agents: .claude/agents/ (reviewer, developer, tester); importing opens a PR; nothing spends until run.
- Every signed-in page must be a SymphonyBoard Callback URL. The Apps' privacy statement (symphony-start PRIVACY.md) goes live before a feature ships; next version after main's.
- Website: Website docs and navigation owns SITE in tools/build_site.py; no scheduled rebuild.
- Grid (hpcworker): runner chain stopped; grid.yml restarts it.
- Chrome Web Store: every merge to an extension repo's main is a store submission.
- Word documents: tools/docx_review.py; never overwrite a file greg changed.
- Experiments: nothing runs without greg's word and number.

## Waiting on greg
1. Approve 0.5.0: https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117 ("Review deployments", tick "release", "Approve and deploy").
2. Grant: final PDF to Han and Schwiebert and aidas@wayne.edu; values; allowability; disclosure audit; Overleaf.
3. Tokens: delete hand-made SYMPHONY_CLAUDE_ACCOUNTS in coordbench; close symphony-template#222.
4. Delete beethoven-extension claude/update-check, symphony-template symphony-locks/probe, hpcworker claude/grid-gate-scaffold.
5. Which autonomous-software-agent repository he meant.
6. Until 0.5.0 is out, Monday's "Vendor symphony-protocol 0.4.1" opens red: greg closes it.
7. Grid: whether hpcworker's rule covers the grid key.
8. Control board: issue-type and Projects v2 clicks.
9. His word for real drive organizer / Word runs.
10. Curse of coordination explanation.
11. Optional: Symphony Setup on symphony-start.
12. Agents: unbuilt options; his word for any benchmark run.
13. WSU C&IT admin consent for SymphonyBoard Folders.

## The grant (AIDaS seed 2027, spine-program)
Read the aidas-grant memory and RECORD.md in 01_carm_level_detection/grants/aidas_2027/ before any grant work. Critical: Dr. Han's edits word for word, changes only as greg asks; never name SchwingNet, FluoroCap or XRSpinoPelvic1K, never "provenance"; never raise data permission, directive D1 or IRB scope (HPR 2026-269); contacts.tex, the two biosketch PDFs and the IRB form never go in git; Elsevier content never trains a model or reaches an outside AI service; literature questions go to a grid-hosted model, never Claude.
