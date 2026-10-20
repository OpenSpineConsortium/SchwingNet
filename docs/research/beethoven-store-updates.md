# How Beethoven reaches students' browsers

Source: the thread "Grid ssh gate", 2026-10-18, after the owner asked "can you also autosubmit?" and
"how can i make sure students who install the extension get the most recent version automaticaaly?".
The code is beethoven-extension#18 (22.0.0, merged and submitted) and #19 (23.0.0).

## Submission

The organization's variable CWS_ON_PUSH is publish, so every push to beethoven-extension's main runs
release.yml through the Chrome Web Store release kit with upload and publish: the store takes the zip as
the item's new draft and submits it for review in the same run. 22.0.0 went this way on 2026-10-18 (run
39092395735, version 22.0.0.114: "The item is submitted for review"). A run started by hand with Run
workflow uses its own upload and publish boxes instead, which is why 21.0.0.108 stayed a draft on
2026-10-16. A submission is withdrawn with "Cancel review" in the developer console. Since a merge is a
submission, a session asks the owner before merging to that main.

## Reaching a student once approved

Chrome asks the store for updates by itself every few hours and downloads a new version, but installs it
only when the extension is idle; a side panel left open keeps Beethoven from ever being idle, so a student
could stay a release behind for as long as the browser stays open. 23.0.0 listens for the downloaded
version (runtime.onUpdateAvailable, which also stops Chrome installing it by itself), asks the store once a
day besides (runtime.requestUpdateCheck, which Chrome throttles), and reloads only while nothing a restart
would lose is under way: no page of Beethoven's open, no press or press kept for the grid, no sign-in in
the grid's shell, no stop, no lab lead's gate press, no grid sign-in or one-shot password. A reload clears
storage.session, which holds those, and the passkey's unlock, which the privacy statement already says.
The worker on the grid is a Slurm job and keeps running.

## Not yet measured

How long the store's review takes for each version, and how soon after approval a student's Chrome
downloads it; the restart is held by tests against the fake Chrome, not yet watched in a real browser.
