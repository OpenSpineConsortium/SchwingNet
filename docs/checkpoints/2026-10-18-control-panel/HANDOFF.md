# Handoff: the control panel's Dependencies section and Folders page, 2026-10-18

Thread "Control panel sign-in" (the project symphony2), written at 06:20 UTC on 2026-10-18 while the
owner's weekly Fable quota stood at 98 per cent, so that any session on any model can carry the two
pieces of work to their pull requests. Everything below is pushed; nothing waits in a container.

## What is built, branch by branch

The Dependencies section (the owner's choice 6 of 2026-10-17: the panel draws each epic's tasks and
their blocked-by relations in the browser, from GitHub's sub-issues and dependencies, as the signed-in
person, nobody hosts anything; docs/research/control-board-graph.md):

- openspineconsortium.github.io, branch claude/graph-section from master 4b6ed93: 71520bb vendors
  Mermaid 12.2.0 (assets/js/vendor/mermaid.min.js, 5,494,801 bytes, sha256
  a8a6a6f805b074a8261a2825c86f99c8054acb3b35f50bb7e24a4f9f2c3c3b9f, MIT, its LICENSE beside it, a
  NOTICE paragraph); 1522372 adds the section (tools/pages/symphony/control/index/body.html between
  the Queue a task box and Ask Claude, the module "The Dependencies section" in
  assets/js/symphony-panel.js, control.css, README.md); 6d8533e rebuilds the pages. A review round
  (three lenses) ran and its fold was applying the findings when this was written; its commits, if
  any, come after 6d8533e. The chart text is byte-identical to the board's (symphony-protocol
  claude/dependencies, draft #51, held until 0.5.1 is cut).
- symphony-app, branch claude/graph-checks from main ddcfd9f: a80ceca adds
  signin/panel-checks/e2e2/graph.test.mjs (14 checks against a mocked GitHub, including byte-for-byte
  parity with the library's fixture board-epics-STATE.md) and a README bullet.
- symphony-start, branch claude/privacy-graph from main cded21b: 0ae3ee5 writes the Apps' privacy
  statement as version 13 for the section. See Numbering below.

The Folders page (the owner's ask of 2026-10-18 04:45: "one-click authorize and literally create a
repo which tracks certain files/folders from my onedrive/google drive that i choose in the browser";
the repository side is symphony-template #175, its design docs/research/drive-sync.md there; the
owner chose "No key" for the Google Picker at 05:13, so the page is OneDrive only for now):

- openspineconsortium.github.io, branch claude/folders-page from master 4b6ed93: 476095c adds
  /symphony/control/folders.html (tools/pages/symphony/control/folders/body.html, registered hidden in
  tools/build_site.py, initFolders in symphony-panel.js, control.css, the control page's link, README):
  Connect OneDrive (PKCE, a state of its own kept apart from the GitHub sign-in's callback), a
  page-drawn browser over Graph in place of File Picker v8 (Files.ReadWrite already reaches every
  file, so no SharePoint token and no iframe protocol), Create through GitHub's template form,
  Track (the secret SYMPHONY_DRIVE_REFRESH sealed first, then .github/symphony/drive.json, then the
  first run), Sync now, the 90-day line. The builder's rebuild of the pages and its suite runs were
  still in progress when this was written; commits, if any, come after 476095c.
- symphony-app, branch claude/drive-routes from main ddcfd9f: 972c15e adds GET /drive/config,
  POST /drive/connect and POST /drive/token to signin/worker.js (microsoft only; the client secret
  stays in Cloudflare), their cases in signin/test_worker.mjs, and the README's routes, settings and
  deploy steps.
- symphony-app, branch claude/folders-checks from main ddcfd9f: 3676e53 adds
  signin/panel-checks/e2e2/folders.test.mjs against a mocked GitHub, Microsoft and sign-in service.
- symphony-start, branch claude/privacy-drive from main cded21b: dc6adda writes the statement as
  version 14 for the page. See Numbering below.

The protocol: symphony-protocol #51 (claude/dependencies, head cc1f4fb) is green again after the
mutation lane's CI run let one mutant slip (the board listing a goal in the Queue; the dependencies
lane now seeds a goal); it stays a held draft until 0.5.1 is cut and is never merged before.

## What remains, in order

1. The Folders page's adversarial review and fix-up (one reviewer who also fixes, to spare the
   quota; the workflow script is
   /root/.claude/projects/-home-claude/c1201a4a-dfe9-5885-9c6b-7e196fd43e69/workflows/scripts/folders-page-wf_5414b57f-ba1.js
   in this thread's container only; a new session reviews the diffs of the four branches above
   itself). Then its suites: node --test signin/test_worker.mjs and bash scripts/check.sh in
   symphony-app; the browser checks with SITE=<site checkout> PORT=<free> bash run-suite.sh e2e2
   folders.test.mjs <log> from signin/panel-checks (Playwright resolves from /opt/node-tools in the
   cloud container).
2. Numbering of the privacy statement (the coordinator, 06:06): each change takes the next version
   after the one on main when it merges, and the coordinator is told the number. The beyond
   cooperation thread's 12 (Add a Claude account) and 13 (SymphonyBoard Actions) land first; the
   Dependencies statement becomes 14 and the Folders statement 15 if nothing else lands between.
   Each is renumbered on its branch after merging symphony-start main in (the head line, the
   Changes entry, the commit message); symphony-start's tests require the Changes entries
   consecutive from the head version, so each branch is red until the one before it is on main.
   Each statement merges by hand once green (symphony-start has no auto-merge).
3. The site: merge master into claude/graph-section and claude/folders-page first (site #32 changed
   SITE in tools/build_site.py: the build fails on any .html not in SITE and on any page more than
   two clicks from the header and footer; folders.html needs its own SITE node, hidden=True, added
   in the Folders pull request, and the node line is sent to the coordinator for the navigation
   thread). Rebuild against the merged statement: cd <site> && SYMPHONY_START_REPO=<symphony-start
   checkout> python3 -X utf8 tools/build_site.py, 0 problems; every page takes one stamp, so the
   rebuilt pages are one commit and a second site branch merges master in and rebuilds again. Each
   section stays self-contained (one root element, one init function), since the Control panel
   redesign thread owns the panel's layout and may move it into a tab.
4. Pull requests, each from its branch, each with an adversarial review before it (the Dependencies
   one had three lenses; the Folders one has step 1): symphony-start first (the statement live
   before the feature), then the site, then symphony-app's checks and routes; merged once green on
   the owner's standing permission, with the head sha copied from git.
5. The template: a research note for the Folders page under docs/research/ (the Google route kept
   for later: the Picker with a key, which the owner declined, or a page-drawn list under a wider
   Drive scope with Google's verification), a line in docs/research/README.md, and
   docs/memory/the-control-panel.md updated; after #175 merges, to avoid conflicts on the README.
6. The owner's one-time clicks, in the reply's own text, numbered, with exact links: Microsoft (an
   Entra app registration for any organization and personal accounts, platform Web with redirect
   URI https://openspineconsortium.com/symphony/control/folders.html, a client secret, delegated
   Files.ReadWrite and offline_access), Cloudflare (paste the merged signin/worker.js into the
   Worker symphony-signin, add MICROSOFT_CLIENT_ID as text and MICROSOFT_CLIENT_SECRET as a secret,
   deploy), GitHub (the Folders page as a SymphonyBoard callback URL; the Secrets permission already
   pending for the Tokens page), then a first connection as the test. No Google step.

## Who owns what around this work

The Symphony beyond cooperation thread owns every workflow's Claude token line and the Tokens page;
the Control panel redesign thread owns the panel's layout and look on both pages; the Website docs
and navigation thread owns the site header, the navigation and the docs section; the Word revisions
thread owns #175 and the repository side of the drive sync. This thread keeps the sign-in, the
Worker, what each section does and symphony-app's panel checks.
