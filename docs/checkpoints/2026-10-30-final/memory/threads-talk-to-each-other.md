---
name: threads-talk-to-each-other
description: greg's rule of 2026-10-30 02:37 UTC that parallel threads on shared work keep each other informed directly, not only through the coordinator
metadata:
  type: feedback
  modified: 2026-10-30T02:38:42.378Z
---

On 2026-10-30 at 02:37 UTC greg told the thread "Continue Bayesian synthetic validation" (bordercall PR 38): "keep in mind whatever the fuck the tan thread is doing, communicate with it" (the Tan thread is "Continue the Tan 2004 stratum split", PR 43; both change research_notes/synthetic-validation/README.md, tables.py and figures/FIGURES.md).

**Why:** the two threads edit the same note and the same files; a thread that works alone lands a rebase conflict or a README that contradicts the other's, and greg does not want to be the one who notices.

**How to apply:** when two threads touch one folder, each sends the other its file list and what it is adding (message_thread), says which lands first and who rebases, and asks for the interfaces it will need (here: the register's grouping function for strata_of's mixture). Do it when the work starts and again before pushing shared files. See [[owner-rules-2026-10-30]].
