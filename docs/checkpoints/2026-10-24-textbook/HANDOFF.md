# Handoff: the Artifact Textbook, stopped at the weekly limit

Resolved 2026-10-24: the thread "Finish the SchwingNet textbook" resumed from this page, wrote and reviewed all thirty-two chapters and finished pull request #194; docs/research/artifact-textbook/README.md says where the programme stands. The rest of this page is the record of the stop.

Written 2026-10-24 about 06:15 UTC from the thread "SchwingNet textbook and critique reviews", at the owner's word to stop, checkpoint and push. The account reached its weekly limit at about 06:00 UTC (it resets 2026-10-29 21:00 UTC), which stopped every writer and reviewer mid-task; nothing is running.

## What is done

- The website: pull request #197 merged on 2026-10-24 04:50 UTC and the Docs run on main deployed it, its new step having read that GitHub reports the Pages site private. The book is at the members-only site's textbook/ path. Chapter text appears there once this branch merges. A public edition waits for the owner's word that the provisional is filed, then an allowlist the owner approves, Part III last (docs/memory/the-textbook-website.md).
- This branch, claude/193 (draft pull request #194), holds the chapter files under docs/textbook/, main merged in at 13f8d21, and the work that made them under docs/textbook/work/.

## Where each chapter stands

- Written and reviewed, finished: 01, 04, 07, 08, 11.
- Written, review stopped partway: 02 (no edits yet), 03 (the reviewer was applying its body edits, so the file may hold some of them), 05 (the reviewer was editing), 06 (body edits done, provenance rows not), 09, 12, 14, 17, 18 (each review had only begun), and 10 (the reviewer's corrected copy is docs/textbook/work/drafts/10-reviewed-not-applied.md and was not applied to the chapter file).
- Writer stopped before its report, so the file is an unlinted draft: 13, 15, 16 (a newer rewrite is in docs/textbook/work/drafts/16-rewrite-*.md), 20 (a 7,611-word draft the writer was cutting to 6,000) and 21 (its finish and limits sections are missing).
- Not written: 19 and 22 to 32. Ready-made writer prompts for 23 to 32 are in docs/textbook/work/prompts/.

docs/textbook/work/reports.md holds every report that came back, with what each writer left open and what each reviewer changed; docs/textbook/work/agents.txt is the order the agents ran in.

## How to resume

1. In a new session, fetch claude/193 and check it out as a worktree at /home/claude/schwingnet-193; tools/toc.py names that path.
2. Copy docs/textbook/work/ to the session's scratch folder as tb/, and replace the old scratch path in tb/brief.md, tb/review-brief.md and tb/prompts/*.txt with the new one.
3. Make the artifacts' texts again, which the tools read from tb/text/: `python3 -I -B artifacts/_synthesis/work/tools/extract.py <a SchwingNet clone> SchwingNet <scratch>/tb/text`, and the same with a symphony-template clone and the name symphony-template.
4. Finish the writers first (13, 15, 16, 20, 21), then write 19 and 22 to 32, each followed by one reviewer whose prompt carries what the writer's report left open, as reports.md shows. A writer prompt is the brief's two opening commands, the chapter's Part III or outside-Part-III sentence and its special notes; the prompts folder has the form. Then resume the stopped reviews.
5. Budget: twenty agents at once spent this account's five-hour window in about 80 minutes and the weekly window about two and a half hours later. About 17 writers and 27 reviews remain. Run fewer at once, or on another account's window, and only on the owner's word.
6. Then a pass across the book (figures, links, labels, privacy, ASCII), `bash scripts/check.sh` in a scratch copy, delete docs/agents/claims/193.md and docs/textbook/work/, write the pull request's body with its "## Adversarial review" section, mark it ready in its own call, merge once green and close #193.

## For the owner's attention

The writers found, and kept out of the chapters, personal details in the sources (logins, grid paths, names, e-mail addresses, phone numbers, a form link, a campus network range). One holding report also records a plain-text access-token file in the grid home with the note to rotate and delete it.
