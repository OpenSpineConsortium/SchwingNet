---
name: gold3-spineps-completion
description: The gold tier 3 completion (C2, sacrum and gap masks) as it stood at the checkpoint of 17:30 UTC 2026-10-29; greg's counts, where the masks, matcher, records and handoff are, what is left in order
metadata:
  type: project
  modified: 2026-10-29T17:31:17.097Z
---

Greg's words at 03:32 UTC on 2026-10-29: "segment the c2 and sacrums which are on ct volumes they just lack the masks and convert them all to gold tier 3 data". Cards: "Run SPINEPS here now" (04:23, overrides "never re-run SPINEPS" for these CTs only), "Continue all" (08:55), rule 3 (#459), "Just continue all ... use the grid where appropriate" (14:53), and at 15:22 UTC "1 CPU job on the grid": his word and count for one CPU job running bordercall's matcher over the census's existing SPINEPS masks, no segmentation. 17:05 UTC: the hold of 2026-10-28 lifted for every thread. 17:22 and 17:27 UTC: push everything, stop all adversarial review, stop. Thread: "Complete gold 3 CTs with SPINEPS".

Where it stands (checkpoint 17:30 UTC 2026-10-29):
- The handoff is SchwingNet docs/checkpoints/2026-10-29-gold3-completion/HANDOFF.md on branch claude/project-thread-1995zb-grid (its draft PR; read it first, its section 3 is the order).
- bordercall PR 28 (branch claude/project-thread-1995zb, 810fef2): holdings/fullspine_complete.py, 60 tests, holdings/spineps_run/ driver, research_notes/fullspine-rule6-calibration/. Suites green: holdings 196, coarse 6, combinations 6; archive, schwingcheck, autoanatomist (alone) and scanimport (needs pydicom) still to run. No CI; every suite before the merge; no review agents (greg, 17:27 UTC).
- SchwingNet #458 (claude/project-thread-1995zb, c838734): rule 3, 1,733 gold 3, 35 to complete; waits on the SPINEPS run.
- SPINEPS 2.1.2 in the container: 13 of 34 CTs done (s1411, s1532, s1593, s1606, s2065, verse018, 033, 255, 531, 547, 558, 559, 593), 21 left; enhance_pet 1379 not completable in a container. The 13 masks and the matcher records are in /mnt/project-files/gold3-ct/completion-2026-10-29/ (never in git).
- The grid job's word is `schwingnet-bordercall-complete` through symphony-template's grid-accounts.yml; not sent; send once after the grid PR merges and the status word and HOLD are read; record the Slurm id.

Rules the matcher follows: anchors are mutual best Dice with 0.8 containment, gaps named by count only if every level passes, walks stop at the first failure, rule 6 reads along the column's own axis (VerSe necks tilt about 34 degrees). The container arm (2.1.2) and the grid arm (2.1.1) are never pooled.

Traps: SPINEPS takes 11 to 13 GB, anything heavy beside it kills one or the other (PAUSE file between CTs; side work under choom -n 1000 nice -n 15); never SIGSTOP a harness task; every git command with -C; delete each CT's inputs when done (disk fell to 6 GB).

**Why:** a later thread must not re-run SPINEPS on the grid, name a level by SPINEPS alone, or send the job twice.
**How to apply:** start from the handoff's section 3; read the records' refusal reasons before counting any study as gold 3. See [[gold3-full-spine-rule2]], [[owner-science-rules]] and [[grid-words-and-counts]].
