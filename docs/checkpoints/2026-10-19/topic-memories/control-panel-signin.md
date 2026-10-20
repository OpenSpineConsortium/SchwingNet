---
name: control-panel-signin
description: Control panel Sign in with GitHub is live since 2026-10-17; the Worker URL, Client ID, and how a cloud session can check it
metadata:
  type: project
  modified: 2026-10-17T14:38:18.844Z
---

Sign in with GitHub on https://openspineconsortium.com/symphony/control/ was switched on 2026-10-17 (site #24, symphony-app #17, symphony-template #126). SIGNIN_SERVICE is https://symphony-signin.openspineconsortium.workers.dev and CLIENT_ID is Iv23liTkIRov2FYN83wD. Neither is a secret. The client secret lives only in the Worker's GITHUB_CLIENT_SECRET.

**Why:** the next session shouldn't ask the owner for these values again.

**How to apply:** the cloud proxy answers 403 for workers.dev and openspineconsortium.com through curl, so read both with the WebFetch tool. Building the site needs beethoven-extension, beethoven-vscode, symphony-extension and symphony-start cloned beside it under /home/claude. The panel-checks take SITE=<site checkout> and need Playwright linked into e2e2/node_modules. Check G7 can fail on timing in a full run and passes when rerun alone. No session can do the real sign-in; that step is the owner's.

Every new signed-in page needs its own callback URL in the SymphonyBoard App's settings: the redirect_uri is the page's own address, and GitHub refuses one it doesn't list ("The redirect_uri is not associated with this application"). The Worker accepts any page on the origin. /symphony/control/tokens.html (site #25, 2026-10-17) needed this; greg was given the step.

greg dropped the "panel never takes a Claude token" rule on 2026-10-18. The Tokens page's "Add or renew a slot" (site #26, privacy v10 in symphony-start#46) seals a pasted setup-token in the browser and PUTs it as an org secret. It needs SymphonyBoard's org permissions Secrets and Variables (read and write), which are greg's clicks. docs/memory/the-control-panel.md in the template still says "never a Claude token"; its owner should correct it.

Statement numbering on 2026-10-19 14:20 UTC: version 34 is the Sync run (symphony-template #257, every adopted repository offered the board files by pull request from symphony/sync) plus symphony-start #76 (Token workflow in a protocol-only adoption), on start branch claude/apps-privacy-sync. The sign-in-by-code text first drafted as 34 on claude/apps-privacy-v34 becomes 35. The Add token fixes thread holds #257 and #76 until 34 and its site page are live.
