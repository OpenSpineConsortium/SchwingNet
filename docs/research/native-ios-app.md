# A native iOS app for the control panel

The note of 2026-10-19, in the thread "Control panel sign-in", on the owner's ask of that day to
start thinking about a native iOS app for the control board, made right after the broad pass that
fitted the board to a phone. Nothing here is built; the note sets out the three ways a phone can
carry the board, what each costs and buys, and the choices that are the owner's. Where a fact
about Apple's or GitHub's rules is named, its source is linked; what is not linked is the
author's reading of the panel's own code, as it is on 2026-10-19.

Corrected on 2026-10-19: the device flow under "Signing in from a native app" said a sign-in by
code lasts eight hours because refreshing needs the secret; GitHub's documentation says a
device-flow token renews with the client id alone, so it lasts until it is revoked.

## What a phone has today

The control panel is one web page, /symphony/control/ on the site, read in Safari. After the
mobile pass of 2026-10-19 (site pull request from the branch claude/panel-feedback) every tab fits
a phone's width, the deck is clipped so the page never pans sideways, the saved desktop text size
is not applied there, the status line at the foot sticks to the window's foot, Refresh holds the
page where it was, and the work a button starts (a workflow run, a token sign-in) speaks at the
foot with the run's steps and the last lines of its log, so no dialog waits for GitHub.

The page is not yet installable: it has a theme colour but no web app manifest, no icon for the
Home Screen and no service worker. Safari's "Add to Home Screen" still works on any page, but
without a manifest the result opens as a Safari tab, not as a full-screen app of its own.

## Three ways

### 1. A Home Screen web app (the same page, installable)

A web app manifest (name, icons, `display: standalone`, the start address with the repository),
Apple's touch icons and a small service worker that caches the page's own shell make the panel
install from Safari's Share sheet as an app with its own icon, full screen, in the app switcher.
Since iOS 16.4 such a Home Screen web app can also receive Web Push notifications and show a
badge, once the person allows it from inside the app
([MagicBell on iOS web push](https://www.magicbell.com/blog/ios-now-supports-web-push-notifications-and-why-you-should-care),
[their guide to the remaining limits](https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide)).
The same manifest makes the panel installable on Android, where Chrome's install and push are
older and broader.

What it costs: a day of work in the site repository, no Apple account, no store, no review, no
new code path; every later change to the panel reaches the installed app on its next open, as it
reaches the browser. What it does not buy: a notification needs a sender, something outside the
phone that holds the push subscription and sends to it when a run ends or a pull request waits.
The panel has no server of its own but the stateless sign-in Worker, which holds the App's
secret; a sender there, keyed by the GitHub login, with a workflow step that calls it, is small
but is a server-side thing the project has avoided so far (Decision: as few moving parts as
possible, no server of ours). Without a sender the installed app is the page, full screen, and
that is already most of what a phone needs. One thing to test on a real iPhone before relying on
it: the "Sign in with GitHub" redirect, which leaves the app for GitHub and must come back into
the standalone app and not into a Safari tab; iOS keeps a redirect inside the app when the
address is within the manifest's scope, and the sign-in service's callback is a page of the site,
so it should, but it is not yet measured.

### 2. A thin native app around the page

A SwiftUI app whose main screen is the panel in a WKWebView, with native parts around it: the
GitHub sign-in through ASWebAuthenticationSession (the system's sign-in sheet, which comes back
into the app by itself), the token in the Keychain, push notifications through APNs, a Home
Screen widget with the board's counts (queue, claimed, in review, open pull requests), the Share
sheet and Shortcuts. Apple's review guideline 4.2, Minimum Functionality, rejects an app that is a
repackaged website
([4.2 explained](https://vp0.com/blogs/fix-app-store-rejection-4-2-minimum-functionality),
[common rejections](https://www.choicely.com/tutorials/app-store-rejection-reasons)); the
widget, the notifications and the native sign-in are what lifts it above one, and they are also
the three things a phone cannot get from the page alone.

What it costs: the Apple Developer Program, 99 US dollars a year
([the fee and what it includes](https://ambsandigital.com/?p=11104)), a Mac with Xcode (the
maintainer has one: Beethoven's installers were signed on it), TestFlight for the owner and a few
testers before any store listing, an App Store listing with its privacy labels, and a push sender
as in way 1, since APNs is only the last hop: something must hold the APNs key and the device
tokens and send when GitHub's event happens. A GitHub Actions step can send to APNs with a key
held as a repository secret, but the device tokens are per phone and per person, so they live in
the sign-in Worker or in a repository branch nobody reads by hand; the Worker is the smaller
change. The web page keeps carrying every tab, so the app and the site never drift apart.

### 3. A native app on GitHub's API, the panel rewritten in Swift

Everything the page does (the board, the tasks, the dependency chart, the runs, the tokens, the
Folders tab) written again in SwiftUI against GitHub's REST API. It would be the best-feeling app
and the most expensive by far: the panel is about seven thousand lines of JavaScript with a
check harness of its own, and a second copy of that logic would need its own checks and would
fall behind the page with every change. Not recommended while the panel changes weekly.

## Signing in from a native app

Two routes, both without a secret in the app:

- The web flow through the existing sign-in service: ASWebAuthenticationSession opens
  SymphonyBoard's authorize page, GitHub returns the code to the service's callback, the service
  exchanges it and refreshes it as it does for the browser today, so the app gets the same
  eight-hour user token and six-month refresh token the page gets, and the App's secret stays
  in the Worker. The smaller change, since nothing new is minted.
- GitHub's device flow, which a GitHub App may turn on and which needs no secret
  ([GitHub's page on authorizing users for GitHub Apps](https://docs.github.com/en/enterprise-server@3.2/developers/apps/building-github-apps/identifying-and-authorizing-users-for-github-apps)):
  the app shows a code, the person types it at github.com/login/device. The token it earns
  renews without the secret too: of the refresh's client secret, GitHub says "Required unless the
  user access token was generated using the device flow"
  ([GitHub's page on refreshing user access tokens](https://raw.githubusercontent.com/github/docs/main/content/apps/creating-github-apps/authenticating-with-a-github-app/refreshing-user-access-tokens.md)),
  and each refresh gives a new eight-hour token and a new six-month refresh token, so a sign-in
  by code needs no second sign-in and lasts until it is revoked, for whoever holds it. The
  control panel ships a code way switched off (site #88, symphony-app #46, 2026-10-19) because
  anyone can start a code and talk a person into typing it: the App's client id is public, and
  the token a code earns goes to whoever started it and renews for as long as they like;
  symphony-app's signin/README.md, "The device routes", says what turning it on opens and what
  ends such a token.

The app would hold a GitHub token in the Keychain, as the page holds one in the browser; it never
holds a Claude credential, which the rule "no API key and no Claude credential anywhere" keeps
out of every client.

## What the owner decides

1. Which way first. The recommendation: way 1 now, since it is a day's work in the site, costs
   nothing to run and gives the phone a full-screen app with an icon; then way 2 only when
   notifications or a widget are wanted, since those are what justify an app and an Apple
   account; never way 3.
2. Whether notifications are wanted at all, and for what: a run that ended, a pull request whose
   check is green, a claim released, a token's window reset. Each needs the sender above, which
   is a server-side piece in the sign-in Worker; the owner's standing decision against servers of
   our own is the reason to ask first.
3. Whether the App Store is the aim or TestFlight is enough: a private tool for the owner and a
   few collaborators ships through TestFlight without a public listing, which also sidesteps the
   4.2 question until the app has its native parts.
4. The privacy statement: way 2 adds a device token and a push subscription to what the sign-in
   service holds, so the Apps' privacy statement takes a new version before the app ships, as
   every feature does.

## What is not yet measured

- Whether an installed Home Screen web app on iOS 26 returns into itself from the GitHub sign-in
  redirect (way 1's one open question).
- The real cost of a push sender in the Worker: the subscription store, the APNs or Web Push
  call, and the workflow step that triggers it.
- Whether Apple's review takes a WKWebView app with a widget and notifications as more than a
  website; the sources above say the native parts decide it, and only a submission settles it.
