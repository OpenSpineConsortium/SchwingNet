# The owner's to-do list, 2026-10-14 (brought up to date at 23:45 UTC)

This list was posted in the old Project at 19:41 UTC on 2026-10-14. The new account cannot open that post, so it is kept here whole, with every link and what to click, and brought up to date where the evening changed it (each such place says "Update, 23:45 UTC"). Nothing here is done by Claude: each item is the owner's own.

Files are in symphony-template unless another repository is named. "14c handoff" means docs/checkpoints/2026-10-14c/handoff.md, "housekeeping-steps.md" means docs/checkpoints/2026-10-14/housekeeping-steps.md, and "PLAN.md" means docs/checkpoints/2026-10-14/handoff-page/PLAN.md. Line numbers in symphony-template and spine-program files were counted by hand and may be off by one.

Two things are urgent:

1. The AIDaS grant, due Fri 2026-10-16 at 11:59 p.m. ET (item 1).
2. Adopting the canary, since the F8 fix waits on its check C5, which cannot run until the canary repository is adopted (item 2).

## Do now, most urgent first

### 1. Grant: values, office questions, audit

- Ask the PI (Zhizhong Han) and Co-PI (Loren Schwiebert) for every [DATA NEEDED] value: "ranks, department codes, contacts, AIDaS membership, New Investigator and NIH Early Stage Investigator status, the IRB number, the cohort size, the specimen count and imaging site, every placeholder fee and the fringe rate, the seat count, the solicitation numbers and dates, the OSTP citation, the F&A rule".
- The review adds: WSU's pay scale for the $15.00 hourly rate; the Claude seats' plan, price and purchase route; the Body Bequest Program's terms for releasing the specimen images; and a confirmation that "the PI is PI on no other AIDaS proposal this cycle".
- Update, 23:45 UTC: a grant thread has worked on the revision since 20:03 UTC, in spine-program's draft pull request #95 (https://github.com/OpenSpineConsortium/spine-program/pull/95, branch claude/94, head b1cc79d). It looked up on the web the values it could find, with a source for each, and recorded that both PIs are AIDaS-affiliated. Its checkpoint names what is now yours, in this order: (1) attach the two biosketch PDFs again in the new account's grant thread, since the new account cannot read the old Project's files; (2) send the allowability e-mail to aidas@wayne.edu, whose text is in 01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-14e.md on claude/94 (https://github.com/OpenSpineConsortium/spine-program/blob/claude/94/01_carm_level_detection/grants/aidas_2027/HANDOFF_2026-10-14e.md); (3) fill the eight [DATA NEEDED] items in RECORD.md section 3, in the same folder, among them tenure-track status, effort and the PI's role; (4) run the disclosure audit and decide what reviewers may see of Figure 3a; (5) submit by Fri 2026-10-16, 11:59 p.m. ET (item 11). Where that checkpoint and the older bullets of this item differ, the checkpoint is newer. The 2026-10-14 decisions on data (any and all data may be used; the VinDr and FluoroCap results stay in; rule 9 stays) are in memory.md, part "The grant".
- Email the AIDaS office today: "whether the cadaver lines (B1 to B5) and the FDA Pre-Submission line (D) are allowable". The review adds lines A and F, and whether DMC can be paid as a fee-for-service scan or WSU's own C-arm in Room 0312 Elliman is used instead. This matters: without B, D and F the total is $9,857, under the $10,000 floor.
- Do the disclosure audit (spine-program's CLAUDE.md rule 8). Releasing the agent and the benchmark under MIT is your call.
- Link: none at 19:41 UTC; this is email and office work. Update, 23:45 UTC: the grant thread gives the office's address, aidas@wayne.edu, and the e-mail's text, in the grant's HANDOFF_2026-10-14e.md (link above).
- Source: spine-program 01_carm_level_detection/grants/aidas_2027/README.md lines 3-4 and 29-40; REVIEW_2026-10-14.md lines 48-65 and items 10, 19, 20, 25, 26 and 33-36; HANDOFF_2026-10-14c.md lines 45-47; 14c handoff lines 130 and 149.

### 2. Adopt the canary repository

This also takes spine-program off Symphony Setup.

1. Quoted from the 14c handoff: "install Symphony Setup at https://github.com/apps/symphony-setup/installations/new, pick Only select repositories and symphony-protocol-canary, then press Create on the form it opens with "Do not share" ticked." Leave the form's other fields at their defaults (Kind Auto, Merge for me).
2. With Merge for me, the adoption's pull request should merge by itself. Once it has merged, uninstall Symphony Setup: open https://github.com/organizations/OpenSpineConsortium/settings/installations, find the row "Symphony Setup", press its Configure button, then the red Uninstall button.
3. Don't press Run workflow (https://github.com/OpenSpineConsortium/symphony-protocol/actions/workflows/canary.yml) until a thread tells you to. canary.yml takes a list of checks, so C5 can run alone when F8 needs it.

- The newer 14c instruction to uninstall Symphony Setup after the adoption merges replaces the older "Do not press the red Uninstall button" in housekeeping-steps.md.
- Picking "Only select repositories" on that install link replaces Symphony Setup's repository list, so spine-program drops off it. That finishes housekeeping step 1 and the Symphony Setup box on spine-program#72.
- SymphonyBoard's Actions read is already done.
- Why now: the F8 fix waits on canary check C5, and the canary does nothing until the repository is adopted.
- Source: 14c handoff line 136; docs/checkpoints/2026-10-14/HANDOFF.md line 34 (the form's defaults); housekeeping-steps.md lines 12-21; CLAUDE.md, Constraints (the install link replaces the list); docs/checkpoints/2026-10-14/protocol-fixes.md lines 46-48; symphony-protocol validation/DESIGN.md lines 692, 843 and 851.

### 3. CooperBench: set up the real run

Three settings, in this order, each quoted from the 14c handoff:

1. "environment bench in coordbench with the owner as required reviewer, Prevent self-review unticked and Deployment branches limited to main, at https://github.com/OpenSpineConsortium/coordbench/settings/environments". Clicks: "New environment, named bench"; then on the environment's page "Required reviewers ticked with the owner added, Prevent self-review left unticked since the owner both dispatches and approves, and Deployment branches and tags limited to main". If bench is already listed (a run can create it), click it and add only the reviewer.
2. "organization secrets SYMPHONY_CLAUDE_1, 2 and so on from `claude setup-token`, one per account, each with Repository access set to Selected repositories and coordbench ticked, at https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions". Run `claude setup-token` while signed in to each account. The button is "New organization secret" (inferred; the documents name no button).
3. "the coordbench variable SYMPHONY_CLAUDE_ACCOUNTS listing the slots in use, for example 1,2,3 (three accounts hold the 50 pairs under five arms in one dispatch), at https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions". The button is "New repository variable" (inferred). An older handoff pointed to the organization's variables page; the newer documents all say this repository page.

- Your decision: which accounts, and how many. The full list is 450 Claude runs, about $195 at API list prices, drawn from the plans' usage limits rather than billed, and it spans days and several usage windows. Three accounts run it in one dispatch; fewer take more dispatches.
- Use accounts you don't use by hand: a run draws on the same five-hour window as everything else on that account, including the Symphony work.
- Nothing runs or spends usage until you approve a real dispatch (item 8).
- Source: 14c handoff line 137; coordbench bench/cooperbench/README.md lines 173-176, 185-207 and 282-287; docs/checkpoints/2026-10-14/cooperbench-run.md lines 54-67; CLAUDE.md, Durable decisions (a token from an account nobody uses by hand).

### 4. spine-program

1. Tick "Allow GitHub Actions to create and approve pull requests": open https://github.com/OpenSpineConsortium/spine-program/settings/actions, scroll to "Workflow permissions", tick the box and press Save (the Save button is inferred). If the box is greyed out, the organisation's setting rules it: https://github.com/organizations/OpenSpineConsortium/settings/actions (same section). Best done before 0.5.0 ships, when the weekly Protocol run first needs it; without it, that run opens an issue with a one-press link instead, so nothing breaks.
2. From WSL in your laptop clone: `git pull`, then `_ops/ship_archive.sh` once. Then check that FILE_COUNT.txt in the archive reads 4379 and tick the last acceptance line of issue #87 (https://github.com/OpenSpineConsortium/spine-program/issues/87, link inferred from the number).
3. Try the student route once: "a Project linked to this repository, `/board`, then the README's paste prompt on one issue labelled todo". Then tick that box on https://github.com/OpenSpineConsortium/spine-program/issues/72
4. Answer the open comment on the onboarding document, which asks whether Beethoven alone is the grid route: https://claude.ai/code/artifact/f730cf94-98ba-4c18-b185-eebb9255659d (an artifact of the old account; open it signed in to that account).

- Source: housekeeping-steps.md lines 130-134; spine-program issue #72; the checkpoint comment https://github.com/OpenSpineConsortium/spine-program/pull/88#issuecomment-6158960359

### 5. Housekeeping

**a. Limit the organization secrets.** Open https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions. For each secret below: "press the pencil (Update) at the right of its row. Under "Repository access", pick "Selected repositories", then press the gear icon next to it and tick exactly the repositories listed. Press "Update secret"."

- RULESETS_TOKEN: beethoven-qa, beethoven-agents, beethoven-base
- SDLC_APP_PRIVATE_KEY: symphony-start, symphony-protocol, symphony-app
- SDLC_SETUP_APP_PRIVATE_KEY: symphony-start
- SDLC_METRICS_SALT: symphony-app
- Leave CLAUDE_CODE_OAUTH_TOKEN as it is.

Your choice: tick symphony-template as a fourth repository for SDLC_APP_PRIVATE_KEY if copies made with "Use this template" should keep starting their first Board run at once. Done when each row's "Repository access" column says "Selected repositories".

Source: housekeeping-steps.md lines 25-41.

**b. Delete the five old test repositories. Deleting cannot be undone.** For each: open its settings page, scroll to the red "Danger Zone" box, press "Delete this repository", confirm twice, type the full name (for example OpenSpineConsortium/sdlc-template-test) and press the red button. GitHub may ask for your password or a two-factor code.

- https://github.com/OpenSpineConsortium/sdlc-template-test/settings
- https://github.com/OpenSpineConsortium/sdlc-start-test/settings
- https://github.com/OpenSpineConsortium/sdlc-setup-test/settings
- https://github.com/Gregory-Schwing-MD-PhD/test-non-org/settings
- https://github.com/Gregory-Schwing-MD-PhD/test/settings

The canary repository replaces them, and the fresh test (Phase 2) makes new ones once these are gone.

Source: housekeeping-steps.md lines 43-59.

**c. Turn on "Automatically delete head branches" in six repositories.** Open each settings page (General tab), scroll to "Pull Requests" and tick "Automatically delete head branches". It saves by itself.

- https://github.com/OpenSpineConsortium/symphony-app/settings
- https://github.com/OpenSpineConsortium/openspineconsortium.github.io/settings
- https://github.com/OpenSpineConsortium/symphony-start/settings
- https://github.com/OpenSpineConsortium/symphony-protocol/settings
- https://github.com/OpenSpineConsortium/symphony-marketplace/settings
- https://github.com/OpenSpineConsortium/coordbench/settings

It may already be on in symphony-protocol and coordbench: the branches of the pull requests merged there on 2026-10-14 are already gone. Done when the box stays ticked after you reload the page.

Source: housekeeping-steps.md lines 61-78; branch lists read 2026-10-14.

**d. Delete the leftover merged branches, claude/festive-edison-al7xu2 among them.** For each repository: open its branches page, press the "All" tab, then the trash-can icon at the right of each branch named below. Delete only the names listed and leave anything else.

Still there at 19:10 UTC on 2026-10-14:

- symphony-start, 15, https://github.com/OpenSpineConsortium/symphony-start/branches : claude/actions-pull-requests, claude/already-adopted, claude/empty-repository, claude/festive-edison-al7xu2, claude/form-defaults, claude/magical-shannon-ak167f, claude/one-repository-per-request, claude/protocol-only-metrics, claude/readme-claude-code, claude/remove-sweep, claude/setting-breakdown, claude/setup-url-chain, claude/symphony-flip, claude/topic-symphony, claude/upbeat-sagan-6th2hu
- openspineconsortium.github.io, 15, https://github.com/OpenSpineConsortium/openspineconsortium.github.io/branches : claude/any-installation, claude/apps-privacy-7, claude/apps-privacy-v2, claude/apps-privacy-v4, claude/apps-privacy-v5, claude/apps-privacy-v6, claude/beethoven-public-listing, claude/beethoven-store-url, claude/extension-vpn-first-xjhm0g, claude/oschome-access-approval-6prr38, claude/symphony-flip, claude/symphony-page, claude/symphony-sound, claude/symphony-video, claude/upbeat-sagan-6th2hu
- symphony-protocol, 14, https://github.com/OpenSpineConsortium/symphony-protocol/branches : claude/festive-edison-al7xu2, claude/magical-shannon-ak167f, claude/protocol-readme-w1by8p, claude/release-approval, claude/spec-board-read-skmdpy, claude/symphony-flip, claude/upbeat-sagan-6th2hu, claude/validation-design, claude/validation-fixes, claude/validation-harness-step-1-l1gmpt, claude/validation-harness-step-2-bsbepq, claude/validation-harness-step-3-4dd8ji, claude/validation-harness-step-4-s410lk, claude/validation-harness-step-5-lc7fnj
- symphony-marketplace, 10, https://github.com/OpenSpineConsortium/symphony-marketplace/branches : claude/claim-no-track, claude/claim-test-quiet, claude/claim-worker-label, claude/festive-edison-al7xu2, claude/magical-shannon-ak167f, claude/marketplace-readme-qrze3x, claude/new-skill, claude/protocol-only-plugin, claude/symphony-flip, symphony-protocol/sync
- coordbench, 7, https://github.com/OpenSpineConsortium/coordbench/branches : claude/cooperbench-parity, claude/epic-fermi-f54f6m, claude/festive-edison-al7xu2, claude/token-alias, claude/wizardly-maxwell-8m4sdt, symphony-protocol/sync, and claude/bench-kit-0fxuxy (the list said to keep it while CooperBench used it; it has merged since)
- symphony-template, 1, https://github.com/OpenSpineConsortium/symphony-template/branches : claude/festive-edison-al7xu2 (four commits of 2026-10-10; the pages it added are on main)
- symphony-app, 8 on the list, not rechecked on 2026-10-14 (private), https://github.com/OpenSpineConsortium/symphony-app/branches : claude/app-claude-03-verdict-test-gzcakd, claude/festive-edison-al7xu2, claude/init, claude/magical-shannon-ak167f, claude/setting-breakdown, claude/symphony-flip, claude/upbeat-sagan-6th2hu, symphony-protocol/sync

Keep: main, master, board, metrics and data (data in symphony-app holds the collected metrics), and the branches of open pull requests. Update, 23:45 UTC: those are now claude/owner-decisions-f18, claude/owner-decisions-f19 and claude/validation-harness-step-6-mm6b8t in symphony-protocol; claude/coordbench-scrub-layers-8d9veg in coordbench; claude/handoff-2026-10-14e-qv2g34 and claude/project-thread-8d9veg in symphony-template; claude/94 and claude/25 in spine-program. claude/owner-decisions-f15 and f16, kept at 19:41 UTC, have merged and are gone; claude/owner-decisions-f4, named in the 14c handoff, is gone too.

If you'd rather not click about 70 times, say so and a thread will offer to delete them from your own computer.

Source: housekeeping-steps.md lines 80-111; 14c handoff line 139; branch lists read 2026-10-14.

**e. Symphony Setup's description.** Open https://github.com/organizations/OpenSpineConsortium/settings/apps/symphony-setup and add to the description the setting the App applies, in the plan's words: "lets GitHub Actions open pull requests". The description box and the "Save changes" button are inferred; the documents give only the link.

Source: PLAN.md, section 4, step 5.

### 6. Beethoven 20.0.0 (separate from Symphony)

In this order, from the guide's checklist:

1. The hand test (docs/store/TEST_BEFORE_UPLOAD.md in beethoven-extension, on the real grid with the VPN up) and the two st1234 curls from WSL.
2. Upload 20.0.0 at https://chrome.google.com/webstore/devconsole (the Beethoven item, id heoopgbkbkfckhhpbkkcgigohfekjicn) from the kit folder release/20.0.0/store-kit/: Package tab (upload 00-beethoven-20.0.0-chrome.zip); Store listing tab; Privacy practices tab; Distribution tab with "Visibility Public" and "Trusted testers empty", then Save draft; Test instructions (left menu, under Access); then press "Submit for review". The texts to paste are in the kit's PASTE.md.
3. Google Cloud, signed in as the account that owns the item: open https://console.cloud.google.com, make a project, enable "Chrome Web Store API", set the OAuth consent screen to User type External and press "Publish app", then "Create credentials, OAuth client ID" with Application type "Web application" and the redirect URI exactly https://developers.google.com/oauthplayground
4. Refresh token: open https://developers.google.com/oauthplayground, press the gear icon, tick "Use your own OAuth credentials", enter the scope https://www.googleapis.com/auth/chromewebstore, press "Authorize APIs", then "Exchange authorization code for tokens".
5. Publisher id: in the dashboard, "Publisher", then "Settings".
6. After the 20.0.0 upload is in: at https://github.com/OpenSpineConsortium/beethoven-extension/settings/secrets/actions press "New repository secret" five times (CWS_PUBLISHER_ID, CWS_ITEM_ID, CWS_CLIENT_ID, CWS_CLIENT_SECRET, CWS_REFRESH_TOKEN), then on the Variables tab "New repository variable": CWS_ON_PUSH with the value upload.
7. One check: Actions, "Release the extension", "Run workflow" on main with "upload" ticked.

Also open since 2026-10-13 and not rechecked: the beethoven-qa tags v4.0.0 and v5.0.0 (the plan gives `gh release create v4.0.0 --repo OpenSpineConsortium/beethoven-qa --target 8f72ad3226cf9cddc7802fe904da980ef6371635`, then v5.0.0 at 85f0e1cee65b16dc31be2ad1bb5c3dd52732b589), and beethoven-vscode#11 and #12, which need their tests before your OK.

Source: docs/checkpoints/2026-10-14/guides/beethoven-store-upload-and-releases.md, sections 1, 2 and 4; PLAN.md, section 4, step 7.

## Later, when a thread tells you

### 7. Approve release 0.5.0

Quoted from the 14c handoff: "GitHub e-mails; on the run's page under https://github.com/OpenSpineConsortium/symphony-protocol/actions press Review deployments, tick release, Approve and deploy."

- Approve before any other change under .github/workflows/ merges; otherwise the approved run fails and the release has to be published by hand.
- The tag goes on the first commit of main that carries 0.5.0, the stuck-claim fix's merge, so library changes merged after it (such as the measurement pass's retry on rate limits) are not in v0.5.0, however long you wait.
- A run nobody reviews fails by itself after 30 days.

Source: 14c handoff line 138; symphony-protocol README.md lines 138, 169 and 173.

### 8. Approve each real CooperBench dispatch

"A real dispatch is approved on its run's page: Review deployments, tick bench, Approve and deploy." One approval covers the whole dispatch.

Source: coordbench bench/cooperbench/README.md lines 158-162 and 206-207.

### 9. Remove COORDBENCH_CLAUDE_TOKEN

Once the real run works on the new secrets, remove COORDBENCH_CLAUDE_TOKEN from the old account's claude.ai cloud environment settings, under Environment variables, where it was added. The documents give no link. Do not add it to the new account's environment.

Source: 14c handoff line 137; cooperbench-run.md lines 68-69; coordbench bench/cooperbench/README.md lines 76-81.

### 10. Optional: canary check C7

After the adoption, C7 "runs by hand, from a clone, with the owner's own sign-in (`CANARY_ADMIN_TOKEN="$(gh auth token)" CANARY_TOKEN=... python3 scripts/canary.py run --checks C7`)". CANARY_TOKEN is a SymphonyBoard installation token for the canary repository; ask a thread before running it.

Source: symphony-protocol validation/DESIGN.md lines 710 and 855; scripts/canary.py lines 23-24.

### 11. Finish and submit the grant

When the revised packet is ready: upload the latex/ zip to Overleaf and compile it to confirm the page count, append the two biosketches, and send the single PDF to the AIDaS office by Fri 2026-10-16, 11:59 p.m. ET. The documents give no submission link or address.

Source: spine-program HANDOFF_2026-10-14c.md lines 22-27 and 45-47; README.md lines 3-4 and 37-40.

## Decisions you can make any time

- The compiler plan's decisions 3 and 4. (3) Whether actionlint and zizmor run in CI; the plan recommends not for now, since they run in the review before each pull request. (4) Whether its two editorial changes go in: actions "pinned to a commit" instead of "pinned to a major tag", and one YAML style for the eleven workflow files. Both matter only once the compiler starts after 0.5.0. Source: docs/checkpoints/2026-10-14b/plans/gh-aw-migration-plan.md lines 244-245.
- F2 and F8 need nothing from you. Your "implement all recommendations" of 2026-10-13 23:48 already chose them: for F2 the issue stays the work's identity, and for F8 the server's push time, once canary C5 confirms it. symphony-protocol's design file still words both as your choice, which is out of date. Source: docs/checkpoints/2026-10-14/memory/MEMORY.md lines 15 and 25; symphony-protocol validation/DESIGN.md lines 797 and 851.

### Possibly stale, confirm first

- Symphony for Chrome: "Submit Symphony for Chrome (https://chrome.google.com/webstore/devconsole), then set the five CWS_ secrets and CWS_ON_PUSH at https://github.com/OpenSpineConsortium/symphony-extension/settings/secrets/actions". It is from the plan of 2026-10-13 and no later list carries it, so it may be done. Source: PLAN.md, section 4, step 4.
- The five proposed additions to the Project instructions ("keep or drop each"), if you did not settle them when you set up the Project. Source: 14c handoff lines 85-91.
- Hardening of the release gate that the library's README calls yours and "none of them made yet": a tag ruleset on refs/tags/v*, the App's key in an environment of its own, and a code owner's review for the gate's files. No handoff asks for it. Source: symphony-protocol README.md line 184.
