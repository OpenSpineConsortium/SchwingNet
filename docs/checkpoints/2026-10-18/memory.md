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

## Decisions
- Protocol: the library fix for every finding; correctness over cost; no deadlock, missed work or orphaned worker. Symphony's protocol over gh-aw; a gh-aw canary only after 0.5.0.
- Experiments grow by strata, greg's choice each step. No coordination data in the grant or competitors doc until he has run the full suite and tried xblossom. Curse of coordination: no more research until greg understands why it exists (explaining it is allowed).
- No API key, including public browser keys.
- Future, on greg's word: a like template for Claude Cowork desktop projects. He values trackable history, shareability, visualization and extensibility.
- Outside code bases: no integration code until greg chooses (docs/research/outside-code-bases.md).
- Control board: no bespoke graph code; Linear optional, never a dependency; no Jira or Zenhub.
- Claude tokens: a usage reading costs a tiny call only on Refresh or Run workflow, never scheduled. The panel may take a Claude token.
- Tokens: each belongs to a GitHub login and they accumulate across an organization; only its owner (or the organization owner) enables, disables, adds or removes it. The Tokens tab holds only the tiles and one way to add. Each repository assigns tokens to agents (review, development, testing); agents are importable, so Symphony is also an agent benchmark (coordbench, flowbench). Issues a token closes credit it and its owner on one leaderboard.
- Grid gate: the world-writable university folders are a note, not a refusal; no Grid page unless greg asks.
- Symphony Setup may hold organization Administration, only to let Actions create and approve PRs. SymphonyBoard may hold repository Administration, used only by the Share tab's Invite.
- Site look: only the top bar shows, each tab's pages drop down on hover; the console fills the height under it. Built: Tasks board, Pull requests, Runs and Workers cards, flashing message line, full screen, per-token gear and side panel, frozen Ask Claude bar whose answers offer panel actions as buttons he presses under his sign-in.
- Taxonomy parked (docs/checkpoints/2026-10-15b/taxonomy/).

## Owners and state, 2026-10-18
- symphony-protocol: 0.4.1 is the latest approved release; 0.5.0 merged, waiting for greg's approval; F22-F28, F30, F31 merged; F29 (#53) ready, needs CI green and a hand merge (auto-merge off there). Next, each its own PR: guard misses (`git push origin $'main'`, `git pu$(true)sh origin main`, here-documents). After 0.5.0 is published: vendor it into the template, move the guard onto the library's full check, check whether the rulesets' "check" must name its app, raise to 0.5.1. #45 (locks) and #51 (Dependencies) stay drafts until 0.5.1.
- Claude tokens (thread Symphony beyond cooperation; tools/pool.py, tools/token_run.py, workers.yml's token steps, assignment, leaderboard): organization secrets SYMPHONY_CLAUDE_1-32 and CLAUDE_CODE_OAUTH_TOKEN ("main"), renew by 2027-10-17. Add a Claude account mints on an Actions runner. TILE_MODELS in symphony-panel.js must equal KNOWN_MODELS in tools/pool.py. Fable's limit comes only from cswap on greg's PC.
- Agents: Claude Code agent files in .claude/agents/ (reviewer, developer, tester); importing opens a PR; accounts.json "workers" maps agents to token slots per repository; benchmark credit keys on agent_file.sha256 (coordbench) and as_agent (flowbench). Nothing spends until an agent is run.
- Control panel https://openspineconsortium.com/symphony/control/ is one console; a new section is one rail button and one panel. Owners: Control panel redesign owns layout, frame and each tab's look; Control panel sign-in owns the sign-in and its Worker (https://symphony-signin.openspineconsortium.workers.dev, secrets only in Cloudflare), what each section does, symphony-app's checks and manifests, and the Dependencies (site #36) and Folders (site #37) tabs; Ask Claude bar owns the assistant (claude.yml's assistant steps, .github/symphony/assistant.md, the Ask tab, #cp-askbar). Every signed-in page must be a SymphonyBoard Callback URL.
- Sharing: the Share tab takes a username or email and a role; with a username Invite sends GitHub's invitation once greg grants SymphonyBoard repository Administration; otherwise it opens Add people and drafts the note.
- The Apps' privacy statement (symphony-start PRIVACY.md) lists all they hold and goes live before a feature ships; symphony-app manifests match it. Each new feature takes the next version after main's when it merges, tells the coordinator and rebuilds the site.
- New users: Symphony Setup makes every per-repository setting; per organization: the Claude token and App, Codespaces, optional issue types and Projects.
- Website (public: nothing from spine-program, nothing of Beethoven's beyond what it shows): Website docs and navigation owns SITE in tools/build_site.py, the header and https://openspineconsortium.com/docs/; no scheduled rebuild. A new page's thread adds its SITE line. Competitor comparison owns docs/research/symphony-versus-competitors.md, compare.html, use-cases.html.
- Grid (hpcworker; /mnt/project-files/grid/your-grid-steps.md): one ssh gate key starts, checks and stops the runner chain, now stopped; grid.yml's "Start the runner chain first" restarts it.
- Chrome Web Store: CWS_ON_PUSH is publish, so every merge to an extension repository's main is a store submission. Symphony extension: https://chromewebstore.google.com/detail/symphony/hfljomhibljegapnfiglenfolnmpopoi; needs repository secret CWS_ITEM_ID (greg says set).
- Word documents: tools/docx_review.py turns comments into tasks and edits into tracked changes; never overwrite a file greg changed; a merged revision goes up to the drive at once. OneDrive first; Google Drive waits for a keyless route.
- Experiments: see the experiments memory; nothing runs without greg's word and number.

## Waiting on greg
1. Approve 0.5.0: https://github.com/OpenSpineConsortium/symphony-protocol/actions/runs/38889703117 ("Review deployments", tick "release", "Approve and deploy").
2. Grant: attach the final PDF to his Outlook draft to Han and Schwiebert and send it, and to the aidas@wayne.edu submission; real values for the approximations; allowability (B, C3, D, F); the disclosure audit (rule 8); Overleaf.
3. Tokens: retry + Add Token; delete any hand-made SYMPHONY_CLAUDE_ACCOUNTS in coordbench; the Tokens thread's card on an org App for members' changes.
4. Delete beethoven-extension's branch claude/update-check, symphony-template's symphony-locks/probe, hpcworker's claude/grid-gate-scaffold.
5. Which autonomous-software-agent repository he meant.
6. Until 0.5.0 is out, Monday's "Vendor symphony-protocol 0.4.1" opens red: greg closes it; don't fix it.
7. Grid: whether hpcworker's rule on "a token held as a secret" covers the grid key.
8. Control board: issue-type and Projects v2 clicks; Linear; graph hosting.
9. Word: the Microsoft Entra app registration clicks once the Folders tab exists; his word for real runs.
10. Curse of coordination: whether the explanation answers why it exists.
11. Optional: install Symphony Setup on symphony-start only.
12. Share: SymphonyBoard's repository Administration permission clicks.
13. Agents, unbuilt options: other runtimes; importing a folder or plugin's agents; an agents leaderboard; his word for any benchmark run.

## The grant (AIDaS seed 2027, spine-program)
Read the aidas-grant memory and RECORD.md in 01_carm_level_detection/grants/aidas_2027/ before any grant work. Critical: Dr. Han's edits word for word, changes only as greg asks; never name SchwingNet, FluoroCap or XRSpinoPelvic1K, never "provenance"; never raise data permission, directive D1 or IRB scope (HPR 2026-269); contacts.tex, the two biosketch PDFs and the IRB form never go in git; Elsevier content never trains a model or reaches an outside AI service; literature questions go to a grid-hosted model, never Claude.
