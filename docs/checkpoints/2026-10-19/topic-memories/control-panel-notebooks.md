---
name: control-panel-notebooks
description: How the control panel's Notebooks tab reads and writes notebooks.json on drive-catalog (sha discipline, cache, the write lock, internal repositories) and what its checks cover; read before touching nbRead, nbWrite or the Notebooks checks
metadata:
  type: project
  modified: 2026-10-19T06:50:00.000Z
---

Live since site #82 (2026-10-19), with the Apps' privacy statement 31 (symphony-start #74); checks notebooks.test.mjs N1-N26 and mutants n01-n39 in symphony-app signin/panel-checks/e2e2 (symphony-app #41).

- Reads go as objects (Accept application/vnd.github.object+json) with &at=<now>, since GitHub lets a signed-in read be cached a minute; a file over 1 MB answers encoding none, and its text comes from /git/blobs/<sha> raw. Playwright routes disable the HTTP cache, so checks assert the at= parameter instead.
- A write goes over the sha read with the cards (none when the file was absent) and takes the next sha from the PUT answer. Never read the sha fresh just before writing: that overwrote the organizer (the first review's blocker).
- A 409/422/404 is not always a change: a ruleset answers 409 too. After one, nbShaNow reads the file's sha again; only a sha that moved says "changed since the cards were drawn" and rereads; else the foot gives GitHub's own words, with access advice only on 404 or a 403 that is not a rate limit (nbRateLimited).
- catalog.json's sha is asked again before every write; a change stops the write. The proposal keeps every top-level field; taking out the last notebook deletes the file, the organizer's other fields with it, and the confirm says so.
- The write lock (nbWriting, nbWritingEnds, nbWriteId) lives outside nb, so a Refresh or repo switch never drops it; it ends with the sign-in (ends moved) and a write frees only its own lock (id), so a write after signing in again is not blocked by one still on its way.
- Visibility: nbVisibility reads visibility first (internal is private:true on GitHub but every enterprise member reads it), so an internal catalog repository holds no proposal and an internal notebook repository gets the make-it-private warning.
- The dialog draws 300 rows at a time, ticked first, ticks kept by path. The + tile id is nb-add.

**Why:** the drive organizer writes the same file; losing its work is the failure greg would notice.
**How to apply:** any new writer of a shared file on a branch follows the same sha discipline and re-reads the sha before calling a refusal a change.
