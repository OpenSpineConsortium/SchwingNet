# Plan: finishing Symphony

Written 2026-10-13, at the end of the night's session, and brought up to date that afternoon at the handoff, for you and for the next session (Fable or any other). It replaces the plan of 2026-10-12 and folds in the night's designs: the public runtime, the QA gate, the validation harness, the account pool, CooperBench, fewer moving parts and spine-program. Repositories go by their GitHub names; local checkouts and the GitHub tools still use the old sdlc-* names. A session merges any pull request once its checks are green, on your standing permission in perpetuity (2026-10-13), spine-program's too while Symphony is in its development phase; approving a release stays yours, since no session can.

## 1. The answer in one paragraph

Symphony is close to a product others can rely on, and tonight closed the gap that mattered most: a new copy now passes its own required check on day one, a protocol-only adoption brings everything its workflows run, and the plugin works in a protocol-only repository such as spine-program. What remains is mostly structure, not features. One public, versioned runtime (symphony-protocol, renamed `symphony`) holds all of Symphony's logic, and every copy calls it through a few small files, so a copy can never fall behind and setup shrinks to callers and settings. A required `qa` check, run from the default branch, gives every agent's pull request a report. The validation harness holds the protocol to its spec on every change. Your accounts become one pool the runs spread over, and CooperBench measures the result. You do not need a program of your own to drive your accounts: each repository's own GitHub Actions run its workers.

## 2. What landed tonight, and what is in flight

Merged (each green on its own check):

- symphony-marketplace#10, plugin 0.1.7: the skills name only files every adoption has, or say what to do where the repository lacks them; the push guard now refuses a push when it cannot run (the Windows Store's python3 stub made it pass every push), from spine-program's handoff.
- symphony-start#37: a protocol-only adoption brings every module its workflows' scripts import (since symphony-template#57 every protocol-only metrics run died at `import economics`); a workflow that needs the library stays out with it; the metrics workflow comes only with its switch; an earlier adoption is repaired by asking again.
- symphony-template#60: a copy passes its own check (two prompt tests and three usage tests held only for the template, so every copy since #56 was red); off in either metrics switch file turns sharing off. symphony-template#61: a copy in crowd mode passes too. tests/test_filled_copy.py now makes three copies and runs their checks.
- Earlier today: symphony-start#36 and symphony-template#59 (the Actions box), the privacy statement version 4 (site#13).

Also merged since: symphony-start#38 (the form adopts a repository once and never turns an opt-out on; privacy statement version 5), site#14 (its page), symphony-protocol#10 (the validation harness's design and prototype, under validation/), symphony-protocol#12 (decision 5: each release waits for your approval in the environment release, and the sync carries only a published release, from the commit that raised main to its version) and symphony-protocol#11 (0.4.1: F1, F3, F5, F6, F10 and F11 fixed, each reproduced first, in two rounds with three reviews each). You approved v0.4.1 on 2026-10-13 at 13:39 UTC, the first release through the gate, and its sync landed in all four consumers the same minutes: symphony-template#64, symphony-marketplace#13 (the plugin to 0.1.10), symphony-app#12 and coordbench#10. symphony-template#62 and symphony-marketplace#11 (plugin 0.1.9) made the claim and checkpoint skills push the branch by name, made with --no-track, since a git with push.default=upstream sent the claim commit to main; #62 also bounded the usage reader's digits; symphony-template#63 and symphony-marketplace#12 made the skill tests steady against git's background maintenance.

In flight: nothing. What comes next is Phase 1 below, starting with the template's follow-up for 0.4.1 (HANDOFF.md lists its files).

## 3. Your decisions

Recorded on 2026-10-13 and not asked again: fresh test repositories, with the update route for older copies parked (the runtime replaces it); the Actions box ticked by Symphony Setup in whole-template adoptions; workers and the coordinator in protocol-only adoptions too, on the repository's own tests; a default worker in every adoption with an opt-out box; the panel as a site page plus a small stateless Cloudflare sign-in service; one token for many Symphony repositories as an organization secret (never Beethoven's); the plugin to Anthropic's directory after the fresh test; the four borrowed pieces (workers ask instead of guessing, no unreviewed agent change to .github/workflows/, Anthropic's Code Review as an option, recipes later); a QA report on every agent's change; few moving parts; a validation harness with concolic testing, its findings fixed; your accounts as one pool, then CooperBench; and the open core: the runtime, the protocol and the plugin public, the hosted parts (panel, account pool and switching, QA reports, analytics) a paid App, the template's private status no longer a moat.

Accepted on 2026-10-13 as recommended, with one caveat on question 3: the separate account is advice, never enforced, since some people have only one Claude account, whose workers then share its window with its owner. Question 5 applies from 0.4.1, whose release you approved the same day. Later that day you allowed releases without your approval for the development phase; no session can approve or publish one (the approval needs deployments: write, which a session's token lacks, and the cloud proxy refuses a session's release), so each release still waits for your click until you tell a session, in your own words, to switch the approval off in release.yml. That change can merge only while no release is waiting, since GitHub refuses GITHUB_TOKEN a tag at a commit whose workflow files differ from main's.

1. **Who may queue work for a worker?** Recommended: only people with write access; the coordinator's tasks from an epic you marked keep todo, and its tidy's proposals wait for you. Why: the Task form adds todo for anyone, and the next run works it on your plan. Blocks Phase 3.
2. **Should GitHub stop a worker changing what steers workers** (its file, the prompts, .claude/, tools/, scripts/, .github/)? Recommended: yes, by the `qa` check run from the default branch's copy, and by code-owner review on those paths (question 7). Why: today's check runs the pull request's own scripts/check.sh, and the Claude App holds Workflows write. Blocks Phase 3.
3. **Whose token goes into the organization secret?** Recommended: an account you never use by hand. Why: the workers share its five-hour window. Blocks Phase 2, step 5.
4. **What caps spending?** Recommended: 10 Claude runs a day per repository, coordinator included, set by a repository variable; none while the default branch is red or after three failures in a row. Why: each six-hourly run or queued issue can start six 90-minute runs. Blocks Phase 3.
5. **Should each release of symphony-protocol, later of the runtime, wait for your OK?** Recommended: yes, through a release environment you approve in the browser. Why: a release reaches every copy, and today no person reviews it. Applies now.

Answer when the phase starts:

6. (Phase 4) **The runtime's licence and what is public.** Recommended: the runtime public under MIT, the terms copies already get, in OpenSpineConsortium/symphony; the template repository's history, issues and research stay private; publish releases, not development branches; a lawyer's read before any source-available licence for later versions. Why: the service, the upkeep and the name are what sell, and copies already hold the runtime's files under MIT.
7. (Phase 4) **How copies follow releases.** Recommended: background jobs (board, tidy, metrics) follow the moving tag `v1`; the required check, the hooks on people's machines and every job that holds a Claude token run a reviewed pin, `.github/symphony/copy.json`, which a reviewed pull request moves; code-owner review on the paths Symphony manages (.claude/, scripts/symphony.sh, .github/), which changes "the rulesets require no review" for those paths only. Why: the design's critique showed a bad release on a moving tag could write a persistent bootstrap into every copy and instruct every session; a pin bounds it.
8. (Phase 4) **Fewer moving parts.** Delete symphony-app's webhook stage and SymphonyBoard's unused Checks permission and events; retire the sweep once installs reliably reach the form; keep a private canary repository adopted daily and worked weekly on your token. Recommended: yes. Why: parts that are off still have to keep working, and the canary notices what breaks.
9. (Phase 5) **Tick the Actions box in protocol-only adoptions too?** Recommended: no. Why: with several writers it lets any workflow approve what a person should review.
10. (Phase 6) **Code scanning on private repositories.** Recommended: make the repositories workers change public where you can, since CodeQL, secret scanning, dependency review and unlimited runner minutes are free there; buy GitHub Code Security only where a repository must stay private. Why: the `qa` check folds in what the plan provides and says "not available here" otherwise.
11. (Phase 8) **Give SymphonyBoard Actions read and write, and narrow its organization installation to the Symphony repositories?** Recommended: yes; never Secrets, Variables or Administration.
12. (Phase 10) **Which repositories may the pool reach?** Recommended: private or internal Symphony repositories where you are the one writer and a push ruleset keeps .github/workflows/ to you; never a public, crowd or Beethoven repository; and your orchestrator decision covers it. Re-read Anthropic's Usage Policy before 2026-11-12, when it adds "services that route requests through consumer subscriptions".
13. (Phase 10) **May coordbench#6's grid route run a self-hosted model through ANTHROPIC_BASE_URL?** Recommended: not yet (Beethoven's no-gateway rule binds your tooling there).
14. (Phase 11) **Pilot the claim protocol in beethoven-qa, Markdown only?** Recommended: yes, after Phase 3.

## 4. Your steps now

Each takes a minute or two; the links go straight to the page.

1. Limit RULESETS_TOKEN, an organization secret every repository sees, to the repositories whose rulesets.yml names it (beethoven-qa, beethoven-agents, beethoven-base), so no worker can read it: https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions, the secret, Repository access.
2. On the same page: if SDLC_APP_PRIVATE_KEY is an organization secret, limit it to symphony-start, symphony-protocol and symphony-app.
3. Delete the old test repositories, each under Settings, Danger Zone: OpenSpineConsortium/sdlc-template-test, sdlc-start-test and sdlc-setup-test; Gregory-Schwing-MD-PhD/test-non-org and Gregory-Schwing-MD-PhD/test. Phase 2 makes fresh ones.
4. Submit Symphony for Chrome (https://chrome.google.com/webstore/devconsole), then set the five CWS_ secrets and CWS_ON_PUSH at https://github.com/OpenSpineConsortium/symphony-extension/settings/secrets/actions.
5. Name the new setting ("lets GitHub Actions open pull requests") in Symphony Setup's description: https://github.com/organizations/OpenSpineConsortium/settings/apps/symphony-setup.
6. Delete the merged branches GitHub keeps: on https://github.com/OpenSpineConsortium/symphony-marketplace/branches claude/new-skill, claude/claim-worker-label, claude/protocol-only-plugin and symphony-protocol/sync; on https://github.com/OpenSpineConsortium/coordbench/branches symphony-protocol/sync; symphony-start keeps every merged claude/ branch. Simplest: tick "Automatically delete head branches" under Settings, General in symphony-start, symphony-protocol, symphony-marketplace and coordbench, then delete what is left from each Branches page. Leave claude/magical-shannon-ak167f and claude/festive-edison-al7xu2 until their sessions end.
7. Beethoven, as before: tag beethoven-qa with `gh release create v4.0.0 --repo OpenSpineConsortium/beethoven-qa --target 8f72ad3226cf9cddc7802fe904da980ef6371635` and then v5.0.0 at 85f0e1cee65b16dc31be2ad1bb5c3dd52732b589; Beethoven 20.0.0 to the store (the hand test's step 18, screenshots, the upload); beethoven-extension#9 is stale; beethoven-vscode#11 and #12 need their tests before your OK.
8. spine-program #72 is yours: the Claude GitHub App on the repository, Symphony Setup uninstalled there, each student invited with Write and their worker label made.
9. Each release of symphony-protocol: when GitHub emails "Deployment review requested", open the run, click Review deployments, tick release, then Approve and deploy; or tell a session in your own words to switch the approval off for the development phase.
10. Done on 2026-10-13: the Claude GitHub App on every repository of the organization; the version 5 privacy page (site#14); the environment release, with you as its required reviewer; and the approval of v0.4.1.

## 5. The work, in order

Phases 1 to 7 make the product others can rely on and test at scale; 8 and 9 add the panel and the listings; 10 and 11 your accounts and Beethoven. 8 and 10 can run beside 5 to 7.

### Phase 1. Finish tonight's fixes, then build the validation harness

- Done on 2026-10-13: the re-adoption guard (symphony-start#38) and its privacy page (site#14), and symphony-protocol 0.4.1, released and synced into all four consumers.
- The validation prototype found twelve things. Fixed in 0.4.1:
  - F6: one branch name (a superscript digit, or any non-ASCII name) stopped every board run in the repository; numbers are now ASCII digits only and every path segment is quoted.
  - F5: claude/03 and claude/3 both claimed issue 3; only the canonical name counts now.
  - F3: the push guard let through forced pushes written as `+branch`, bundled `-fu`, abbreviated `--al` and `--mirr`, `heads/main`, and any push behind `VAR=value`, `env`, `command`, `nice` or `time`.
  - F1: a release whose label removal failed was never completed; F10: a finished draft released by hand never took effect; F11: one refused comment failed the whole board run, so the board branch was not written.
- Left for you or the canary, none of them fixed: F2 (overlapping work told again when a claim opens its pull request; one more API call per run, or the notices move to the issue), F12 ("main moved" lost when the board's concurrency group cancels the run of a push to main; one API call per pull request per run), F4 (the clerk can deal one issue to two workers of one run; the claim lock still holds), F7 (a worker that has fetched can take another's claim with `--force-with-lease`; the guard can refuse it by reading the claim file before a lease push), F8 (idleness uses the committer date the pusher sets; the spec already says so), F9 (whether a draft ever hears "main moved"; one REST read of a live draft settles it).
- Next, before the harness: a recheck of the handoff's claims against GitHub's live state, which the owner left to the next session; then the template's follow-up for 0.4.1 (its texts on the claim branch's name, the release order and the guard's refusals, and the crowd audit reading claim names through the library), the marketplace README's list of refusals, symphony-app's test for the claude/03 verdict, symphony-protocol's README made to agree with its CLAUDE.md on who merges the gate's files, and the plan ladder memory brought up to the free-or-paid table (HANDOFF.md lists each).
- Then the harness itself, in symphony-protocol under validation/, as validation/DESIGN.md lays out: scripted workers in the library's memory and git worlds; a breadth-first checker over every interleaving of two or three workers to a set depth, with a sound state key and replayable shortest counterexamples; an oracle written from the spec's own text, never from the code under test; effects compared run by run, and "a board run never raises"; a mutation lane as its acceptance test (the critique's mutants slipped past the prototype until waits of 24 and 25 hours and effect checks were added); the fast lane inside the required check, under 60 seconds; the deep lane weekly; the concolic lane as assert-shaped properties run by hand from a scratch virtual environment, so no new dependency enters CI.

Done when: every fix is released and synced, the harness's fast lane runs in symphony-protocol's check, and its report names each guarantee with its status.

### Phase 2. The fresh test, first pass

Today's product as a new user meets it; Phase 7 repeats it. First `gh auth switch --user Gregory-Schwing-MD-PhD` (the other login caused "Repository not found"); in Claude Code, `/plugin marketplace add OpenSpineConsortium/symphony-marketplace` and `/plugin install symphony@symphony-marketplace`.

1. Organization, whole template: `/symphony:new OpenSpineConsortium/<name>`, adding the repository to Symphony Setup's list under Configure at https://github.com/organizations/OpenSpineConsortium/settings/installations rather than through the skill's link (which would replace the list); press Create on the form, keeping its defaults; take the repository off the list afterwards.
2. Organization, existing code: import a small project with tests (https://github.com/new/import), private; adopt it the same way.
3. Personal account: https://github.com/new, private, with a README; adopt it.
4. The whole-template repository: the Claude GitHub App and the token (question 3), two workers by the "Add a worker" form, two small queued issues, one epic.

Private repositories only until Phase 3; watch every run. Results go into one issue on symphony-template and an issue per failure. Measure: two workers on one token, a usage-limit stop, the guard and the cost hook in Actions, a Task-form issue waking workers, an idle run's minutes, the cost artifact, the board's release and overlap comments, and on Windows the plugin's session-start fetch (cut at ten seconds, which Windows' DNS stall exceeds).

### Phase 3. Rails before any worker runs unattended

Needs questions 1, 2 and 4; each line gets a test.

- **The front door's keys apart from template code (do first):** adopt-run.yml runs template code in the one job that names both Apps' private keys; stage the files in a job that names no secret and hand the tree over as an artifact.
- **Only writers queue:** crowd mode's queue gate runs wherever an Actions worker is registered.
- **No worker changes what steers it:** question 2's check and code-owner review; both required checks pinned to GitHub Actions (integration 15368), since the Claude App can write check runs.
- **No push to another worker's branch:** the guard reads the claim file before a lease push (F7).
- **Text is data:** the prompts say so and heed only writers; the board shows a fork's pull request by number.
- **Safe landing:** a thin issue leaves the queue with the worker's questions; main comes in by merge; auto-merge is armed, never `gh pr merge --auto` where nothing is required (it merges at once there).
- **The token harder to reach:** CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 and the sandbox on every Claude job; no Bash(python3:*) for workers.
- **Caps and a pause:** question 4; "Disable workflow" on workers.yml and coordinator.yml as the pause.

Done when every test passes and a drill passes on a private organization repository and a private personal one.

### Phase 4. One public runtime that copies call

The night's design (sent beside this plan) in brief:

- symphony-protocol, already public, renamed OpenSpineConsortium/symphony (your step: the proxy refuses renames). It publishes a dispatcher, `symphony.yml`, with reusable workflows behind it, and one composite action, `run`, with commands; everything runs on the runner's python3 and the standard library.
- A whole-template copy shrinks from 145 files and 28,436 lines to 38 files and about 1,070; a protocol-only copy from 28 files to 8. What a copy runs of its own: three thin workflow files and a small bootstrap for the hooks. The text Claude reads (PROTOCOL.md, skills, rules, prompts) stays in the copy and a text sync keeps it current by pull request.
- Gone: vendoring into copies, protocol.yml, template-init in copies, the parked update route, the sync's pull request into the template, the front door's private read, two protocol texts becoming one, and the whole class of drift bug fixed tonight.
- Releases: an immutable `vX.Y.Z` and the moving `v1`, created only through a release environment you approve; question 7 decides what follows `v1`.
- Measure first, in a one-day spike with a toy runtime on a branch of the public library, called from an internal, a public personal and a private personal repository: whether claude-code-action's token exchange accepts a job defined in another repository's reusable workflow (if it refuses, the action reports success and does nothing, so the Claude jobs stay out of v1 until this is answered); nested permissions (a central job may not ask for more than its caller grants, so one dispatcher per caller shape); `$/` across owners; Dependabot's update of a pinned commit; two runs named `check` on one head.
- Migration: canaries on `@main`, v1.0.0, the template itself becomes a copy and the permanent canary, the front door reads the public release and gains an Upgrade kind, existing copies move by `migrate` (it removes a file only when its bytes match a known release, and keeps and names every edited one), spine-program first among them (section 7).

Done when a fresh adoption holds only callers and settings, passes its check, and takes a new release with none of its files changing.

### Phase 5. Workers for existing code, and the default worker

After Phases 3 and 4. The check written once (the repository's test command and its CI job's name, read from the tree or filled in the adoption pull request) and read by the runtime, the prompts and the clerk in place of `bash scripts/check.sh`; the protocol-only ruleset requires it, pinned. The default worker, `.github/symphony/workers/helper.json`, label worker:helper, 40 turns and 2 runs in a row, landing when you merge; the form's opt-out box. Its pull request says what it is, what it needs, whose plan it spends, that it never merges and how to stop it. New adoptions get it only once Phase 6's check exists.

### Phase 6. A QA report on every agent's pull request

The night's research, simplified by its critique:

- Two required checks, both pinned to GitHub Actions: `check` (the repository's own tests, unchanged) and `qa`.
- `qa` runs from the default branch's copy (on workflow_run when the check finishes), reads the pull request only through the REST API and never runs its code, so a pull request cannot forge its own report.
- It fails on: added suppressions and skipped tests in any language (`noqa`, `nosec`, `type: ignore`, `eslint-disable`, `@ts-ignore`, `codeql[`, `lgtm[`, `t.Skip`, `@Disabled`, `#[ignore]`, `nolint`, `node:coverage` and the like); secret shapes in added lines; changes on a claude/ branch to .github/, scripts/check.sh, CODEOWNERS or linter configs; shell that fails `shellcheck --norc --severity=warning`; Python that does not compile; JavaScript that fails `node --check`; workflows that grant write at the top level or run a download without a digest check.
- It folds in GitHub's own results where they exist: CodeQL alerts on the pull request (and who dismissed one), the dependency graph's comparison, malware advisories for added packages. Each question answers pass, fail, or "not available here"; a tool that should have run and did not is a fail.
- One check run with notes at the lines, and one sticky comment.
- beethoven-qa stays the Python design-by-contract specialist in its own repositories (CrossHair, contracts, its standards), outside the generic gate.
- Precondition: workers must not push or open pull requests as an organization owner (owners can edit rulesets and dismiss alerts); a worker identity makes your merge a real review.

Done when a planted suppression or skipped test turns qa red with a note at its line, and a session's and a worker's pull request both carry the report.

### Phase 7. The launch test, then the plugin's listing

Phase 2 again on repositories made after Phase 6, then the plugin submitted to https://claude.com/docs/directory/publish.

### Phase 8. The control panel and its sign-in service

Needs Phase 3 and question 11. One Cloudflare Worker with no storage that adds SymphonyBoard's client secret to GitHub's sign-in exchange and returns the token; a site page that calls the GitHub API as you to show boards, workers and numbers and to queue, assign, add workers, run and pause. A privacy version first.

Later in the phase, the same Worker may answer GitHub's custom deployment protection rule, which a paid App would be listed for in the Marketplace: the Claude jobs run in an environment holding the Claude token, and the rule lets a job start only within the day's cap, the account pool's budget and a green default branch, so the token never reaches a job it refused and no edit to a workflow lifts the cap. It is in public preview; GitHub sends its event only to a webhook (no workflow can take it), so it needs that Worker; and it works on public repositories and, for private ones, only under GitHub Enterprise, so Phase 3's checks inside the workflows stay for everyone else.

### Phase 9. The Claude connector and its listing

After Phases 7 and 8: the Worker becomes Claude's sign-in server and an MCP server, with read tools and one write tool per act, marked destructive so Claude asks first.

### Phase 10. Your accounts: one pool, then CooperBench

After Phase 4, beside Phase 8; questions 12 and 13.

- **The pool:** an organization secret per account, SYMPHONY_CLAUDE_<NAME>, and a variable SYMPHONY_CLAUDE_ACCOUNTS naming them, on "Selected repositories". The template's new scripts/accounts.py, which you run and no session does, takes each token through gh's hidden prompt and never prints or keeps it.
- **The pick:** a library module, pure and clock-injected, reads each run's account record from the Actions cache (refused until the reset plus a minute, near the limit last, dead for six hours) and spreads parallel legs over the accounts in turn; with all out, the run waits and names the first reset. A called workflow, claude-session.yml, receives exactly one account's token. Measure first, with dummy secrets: whether a computed secret name works in a call's secrets mapping, and whether a run under the limits writes a rate-limit event.
- **CooperBench** in coordbench's own Actions on GitHub's runners, in an environment you approve: a free survey of which task pairs grade there, a token scrub before any real run (an agent that prints its environment would otherwise put a token in a public artifact), a pilot (pallets_click 2068, 66 sessions) to size the run, then the first benchmark (solo, coop, coop-git, team, sdlc; about 378 sessions over 42 pairs), pre-registered in bench/cooperbench/PLAN.md. 42 pairs detect only large gaps (about 26 to 30 points), so report intervals, not verdicts.

### Phase 11. Beethoven and Symphony

No Beethoven repository runs Symphony's code or holds a Claude token. beethoven-qa may pilot the claim protocol as Markdown only, by its own pull request through its gate, after Phase 3 and question 14.

## 6. How it stays working

The broad strokes, for the next session:

- **Guarantees come from what is enforced, not from what is written.** GitHub refuses the second push of a branch name, so the claim lock holds whatever an agent believes. Required checks pinned to GitHub Actions, rulesets and code-owner review are the second fence; the push guard is the first, and it now fails closed. Anything that only a prompt says is advice; anything that matters gets one of these.
- **A checked model, not a new language.** The risks here are logic and drift: a rule that misses a case, a copy that falls behind, a test that holds only in the template. Memory safety and speed are not the risks, so Rust or another language would buy nothing and would cost the property that every runner and every machine with Python 3.12 runs Symphony from readable source with no build and no dependency. The guarantee comes from the validation harness (every interleaving of a few workers, checked against the spec's own text, with mutants that prove the checks bite), from the filled-copy guard (the template's tests run in what a copy really is), and, for pure rules, from enumerated properties and CrossHair by hand. If a part ever needs more, make it a small pure core with contracts and prove it, as beethoven-qa does.
- **One source of truth, versioned.** The runtime in one public repository, released behind your approval, called by every copy; one protocol text; the canary on `@main` before a release moves.
- **Fewer moving parts.** No server of ours: the Apps only mint tokens, with webhooks off; the sweep retires once installs reach the form; every schedule is a fallback, never the only trigger.
- **Every check must have looked.** "Not applicable" is a verdict of its own; a tool that did not run is a fail; a skipped test is refused.

## 7. spine-program

- What it is: your private research repository, thirteen project folders, adopted with the protocol only on 2026-10-11 (pull request #1). Its library is 0.2.0 with no protocol.yml, so nothing updates it; its labels are account:main; it has no CI check, though its PROTOCOL.md describes one; the plugin is enabled there.
- Its rules hold for every session: changes only through the claim protocol (an issue labelled todo, the branch claude/<N>, a draft "Closes #N", the labels claimed and the account's label); never edit or push main; no project's research unless you ask (issues #17 to #42); gh and git fetch through WSL on Windows, the claim branch pushed from the Bash tool; no python or heavy find on the grid's login node; never the banned word, whole-number versions only, no student name or username in any file. Its rule that only you merge is set aside while Symphony is in its development phase (2026-10-13: "you can also push releases without my permission and spine program"): a session merges its pull requests once their checks are green, as everywhere else.
- Tonight: the plugin's skills now fit it and its guard fails closed (symphony-marketplace#10); its sessions get 0.1.7 when Claude Code next updates the plugin.
- Next: Phase 4's migrate moves it to the runtime first among existing copies. Its pull request must say what changes from 0.2.0: idle claims are released after a day with a comment, overlapping work is told, METRICS.json gains by_setting, economics and coordination, and its sessions get the push guard in the cloud for the first time. account:main keeps working, since the library reads it as a worker label. Until then it is safe as it is.

## 8. Risks

- **A bad release reaches every copy.** Bounded by the release gate, the canary, immutable tags, the pin for the check, the hooks and the Claude jobs (question 7), and code-owner review on managed paths.
- **The Apps' keys.** SymphonyBoard can push workflow files wherever it is installed; its key sits in three repositories; the front door runs template code beside both keys today (Phase 3, first item).
- **Spend.** Repositories on one account's token share its five-hour and weekly limits until the pool spreads them; idle runs cost minutes on private repositories.
- **Free private repositories** enforce no ruleset and cannot arm auto-merge; `gh pr merge --auto` merges at once there.
- **Terms.** From 2026-11-12 Anthropic's Usage Policy names services that route requests through consumer subscriptions. Symphony stays clear while each repository spends only its owner's tokens and the paid App starts nobody's runs; re-read it before charging anyone (https://www.anthropic.com/legal/aup).
- **Not yet measured:** Phase 2's list, Phase 4's spike, Phase 10's dummy-secret run, and how many outside copies exist (the proxy refuses the App's installation listing).

## 9. Where the detail is

- The runtime design and its critique (DESIGN-runtime.md), the QA gate research and its verification (DESIGN-qa-gate.md), and the account pool, CooperBench and fewer-moving-parts research (RESEARCH-scale.md): files of the handoff page, which .claude/session.md links, and sent to you.
- Which GitHub-native tools are free or paid on public and private repositories, per plan, with a quote for every cell: free-or-paid.md, beside them.
- The validation harness: validation/DESIGN.md and validation/prototype/ in symphony-protocol (merged in #10).
- The decisions and constraints: the checkpoint block of symphony-template's CLAUDE.md, word for word, and .claude/session.md beside it.
