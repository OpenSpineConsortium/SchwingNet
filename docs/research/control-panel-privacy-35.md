# The control panel's privacy section against statement 35

From the thread "Control panel sign-in" of the claude.ai Project "symphony_2", 2026-10-20.

## What changed

The About tab's "What this page keeps and sends" (the site's tools/pages/symphony/control/index/body.html)
left out three things the Apps' privacy statement version 35 already said: the Google Fonts
stylesheet and font files the browser fetches on each load, the pending sign-in record a press of
Sign in with GitHub keeps in the tab's own storage until GitHub's return, and the Dependencies
tab's stored chart choice. Site #96 adds all three in the statement's terms. A review read the
script to confirm them: the pending record is sessionStorage symphony_panel_oauth_state, cleared by
any GitHub return and by Microsoft's, never by Forget the token; the chart choice is localStorage
keyed by the repository's name, removed neither by Forget the token nor by taking the repository
off the list. Site #97, prepared by the Tokens thread, makes the Token 404 and the Share refusal say
what is really missing; it needed no statement version.

## Found on the way

- The panel checks in symphony-app must be pulled to main before each run: a stale checkout failed
  41 checks against the rebuilt Folders and Explore tabs (site #98, #99) that pass on main.
- On the site's master at 751fcfb, run-mutants.sh kills 588 of 590 mutants: k40_box_out_of_sight
  (K24, code.test.mjs) survives and m7_no404 (E5) is stale, its text gone from the script. Both
  are the same without this thread's changes, so they are the checks' owners' to refresh.
- The privacy section does not name symphony_panel_repo, the repository last opened, which the
  statement counts among "the names of the repositories you listed"; statement 36 may say it.

## Statement 36

Published on 2026-10-20 (symphony-start #82, site #100). It adds the Folders tab's actions on
OneDrive, checked against the site branch claude/folders-actions at 5cf7960 (new folder, rename,
delete into the recycle bin, upload in one request up to 4 MB or in 3.3 MB pieces, download through
Microsoft's short-lived address, cut, copy, paste and drag to move, sharing links whose kinds follow
the drive's type, properties, a preview pane, a whole-drive search of up to 2,000 results, file
pictures), all under the Files.ReadWrite access the sign-in already asked for, so no new consent
and no App permission changed. It drops the Folders tab's catalog read and describes the drive
organizer's workflow on Graph as symphony-template #261 left it: one commit on top of drive-catalog,
the Microsoft 365 top folders listed and not read, texts of up to 1,500 characters from at most 400
sampled files, and the step organize giving them to Claude on the repository's own token. Two
reviews against the code found what the first draft missed: the organize step's Claude run and
issues, the scope and limits of the walk, the search words that Ask in claude.ai carries, and how
New folder, Properties, the preview and name clashes really behave. Moves through Graph, planned
and not built, need a statement after 37 before they ship; so would a Claude run added to the onedrive
repository's own catalog workflow.

Statement 37 (symphony-start#84, site #101, 2026-10-20) adds the environment token-store, limited
to the default branch, which Symphony Setup makes in an adoption run (symphony-start#83); it raised
the statement's count of Setup's settings from seven to eight, which tests/test_form.py checks.
