# Beethoven on the Chrome Web Store: the upload and automatic releases

Oct 13, 2026 - @Someone

## 1. Upload 20.0.0 now, by hand

The first upload of each version stays yours: it is your Google sign-in on the dashboard, and the automatic route (section 2) needs the item id the listing already has. Everything you paste or upload is in one folder of the repository, `release/20.0.0/store-kit/`, also zipped as `release/20.0.0/store-kit-20.0.0.zip` and attached in the thread. The files carry the number of the dashboard field in front of their name, so the folder lists in the dashboard's order; `PASTE.md` in the folder (the same as `docs/store/PASTE.md`) has every typed field's text.

**What is in the kit**

- `00-beethoven-20.0.0-chrome.zip`: the package, 441,350 bytes, SHA-256 `33294f8b9ea662d9354eef416a05ca1d570918dbcb74cd4b8f73e05f9bbbd790` (pinned in `release/20.0.0/SHA256SUMS.txt`).
- `01-description.txt`: field 1, the description.
- `04-store-icon-128.png`, `06-promo-tile-440x280.png`, `08-marquee-1400x560.png`: the icon, the small tile and the marquee.
- `05-promo-video-1280x720.mp4` and its thumbnail: the promo video, which goes to YouTube first; the dashboard takes the YouTube link. It is 9.0.0's and shows the old panel; leave field 5 empty if you would rather not show it.
- `07-screenshot-1-...` to `07-screenshot-5-...`: the five screenshots, 1280x800 (see the note on screenshots below).
- `12-test-username.txt`, `12-test-password.txt`, `12-test-instructions-500.txt`: the three Test instructions boxes, each under its limit (100, 100, 500 characters). `12-test-instructions-long-reply.txt` is the fuller text for a reply to a reviewer, not a box.

**Before you open the dashboard**

1. The hand test: `docs/store/TEST_BEFORE_UPLOAD.md`, on the real grid with the VPN up, and the two st1234 curls from WSL (the mock portal's test account must still answer from a fresh installation; beethoven-access#6 changed that on 2026-10-13).
2. `unzip -l` on the package: `fonts/` present, no `bridge/`, no `.msi`, no `.pkg`.
3. From inside the kit folder, the one-line Pillow check in `PASTE.md` ("Check the image files before you upload them"): the icon 128x128 RGBA, everything else RGB at its size.

**In the dashboard** (https://chrome.google.com/webstore/devconsole, the Beethoven item, id `heoopgbkbkfckhhpbkkcgigohfekjicn`)

1. **Package** tab: upload `00-beethoven-20.0.0-chrome.zip`. The name and the 128-character summary come from the manifest.
2. **Store listing** tab: fields 1 to 11 from `PASTE.md`, the files from the kit. Category, language and the three URLs are typed (official URL, homepage and support are in PASTE.md fields 9 to 11). The description changed for the public listing, so paste it again even though the item already has one.
3. **Privacy practices** tab: the single purpose, one justification per permission (`storage`, `alarms`, `scripting`, `sidePanel`, `webRequest`, `webRequestAuthProvider`, host permission), remote code No, the data-usage ticks (Authentication information Yes, as 19.0.0 had), the certifications, and the privacy policy URL https://openspineconsortium.com/beethoven/privacy.html. All of it is in `PASTE.md` under that tab's heading; the answers are 19.0.0's, since 20.0.0 changes no permission and no data type.
4. **Distribution** tab: Payments Free, **Visibility Public** (this is the change from 19.0.0), **Trusted testers empty** (the Beethoven-users group served the private listing and is retired), Regions United States only. Save draft.
5. **Test instructions** (left menu, under Access): the three boxes from the `12-` files.
6. Press **Submit for review**. Leave "Publish automatically after it has passed review" ticked unless you want to press Publish yourself; either is fine for 20.0.0.

**Screenshots.** The listing's images on the dashboard are 9.0.0's. The kit's `07-` files are the 20.0.0 screens the thread could capture headlessly against the mock portal, named by field 7's order in `PASTE.md` (Your grid, the sign-in sheet or GlobalProtect step, online with Open my session, Settings). If any `07-SCREENSHOTS-OUT-OF-DATE.txt` is in the kit, the images it names are still 9.0.0's: replace them in the dashboard only once you have a capture of your own, since a stale screenshot on a public listing is worse than a missing one (the store needs at least one).

**After the review** (usually one to three days, by e-mail to the dashboard's account): nothing else is yours. The site's install card already links the listing (site#18, merged 2026-10-13), and the approval check decides who can use the installed extension.

## 2. Automatic releases to the store: setting it up, step by step

The route is the organization's own Chrome Web Store release kit (OpenSpineConsortium/chrome-store-release-kit), the same one symphony-extension already calls. The thread's pull request adds the one workflow file, `.github/workflows/release.yml`, to beethoven-extension. The workflow runs on its own as soon as it is merged, and until the secrets below exist its store step says "Not configured" and the run stays green, so the order is: merge the pull request, finish the upload of 20.0.0 by hand (section 1), then set the secrets, then the variable.

What it needs from you is one Google OAuth client, one refresh token, and six repository settings. None of it is a Claude credential or an API key: the five secrets are the store's own sign-in for the one Google account that owns the item, and the kit sends them to Google's Chrome Web Store API and nowhere else. If you already made the client and the refresh token for symphony-extension, reuse them; only `CWS_ITEM_ID` differs between the two repositories.

**Step A. The OAuth client** (once per Google account, about ten minutes). Google's own page with screenshots: https://developer.chrome.com/docs/webstore/using-api

1. Open https://console.cloud.google.com signed in as the Google account that owns the Beethoven item (the dashboard's account).
2. Make a project, any name (for example "Chrome Web Store uploads").
3. APIs and services, Library: search **Chrome Web Store API** and press Enable.
4. APIs and services, OAuth consent screen: User type **External**, your e-mail as the support contact and the developer contact, add your own e-mail as a test user, save. Then **Publish app** (Publishing status). This matters: a consent screen left in Testing gives refresh tokens that expire after seven days, and the workflow would start failing a week later.
5. APIs and services, Credentials, **Create credentials, OAuth client ID**: Application type **Web application**, any name, and under Authorized redirect URIs add exactly `https://developers.google.com/oauthplayground`. Create.
6. Copy the **Client ID** and the **Client secret** it shows. They are `CWS_CLIENT_ID` and `CWS_CLIENT_SECRET`.

**Step B. The refresh token** (once, two minutes)

1. Open https://developers.google.com/oauthplayground in the same account.
2. Press the gear icon (top right), tick **Use your own OAuth credentials**, paste the client id and the client secret.
3. In the left column, under "Input your own scopes", type `https://www.googleapis.com/auth/chromewebstore` and press **Authorize APIs**.
4. Google warns "Google hasn't verified this app": that is expected, since Google does not verify apps that hold the store's write scope. Press Advanced, then "Go to \<your project name> (unsafe)", and allow.
5. Back in the playground, press **Exchange authorization code for tokens**. Copy the **Refresh token** it shows. That is `CWS_REFRESH_TOKEN`. (The access token beside it is not needed.)

**Step C. The publisher id and the item id**

- `CWS_PUBLISHER_ID`: in the developer dashboard (https://chrome.google.com/webstore/devconsole), open **Publisher** (left menu), then **Settings**; the publisher id is near the top.
- `CWS_ITEM_ID`: `heoopgbkbkfckhhpbkkcgigohfekjicn`, the 32 letters in the listing's address you sent.

**Step D. The repository settings** (https://github.com/OpenSpineConsortium/beethoven-extension/settings/secrets/actions)

1. Under **Secrets**, New repository secret, five times: `CWS_PUBLISHER_ID`, `CWS_ITEM_ID`, `CWS_CLIENT_ID`, `CWS_CLIENT_SECRET`, `CWS_REFRESH_TOKEN`, each with the value from the steps above. Paste each value into the secret's box only, never into a message or a file.
2. Under **Variables** (the tab beside Secrets), New repository variable: `CWS_ON_PUSH` with the value `upload`. That makes every push to main upload the new build as the item's draft, which you then submit by hand in the dashboard; set it to `publish` instead when you want each push submitted for review as well with no press of yours. Leave it unset until the 20.0.0 upload by hand is done, so the first automatic draft does not land on top of it.

**Step E. Check it once**: Actions, "Release the extension", **Run workflow** on main with **upload** ticked. The run's store step should end with the item's new draft; the dashboard then shows a draft numbered 20.0.0.\<commit count> under the Package tab. If it fails, the store step prints the store's own answer, unshortened; the usual causes are a refresh token from a consent screen still in Testing (step A4) or a missing scope (step B3).

The kit's manual, with the same steps and the reasons: https://github.com/OpenSpineConsortium/chrome-store-release-kit/blob/main/release-kit/README.md (private to the organization). The kit itself is already set to be callable from every repository of the organization, so beethoven-extension needs no setting on the kit's side.

## 3. What happens on each push, and how to release by hand

**Every push to main**, once the workflow is merged:

1. `npm ci`, then `npm run sync-profiles`, the typecheck and the vitest suite, the same checks as CI. A failing test stops the release; nothing reaches the store.
2. `npm run zip` builds the Chrome package, as the hand build does.
3. The kit writes the build number into the zip's manifest: the version becomes `<manifest version>.<number of commits on main>`, for example 20.0.0.312. The three integers in `extension/wxt.config.ts` stay the version you choose; the fourth makes every build from main higher than the last without a commit that only raises the manifest. The access service and the withdrawn-versions list accept four-part versions (checked: the service's version pattern allows up to 40 characters of digits, letters and dots; the kill-list matches exact strings, so a withdrawal names the full four-part version).
4. The GitHub release `extension-v20.0.0.312` is made, marked latest, with `beethoven-20.0.0.312-chrome.zip`, `beethoven-chrome.zip` and their SHA-256 attached. The newest build is always at https://github.com/OpenSpineConsortium/beethoven-extension/releases/latest/download/beethoven-chrome.zip (the repository is private, so that link works for members only; students install from the store).
5. With `CWS_ON_PUSH` = `upload`, the same zip becomes the item's draft in the dashboard; with `publish`, the draft is also submitted for review, and Chrome updates every installed copy once Google approves it. Unset, steps 1 to 4 happen and nothing goes to the store.

**A release with the exact manifest version** (no build number), for the record you keep under `release/<version>/`: push a tag `extension-v20.0.0` (or the next version). The tag always uploads, whatever `CWS_ON_PUSH` says.

**By hand, any time**: Actions, "Release the extension", Run workflow, pick the branch or tag, tick **upload** and, if you want it submitted too, **publish**. With neither ticked the run only tests and builds, and the zip is the run's artifact.

**Raising the version**: edit the version in `extension/wxt.config.ts` (three integers, as the rules say), update `release/<version>/` and the store texts as before, merge; that push releases it. The store refuses a version lower than the one it has, so once a 20.0.0.N build is on the item, the next hand upload has to be 20.0.1 or higher, never a plain 20.0.0 again.

**What stays by hand**: the listing texts, the screenshots, the privacy answers and the Distribution tab are not in the zip and are not touched by the kit; change them in the dashboard when `PASTE.md` changes. The publisher's own upload tool, `extension/scripts/publish-store.mjs`, stays as the one-off path from your machine; its header now records that the kit runs the same upload from CI on the organization's own OAuth client since 2026-10-13.

**What to watch**: the run's log is the only place the store's answer appears; the kit never retries and never shortens it. A refresh token stops working if the consent screen goes back to Testing, if you change the Google account's password with sessions revoked, or after about six months without use: make a new one with section 2, step B, and replace the secret.

## 4. Your checklist, in order

1. Hand test on the grid (`docs/store/TEST_BEFORE_UPLOAD.md`) and the two st1234 curls from WSL.
2. Upload 20.0.0 in the dashboard from the kit folder (section 1): package, listing, privacy, Distribution set to Public with no trusted testers, test instructions, submit.
3. Merge nothing yourself: the thread merges the release.yml pull request once its CI is green and tells you.
4. Google Cloud: OAuth client (section 2, step A), consent screen published.
5. OAuth Playground: refresh token (step B).
6. Dashboard: publisher id (step C).
7. beethoven-extension settings: the five secrets, then the variable `CWS_ON_PUSH` = `upload` (step D), after 20.0.0's own upload is in.
8. One manual run with upload ticked to see a draft appear (step E).
9. When the listing's review passes: nothing; the site already links it.

What the thread cannot do from a session, by rule and by reach: sign in to the dashboard or to Google Cloud, upload or submit anything, read or set repository secrets. Everything above is in your own browser with your own sign-in; a session never holds any of those values.
