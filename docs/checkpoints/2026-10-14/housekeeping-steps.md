# Housekeeping: the owner's clicks, in order

Written 2026-10-14 from GitHub's live state. Every step is a click in the browser while signed in as Gregory-Schwing-MD-PhD; nothing here was changed by a session. Where a page is one a session cannot read (App installations, the Actions box, the secrets page), the step says what you should see so you can confirm it yourself.

Already done, no click needed:

- spine-program already has "Automatically delete head branches" on, and so does symphony-template.
- The student aschehr has Write on spine-program (the invite was accepted; they are on the collaborator list).
- The Claude GitHub App reaches spine-program (a thread cloned it on 2026-10-13).
- spine-program's Board, Tidy and Protocol workflows all ran green on 2026-10-13.

## 1. Take spine-program off Symphony Setup, keep the canary on it

Why: Symphony Setup holds Administration on every repository it is installed on. It did its one job on spine-program (the settings, 2026-10-12). A student repository should not expose that. The canary thread needs the same App on symphony-protocol-canary, so narrow the list rather than uninstalling.

1. Open https://github.com/organizations/OpenSpineConsortium/settings/installations
2. Find the row "Symphony Setup" and press its Configure button.
3. Under "Repository access", "Only select repositories" should be selected. In the list of repositories, remove spine-program (the small x next to its name). If symphony-protocol-canary is not in the list, press "Select repositories" and add it.
4. Press Save at the bottom.

Done when: the Symphony Setup row's Configure page lists symphony-protocol-canary and not spine-program. Do not press the red Uninstall button; that would take the canary off too.

While you are on that page: SymphonyBoard's installation should say "All repositories" (leave it), and the canary thread asked for Actions: Read on SymphonyBoard's permissions (https://github.com/organizations/OpenSpineConsortium/settings/apps/symphonyboard/permissions, then accept the new permission on the installations page). That is the canary thread's item, not this list's.

## 2. Limit the organisation secrets to the repositories that use them

Why: an organisation secret set to "All repositories" can be read by any workflow in any repository of the organisation, a worker's too. Each secret below is used by only a few repositories, verified by reading every workflow file in the Symphony and Beethoven repositories today.

1. Open https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions
2. For each secret in the table, press the pencil (Update) at the right of its row. Under "Repository access", pick "Selected repositories", then press the gear icon next to it and tick exactly the repositories listed. Press "Update secret".

| Secret | Set it to these repositories |
| --- | --- |
| RULESETS_TOKEN | beethoven-qa, beethoven-agents, beethoven-base (each has .github/workflows/rulesets.yml naming it; no Symphony repository does) |
| SDLC_APP_PRIVATE_KEY | symphony-start, symphony-protocol, symphony-app (adopt.yml and adopt-run.yml; ci.yml and sync.yml; collect.yml) |

If other secrets on that page say "All repositories", the same treatment applies: SDLC_SETUP_APP_PRIVATE_KEY is used only by symphony-start, SDLC_METRICS_SALT only by symphony-app. Leave CLAUDE_CODE_OAUTH_TOKEN as it is; the plan keeps it one organisation secret for the Symphony repositories' workers.

One effect to know: symphony-template's template-init.yml reads SDLC_APP_PRIVATE_KEY when a repository is made with "Use this template" inside the organisation, to start the first Board run. After this change such a copy starts its Board on its first push instead. Adoption through the front door (the form) does not use the copy's secrets and is unaffected. If you want template copies to keep the old behaviour, tick symphony-template as a fourth repository.

Done when: each row's "Repository access" column says "Selected repositories" with the count you ticked.

## 3. Delete the five old test repositories

Why: the new canary repository symphony-protocol-canary replaces them, and Phase 2 makes fresh ones. All five still exist today.

For each repository, in turn:

1. Open its settings page (links below).
2. Scroll to the bottom, to the red "Danger Zone" box, and press "Delete this repository".
3. GitHub asks you to confirm twice, then to type the repository's full name (for example OpenSpineConsortium/sdlc-template-test) and press the red button. It may ask for your password or a two-factor code.

- https://github.com/OpenSpineConsortium/sdlc-template-test/settings
- https://github.com/OpenSpineConsortium/sdlc-start-test/settings
- https://github.com/OpenSpineConsortium/sdlc-setup-test/settings
- https://github.com/Gregory-Schwing-MD-PhD/test-non-org/settings
- https://github.com/Gregory-Schwing-MD-PhD/test/settings

Done when: each link answers "404 This is not the web page you are looking for".

## 4. Turn on "Automatically delete head branches" in six repositories

Why: with it on, GitHub deletes a pull request's branch the moment the pull request merges, so the branch lists stop filling up. It is off today in all six below (and already on in symphony-template and spine-program).

For each repository:

1. Open its settings page (links below). You land on the General tab.
2. Scroll down to the "Pull Requests" section.
3. Tick "Automatically delete head branches". It saves by itself, with a small green "Saved" flash; there is no Save button.

- https://github.com/OpenSpineConsortium/symphony-app/settings
- https://github.com/OpenSpineConsortium/openspineconsortium.github.io/settings
- https://github.com/OpenSpineConsortium/symphony-start/settings
- https://github.com/OpenSpineConsortium/symphony-protocol/settings
- https://github.com/OpenSpineConsortium/symphony-marketplace/settings
- https://github.com/OpenSpineConsortium/coordbench/settings

Done when: the box stays ticked after you reload the page.

## 5. Delete the leftover merged branches

Why: step 4 only covers future merges. Every branch below is already merged into its default branch (checked today: each is 0 commits ahead), so deleting it loses nothing. The two you asked about, claude/remove-sweep and claude/apps-privacy-7, are still there and are in the lists.

How, for each repository:

1. Open its branches page (links below) and press the "All" tab near the top.
2. Each branch row ends with a small trash-can icon at the right. Press it; the row greys out and offers Restore for a moment, then goes.
3. Delete only the branches named for that repository. Leave main, master, board, metrics and data, and the branches marked keep.

symphony-start, https://github.com/OpenSpineConsortium/symphony-start/branches (15 branches):
claude/actions-pull-requests, claude/already-adopted, claude/empty-repository, claude/festive-edison-al7xu2, claude/form-defaults, claude/magical-shannon-ak167f, claude/one-repository-per-request, claude/protocol-only-metrics, claude/readme-claude-code, claude/remove-sweep, claude/setting-breakdown, claude/setup-url-chain, claude/symphony-flip, claude/topic-symphony, claude/upbeat-sagan-6th2hu

openspineconsortium.github.io, https://github.com/OpenSpineConsortium/openspineconsortium.github.io/branches (15):
claude/any-installation, claude/apps-privacy-7, claude/apps-privacy-v2, claude/apps-privacy-v4, claude/apps-privacy-v5, claude/apps-privacy-v6, claude/beethoven-public-listing, claude/beethoven-store-url, claude/extension-vpn-first-xjhm0g, claude/oschome-access-approval-6prr38, claude/symphony-flip, claude/symphony-page, claude/symphony-sound, claude/symphony-video, claude/upbeat-sagan-6th2hu

symphony-app, https://github.com/OpenSpineConsortium/symphony-app/branches (8; keep data, it holds the collected metrics):
claude/app-claude-03-verdict-test-gzcakd, claude/festive-edison-al7xu2, claude/init, claude/magical-shannon-ak167f, claude/setting-breakdown, claude/symphony-flip, claude/upbeat-sagan-6th2hu, symphony-protocol/sync

symphony-protocol, https://github.com/OpenSpineConsortium/symphony-protocol/branches (14; a running thread may add a claude/harness-step-6, claude/harness-step-7 or claude/owner-decisions branch in the meantime, leave those):
claude/festive-edison-al7xu2, claude/magical-shannon-ak167f, claude/protocol-readme-w1by8p, claude/release-approval, claude/spec-board-read-skmdpy, claude/symphony-flip, claude/upbeat-sagan-6th2hu, claude/validation-design, claude/validation-fixes, claude/validation-harness-step-1-l1gmpt, claude/validation-harness-step-2-bsbepq, claude/validation-harness-step-3-4dd8ji, claude/validation-harness-step-4-s410lk, claude/validation-harness-step-5-lc7fnj

symphony-marketplace, https://github.com/OpenSpineConsortium/symphony-marketplace/branches (10):
claude/claim-no-track, claude/claim-test-quiet, claude/claim-worker-label, claude/festive-edison-al7xu2, claude/magical-shannon-ak167f, claude/marketplace-readme-qrze3x, claude/new-skill, claude/protocol-only-plugin, claude/symphony-flip, symphony-protocol/sync

coordbench, https://github.com/OpenSpineConsortium/coordbench/branches (6; keep claude/bench-kit-0fxuxy, the running CooperBench thread's branch, 3 commits ahead):
claude/cooperbench-parity, claude/epic-fermi-f54f6m, claude/festive-edison-al7xu2, claude/token-alias, claude/wizardly-maxwell-8m4sdt, symphony-protocol/sync

symphony-template, https://github.com/OpenSpineConsortium/symphony-template/branches (1):
claude/festive-edison-al7xu2

Done when: each branches page's "All" tab shows only the default branch and the ones marked keep.

## Pending, not a step now

The next symphony-protocol release waits for your approval once the fixes thread says the library is ready. GitHub will e-mail you; the click is "Review deployments", tick release, "Approve and deploy", on the run's page under https://github.com/OpenSpineConsortium/symphony-protocol/actions. Nothing to do until that e-mail.

## spine-program: is the installation up to date?

What its four workflows need (board.yml, tidy.yml, metrics.yml, protocol.yml): every one runs on the repository's own GITHUB_TOKEN with the permissions written in the file. No secret, no App token.

Right today:

- Board, Tidy and Protocol ran green on 2026-10-13 (the last Board run at 23:54, the Protocol run by hand at 18:35).
- SymphonyBoard is installed through the organisation's "All repositories" installation, which covers spine-program; the workflows do not need it, the field-metrics collector does.
- "Automatically delete head branches" is on.
- The ruleset "Protect the default branch" is active on main.
- The student aschehr has Write. The claim skill makes their worker:aschehr label the first time they claim, so no label step is left.
- The Claude GitHub App reaches the repository.

Not right yet, or unverifiable from here:

- Symphony Setup is still installed on spine-program until step 1 above.
- "Allow GitHub Actions to create and approve pull requests": a session cannot read this box. The Monday Protocol workflow opens its sync pull request only when the box is on; otherwise it opens an issue with a link that makes the pull request in one press, so nothing breaks either way. To check: https://github.com/OpenSpineConsortium/spine-program/settings/actions, scroll to "Workflow permissions", and look at the box "Allow GitHub Actions to create and approve pull requests". If it is greyed out, the organisation's setting rules it (https://github.com/organizations/OpenSpineConsortium/settings/actions, same section), and above that the enterprise's. No release newer than 0.4.1 exists yet, so the workflow has not needed the box so far.
- Issue #72's own list still has two boxes to tick once step 1 is done: the Setup App box, and "Greg tries the route once" (a Project linked to spine-program, /board, one todo issue).
