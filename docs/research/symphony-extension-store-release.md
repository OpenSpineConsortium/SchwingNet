# Symphony for Chrome on the Chrome Web Store

Source: the thread "Symphony extension on the Chrome Web Store", 2026-10-18, read from OpenSpineConsortium/symphony-extension at main (233e5af, version 1.4.1) and OpenSpineConsortium/chrome-store-release-kit at main.

## What is already built

symphony-extension's .github/workflows/release.yml calls the organization's release kit (chrome-store-release-kit, release-kit.yml at main). Every push to main tests, builds the WXT zip, numbers it `1.4.1.<commit count>` and keeps it as the GitHub release `extension-v<version>`, whose zip is at https://github.com/OpenSpineConsortium/symphony-extension/releases/latest/download/symphony-chrome.zip. The kit's store job runs on a push when the variable CWS_ON_PUSH is upload or publish, and takes the five secrets CWS_PUBLISHER_ID, CWS_ITEM_ID, CWS_CLIENT_ID, CWS_CLIENT_SECRET and CWS_REFRESH_TOKEN. Its ten runs to 2026-10-11 were green with the store job skipped, since no CWS_ON_PUSH reached the repository then. docs/store/SUBMISSION.md and docs/store/LISTING.md in symphony-extension hold every field of the listing and the privacy tab. So nothing needs building: the release needs the store item and its id.

## The one hazard

The organization variable CWS_ON_PUSH is publish for every repository since 2026-10-18, so the next push to symphony-extension's main sends its zip to the store. If CWS_ITEM_ID is set at the organization's level, it names Beethoven's item, and that push would upload Symphony onto Beethoven's item. The store would most likely refuse it, since 1.4.1.N is below Beethoven's 21.0.0, but that is luck, not a rule. A repository secret overrides an organization secret of the same name, so CWS_ITEM_ID is set as a repository secret in symphony-extension, with Symphony's own id, before anything merges there. Each extension repository has its own CWS_ITEM_ID; the other four secrets, one Google account's publisher id, OAuth client and refresh token, serve every item that account publishes (release-kit/README.md, section 2).

## The order

1. The first upload is by hand: the store gives an item its id only when a zip is uploaded to a new item. The latest release's zip serves, since CI's next build has a higher number.
2. The listing, privacy and distribution tabs from LISTING.md, then Submit for review.
3. CWS_ITEM_ID as a repository secret of symphony-extension, the id from the item's URL.
4. From then on every push to main uploads and submits. Every submission is reviewed again; "Cancel review" in the dashboard withdraws one.

Not checked from the container: whether https://openspineconsortium.com/symphony/privacy.html answers 200 (the site is blocked here), and whether CWS_ITEM_ID is in fact an organization secret (the proxy refuses the secrets API).
