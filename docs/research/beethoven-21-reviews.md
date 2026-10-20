# Beethoven 21.0.0's two adversarial reviews

The record of the thread "Beethoven worker opening", written 2026-10-16 at 19:15 UTC: the two
adversarial review rounds of Beethoven 21.0.0, pull request 17 on
OpenSpineConsortium/beethoven-extension
(https://github.com/OpenSpineConsortium/beethoven-extension/pull/17), and the fit measurement made
for it. Each round was a reviewer agent that read the branch, ran the checks and wrote a report
without editing anything. The reports stayed in the thread's scratchpad until the owner asked, at
18:58 UTC the same day, that every piece of work, intermediate or final, be in git for the next
account. They are kept here as prose: each finding with where it was, why it mattered and what was
done about it, then what neither round verified. The research behind the change itself is
beethoven-worker-opening.md beside this file, and the pull request's description has the short
account.

Round one read commit 8ac4fa9, the change as first written; its findings were fixed in e919417.
Round two read e919417; its findings were fixed in 5f1508f. The pull request merged at 09:24 UTC
as 87e06c8. Paths are in beethoven-extension, and line numbers are those of the commit each round
read.

## What both rounds found sound

Round one ran the typecheck (clean) and the whole test suite (45 files, 767 passed, 5 skipped).
It found the agreement's and the privacy statement's public copies byte-identical to the root
files, at versions 15 and 16, with `TERMS_VERSION` and `TERMS_DATE` to match, both texts ASCII and
no line of the agreement over 100 columns after section 5(f) was wrapped again. It found the
address handling sound: `projectLinkOf` and `isProjectUrl` in `extension/src/core/contract.ts`
take https only, with no user name or port, on the host claude.ai or claude.com exactly after the
URL parser has run, so a look-alike host becomes punycode and fails; they anchor the path
`/code/project/<id>` on the parsed path, so an encoded slash, a settings page, a session's link
and an environment's link all fail; and they drop the query and the fragment. The `set-pref`
action replaces the stored preferences with a fresh copy, so clearing the address leaves no stale
key, and a refused address is answered before anything is written. The background opens the
project by itself only for a worker the student pressed, with the switch "Open Claude when my
worker is ready" on, and once per worker link.

Round two ran the typecheck, the five test files the change touched most (124 passed, 1 skipped)
and the background's tests alone (13 passed). It checked the copies again, scanned every changed
file for non-ASCII text and for the word the repository forbids, reproduced its first two
findings in tests of its own against the extension's modules, measured the fit (below), and read
code.claude.com/docs/en/claude-projects to check claude.ai's three labels. It confirmed that the
address is refused in every bad shape the tests list and kept in one form otherwise, that each
button brings its own tab forward and never the other's, that the listeners for a tab's loading
and closing carry the new record, that every new state has a fixture the hygiene tests pass over,
and that the Settings field's refusal is announced.

## Round one: thirteen findings on 8ac4fa9

1. Blocking. The "You're online." moment, shown for four seconds after a worker the student
   pressed comes online (`ONLINE_HOLD_MS`), which is exactly when the project's page is opened,
   still offered *Open my session* whatever project was named (`extension/src/core/steps.ts`,
   lines 673 and 1220). Pressing it opened the worker's own link in a new tab: the plain session
   the change exists to keep the student away from, on the most prominent screen. Fixed: one
   function, `openClaude`, makes the button for the home and the moment alike, with the sentence
   on what to do in the project under it, and a test holds the moment to *Open my project*.
2. CLAUDE.md still said `TERMS_VERSION` was 14 and `TERMS_DATE` 2026-10-13, while the same bullet
   and `terms.ts` said 15 and 2026-10-16: the governing file contradicted the code. Fixed.
3. The store's texts and the upload's gates had not moved to 21.0.0. `docs/store/LISTING.md` and
   `docs/store/PASTE.md` listed the pages Beethoven opens without the project's and said the
   session's page opens when the worker connects; `docs/store/SUBMISSION.md` and
   `docs/store/TEST_BEFORE_UPLOAD.md` gated the upload on the site showing versions 15 and 14.
   Since `.github/workflows/release.yml` uploads on every push to main once `CWS_ON_PUSH` is set, a
   merge before the site was rebuilt would have shipped texts newer than the public privacy page
   the listing links. Fixed in part: the listing, the paste texts, the submission and the old
   store listing name 21.0.0 and versions 15 and 16, and the gate says the site publishes version
   16 first; the hand test's title and steps were finished in round two (its finding 4).
4. A worker online on a resumed session's own link, the link the successor job's `--continue`
   prints, lost every button to its session: with a project named the primary was *Open my
   project*, and *New session* appears only for an environment's link, which left *Copy link* and
   *Phone*. Fixed: an outline *Open my session* sits in the row under the press when a project is
   named and *New session* cannot appear, with the fixture h-online-project-session and a test.
5. Two sentences promised an opening the code may not do. The card and the Settings note said
   Beethoven opens the project when the worker is ready, but nothing opens with "Open Claude when
   my worker is ready" off, nor for a worker found online that the student did not start; README
   and the user's guide said the same. Fixed: the card, README, the guide, the privacy statement
   and the agreement say it opens while that switch is on, and the Settings note leans on the
   switch in the card above it.
6. One tab record served two addresses (`extension/src/entrypoints/background.ts`, lines 3938 to
   3987), so *Open my project* and *Open my session* each opened a new tab on every press once the
   other had been used. Fixed: the project's tab has a record of its own, `PROJECT_TAB_KEY`, beside
   `CLAUDE_TAB_KEY`, chosen by `tabKeyOf`, with a test of a second press of each button.
7. Tests did not exercise the guards the change relies on: the switch off with a project named, a
   worker found online but never pressed, the moment, the card's dismissal, the Settings field in
   the page, and finding 6. Fixed for all but one: tests for the moment, the row under the press,
   a second press of each button, the card's dismissal, the switch off, a link that looks wrong
   and the Settings field, among them "a project named with Open Claude when my worker is ready
   off: nothing opens when the worker is ready; Open my project opens it on request" in
   `extension/test/background.test.ts` and "Settings' project field" in
   `extension/test/ui-fixtures.test.ts`. A worker found online but never pressed has no test of
   its own with a project named; on main the project opens inside the one guard that opens the
   worker's link, which asks that the student pressed (`background.ts`, line 3883 at 87e06c8).
8. A minor point: a branch for a tab record with no address (`rec.link === undefined`) was dead
   code, since session storage is emptied whenever the extension updates, and it read a missing
   address as matching any. Fixed: the record keeps no address; finding 6's records replace it.
9. A minor point: documents stale since 14.0.0 said the extension opens only the session's link
   (`docs/ARCHITECTURE.md`, `SECURITY.md`, `docs/DIAGNOSTICS.md`, `extension/README.md`). Fixed:
   they name the project's page among the pages opened.
10. A minor point, on the Settings field (`extension/src/ui/settings.ts`): the old view flashed
    after *Use* until the background's new view arrived; the refusal's `role="alert"` was added to
    a paragraph already on the page, which a screen reader may not announce; Enter and Escape left
    the caret on the page's body. Fixed in part: the alert is a keyed element of its own and the
    caret returns to the row's button through the panel's own document; the *Add* case was
    finished in round two (its finding 5). The flash after *Use* was left as is.
11. A minor point: the card that points at Settings comes after the pin tip and the tour card, one
    card at a time, so a student who neither pins Beethoven nor closes the pin tip never sees it.
    Left as designed; the comments were rewritten to say the order.
12. A minor point: the fit of the new sentence at the panel's smallest sizes was not measured.
    Measured (below).
13. A minor point: claude.ai's own labels (*Work locally*, the + menu, *Allow once*) are
    Anthropic's and may change, and nothing said where they were read. Fixed: the comment in
    `extension/src/core/model.ts` names code.claude.com/docs/en/claude-projects, "Run a thread on
    your own computer".

Round one's verdict: the mechanics were right and well guarded and the suite green, but the
change was not mergeable until findings 1 to 5 were fixed.

## Round two: twelve findings on e919417

1. Should fix. A worker coming online with a project named opened a second tab on the project's
   page when *Open my project* had opened one already: the open-on-connect path (`background.ts`,
   lines 3886 and 3900) opened the address directly and never read the project's tab record,
   which only the buttons consulted. Round two reproduced it on the tests' fake browser, two tabs
   on the project's address. Fixed: the open-on-connect path brings the project's tab forward as
   the button does, and opens the worker's own link in a tab of its own as before; the test "the
   project's tab Beethoven opened before the worker was ready is brought forward when the worker
   is ready, never a second one" holds it.
2. Should fix. With a project named and a worker link that looks wrong, the home showed no button
   at all while the moment showed *Open my project*, though the project's page needs no worker
   link (`steps.ts`, lines 999 and 1141 to 1150). Fixed: the home keeps *Open my project*, and
   *Copy link* and *Phone*, which need the link, stay away; a steps test holds both cases.
3. Should fix. README still named 20.0.0 and the versions 14 and 15 in three places. Fixed.
4. Should fix. `docs/store/TEST_BEFORE_UPLOAD.md`, the hand test the submission gates refer to,
   kept 20.0.0's title and versions and had no step for anything 21.0.0 adds. Fixed: a step walks
   the Settings field (Add, a refused address, Use, Change, Clear), *Open my project*, the moment's
   sentence, the outline *Open my session* and the card.
5. Should fix, likely. After *Add*, the caret was probably lost: the button that had it was
   replaced when the background's new view arrived, and the field's test never checked where
   focus ended. Fixed: the caret stays on the row's button through *Add*, *Use* and *Clear*, and
   the Settings field's test checks it.
6. A minor point: `SECURITY.md` and CLAUDE.md named only claude.ai for the project's address,
   though claude.com is taken too. Fixed.
7. A minor point: the privacy statement's row for session storage listed one claude.ai tab; there
   are two records since 21.0.0. Fixed.
8. A minor point: three of the steps test's assertions sat behind a check of the moment's kind
   with no assertion on the kind first, so a change of signature would have silenced them. Fixed.
9. A minor point: a ragged line in the privacy statement's version 16 paragraph, which ships byte
   for byte. Fixed.
10. A minor point: the card reused the pin tip's icon, and the moment's sentence sat 20 px under
    the press against 10 px on the home. Fixed: the icon and the gap match the home.
11. A minor point in two parts. A refused address in the same action as other preferences drops
    them too; left as is, since no screen sends both. A failed message, with no answer at all,
    showed "That isn't a project's address"; fixed, a save with no answer keeps the field.
12. A minor point older than the change: "Open in Claude" survived in current documents. Fixed
    where they are current; the V11 and V12 status files keep it as history.

Round two's check of round one's thirteen: 1, 2, 4, 5, 7, 8, 9 and 13 fixed; 3 and 10 partly,
finished by its own findings 4 and 5; 6 fixed for the buttons but not for the open-on-connect
path, its own finding 1; 11 kept by design, with comments that now match the code; 12 measured,
with the fixtures' notes matching its numbers. Each code fault of round two was fixed with a test
shown to fail without its fix, and the whole suite passed before the merge (45 files, 770 passed,
5 skipped).

## What neither round verified

- The order in a real browser between the reply to a saved address and the Settings view the
  background pushes after it: the caret's fix is reasoned from the code and tested in a test
  document, not timed in Chrome.
- The premise itself: that a project cannot take a session the worker started, and that *Work
  locally* offers the worker's folder. Both rest on the owner's report and the documentation
  page, and were not tried.
- Whether opening a thread inside the project counts as a new load of the tab (`tabs.onUpdated`
  "loading"), which decides whether *Open my project* brings the tab forward or opens another;
  listed in beethoven-worker-opening.md too.
- Round two ran neither the whole suite nor the 19.0.0 background tests, which have flaked; the
  thread ran the whole suite. The mock portal's selftest fails its terminal section in a cloud
  container for want of `ssh-keygen`; the repository's CI has it and passes.

## The fit measurement

The question was whether the sentence under *Open my project* pushes the press, the sentence or
the row under them out of the panel at its smallest sizes. The development build
(`npm run build:dev`, the only build that carries the gallery of fixtures) is served from
127.0.0.1 and drawn in Playwright's Chromium at 360 px wide and 658, 560 and 500 px high, with a
stand-in for the extension's APIs, as `extension/e2e/sheet-fit.mjs` does for the sign-in sheet.
For each fixture the script reads where the press, the sentence, the row, the last card and the
try-asking block end, and whether each ends inside the window.

It ran when the fixtures were written, again in round two with a script of the reviewer's own,
and at 19:05 UTC on a development build made at 08:56 UTC from the round-two fixes. Round two
measured the moment's sentence 20 px under the press and the press 58 px higher than without a
project (its finding 10); the numbers below are after that fix.

- The home at 360 x 658: the press ends at 187 px with a project or without one; with one, the
  sentence ends at 235 (two lines) and the row under it at 283, 48 px lower than without.
- The "You're online." moment at 360 x 658: *Open my project* ends at 586 and its sentence at 634,
  against *Open my session* alone at 634; the press moves up 48 px to make room. At 560 and 500
  the press and the sentence stay in view (488 and 536; 428 and 476).
- What scrolls: the press, the sentence and the row stay in view at every size. With a project
  and every card (h-online-project-full) the page is 689 px, so it scrolls at every size; its last
  card, ending at 639, is in view at 658 and below the window at 560 and 500. The card that points
  at Settings (h-online-project-tip) ends at 577, below the window at 560 and 500; at 500 the home
  with a project is 531 px.

The script, as run. The build's folder is its argument, and `PLAYWRIGHT_DIR` names Playwright's
package folder, as `extension/e2e/sheet-fit.mjs` reads it; from the extension's folder, after
`npm run build:dev`: `PLAYWRIGHT_DIR=<playwright's folder> node fit.mjs .output/chrome-mv3-dev`.

```js
// The home and the online moment with a project named, at the panel's smallest sizes: does the sentence under
// Open my project push the press, the sentence itself or the row under them out of view? Modeled on
// e2e/sheet-fit.mjs: the development build served from 127.0.0.1, drawn in Playwright's Chromium with a
// stand-in for the extension APIs. Prints one line per fixture and size, with the baseline (no project) beside.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const DIR = path.resolve(process.argv[2]);
const SIZES = [[360, 658], [360, 560], [360, 500]];
const NAMES = ['j-online', 'j-online-project', 'h-online', 'h-online-project', 'h-online-project-session', 'h-online-project-tip', 'h-online-project-full', 'h-online-try'];
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png', '.txt': 'text/plain', '.md': 'text/plain' };
const server = http.createServer((req, res) => {
  const p = path.normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^([/\\])+/, '');
  const file = path.join(DIR, p);
  if (!file.startsWith(DIR + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
  res.writeHead(200, { 'content-type': TYPES[path.extname(file)] ?? 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const base = `http://127.0.0.1:${server.address().port}`;
const { chromium } = await import(pathToFileURL(path.join(process.env.PLAYWRIGHT_DIR, 'index.mjs')).href);
const browser = await chromium.launch({ headless: true });
try {
  for (const [W, H] of SIZES) {
    const page = await browser.newPage({ viewport: { width: W, height: H } });
    page.on('pageerror', (e) => console.log(`PAGE ERROR ${String(e).slice(0, 200)}`));
    await page.addInitScript(() => {
      const area = () => ({ get: async () => ({}), set: async () => {}, remove: async () => {}, onChanged: { addListener() {} } });
      const evt = { addListener() {}, removeListener() {} };
      globalThis.chrome = {
        storage: { local: area(), session: area(), onChanged: evt },
        runtime: { id: 'x', getManifest: () => ({ version: '21.0.0', name: 'Beethoven' }), getURL: (p) => new URL(p, location.origin).href, onMessage: evt, connect: () => ({ onMessage: evt, onDisconnect: evt, postMessage() {}, disconnect() {} }), sendMessage: async () => undefined, getPlatformInfo: async () => ({ os: 'win' }) },
        tabs: { create: async () => ({}), getCurrent: async () => undefined },
        windows: { getCurrent: async () => ({ id: 1 }) },
        permissions: { contains: async () => true, request: async () => true },
        sidePanel: { open: async () => {} },
        i18n: { getUILanguage: () => 'en' },
      };
      globalThis.browser = globalThis.chrome;
    });
    for (const n of NAMES) {
      await page.goto(`${base}/sidepanel.html?fixture=${n}`);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForSelector(n.startsWith('j-') ? '.m-foot' : '.home-primary', { timeout: 8000 });
      await page.waitForTimeout(900);
      const m = await page.evaluate((journey) => {
        const live = (e) => !e.closest('.leaving');
        const all = (s) => Array.from(document.querySelectorAll(s)).filter(live);
        const bottom = (e) => (e ? Math.round(e.getBoundingClientRect().bottom) : null);
        const press = all(journey ? '.m-foot button' : '.home-primary button')[0];
        const how = all(journey ? '.m-foot .home-reminder' : '.home-primary .home-reminder')[0];
        const row = all(journey ? '.m-track' : '.home-secondary')[0];
        const cards = all('.once');
        const tryAsking = all('.try-asking, .home-try')[0];
        return { vh: innerHeight, docH: document.scrollingElement.scrollHeight, scrollY: Math.round(scrollY), press: bottom(press), pressText: press?.textContent.trim(), how: bottom(how), howLines: how ? Math.round(how.getBoundingClientRect().height / parseFloat(getComputedStyle(how).lineHeight)) : null, row: bottom(row), lastCard: bottom(cards.at(-1)), tryAsking: bottom(tryAsking) };
      }, n.startsWith('j-'));
      const inView = (b) => (b == null ? '-' : b <= m.vh ? `${b} in` : `${b} OUT`);
      console.log(`${W}x${H} ${n.padEnd(26)} page ${String(m.docH).padStart(4)}  press ${inView(m.press)} (${m.pressText})  how ${inView(m.how)}${m.howLines ? ` ${m.howLines} lines` : ''}  row ${inView(m.row)}  cards ${inView(m.lastCard)}  try ${inView(m.tryAsking)}`);
    }
    await page.close();
  }
} finally {
  await browser.close();
  server.close();
}
```
