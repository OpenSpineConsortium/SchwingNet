---
name: papers-in-hand
description: The 44 papers behind synthetic_spine and the clinical reread go into bordercall's main (research_notes/clinical-reread/papers/), greg's choice on a decision card of 2026-10-29 03:30 UTC; each matches PAPERS.sha256
metadata:
  type: project
  modified: 2026-10-29T03:31:00.148Z
---

The 44 PDFs are the 42 of spine-program synthetic_spine/sources.csv and Panjabi's four, with his thoracic paper twice. They are in bordercall at research_notes/clinical-reread/papers/.

How they got there:
- greg's word of 2026-10-29 00:33 UTC first put them in git, at commit dd8a300 on branch claude/project-thread-ljtlt9 (draft PR 24).
- His instructions of 02:06 UTC repeated the older rule, "never committed". So the thread "Finish the clinical reread" asked him on a decision card.
- At 03:30 UTC he chose "Merge them into main". They are on branch claude/project-thread-adplcz at commit 520dbd7 (draft PR 26) and reach main when that PR merges.

papers/README.md maps each key to where it came from. Every file matches research_notes/clinical-reread/tools/PAPERS.sha256, and the notes cite pages of exactly those bytes. hinck1966.pdf carries the publisher's download stamp as it came; no note quotes it.

The project symphony_4's library (/mnt/project-files/: literature/synthetic_spine/, last_papers/, synthetic/ and one PDF at the root) held only copies of these 44 under their upload names.

Still in force for these 44:
- No page image or run of a paper's text goes in a note (tools/check_notes.py).
- A quote is 12 words at most.
- Never scrape Google, never pass a robot check.

Other uploads stay out of git unless greg says otherwise.

**Why:** a new account starts with empty project files, so these papers now travel with the repository.

**How to apply:** read papers/ from main once PR 26 merges, or from PR 26's branch until then. Never refetch them.

Related: [[clinical-reread]], [[closed-papers-check]].
