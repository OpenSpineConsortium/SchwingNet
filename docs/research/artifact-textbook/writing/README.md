# How the book was written

The thread "Finish the SchwingNet textbook", 2026-10-24, issue #193, pull request #194. What it holds is the method, so the next edition, or a chapter written again, can be made the same way.

- writer-brief.md: the brief every chapter's writer read, with the house rules (the chapter's shape, the four grades, mechanism only in Part III, people by role only, unsettled figures quoted as a record and not a final value).
- reviewer-brief.md: the brief every chapter's adversarial reviewer read; the reviewer checked each statement against its source and mended the chapter in place.
- reports.md: one block per writer and per review, then the cross-book pass, which made the figures that recur across chapters agree in value, grade and unsettled mark.
- tools/: toc.py reads a chapter's entry in the plan, rec.py prints an artifact's record, and lint.py checks a chapter's shape, its links, its grades, its length and the shapes of private data. Each is run as `python3 -I -B docs/research/artifact-textbook/writing/tools/lint.py docs/textbook/NN-name.md` from the repository root; lint.py needs a real checkout, since it resolves every link against it.

Writers and reviewers ran as parallel subagents of one session, at most eight at a time, each given the chapter's plan entry, its artifacts' extracted texts and the briefs; the site build's ledger check (tools/textbook_site.py) was then read for figures still stated without their mark.
