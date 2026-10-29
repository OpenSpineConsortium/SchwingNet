---
name: drr-comparison-grid-count
description: The owner's count for the DRR comparison (2 fetches done, 2 GPU jobs: bench flexray_drr_seg running as 40799505, bench flexray_drr_gap once after it), the sent state, and the grid HOLD lesson
metadata:
  type: project
  modified: 2026-10-27T04:32:08.230Z
---

Count: the owner (greg) tapped "2 fetches + 2 GPU jobs" at 2026-10-26 01:19 UTC on the thread "Compare FleXray DRRs to real X-ray corpora" (cmsg_014WUU19NHgHPhf7QetT9cbSBA775A5CPNAFT3bnoF53ko). Each word goes once; a second send of a bench word only reads its report after the job ends. The SPINEPS production array is NOT approved, and SPINEPS is never run.

Sent state:
- Fetches: moose_weights (Slurm 40788796) and hf_flexray_data (40788810, 19 GB) both COMPLETED 2026-10-26. Room 4,393 GB at 04:08 UTC 2026-10-27.
- Seg job, first attempt: 40790826 FAILED (no module fxr). Fixed by SchwingNet #414 (6b2daf4).
- Seg job, current run: bench flexray_drr_seg SENT 03:39:47 UTC 2026-10-27 as Slurm 40799505 at 6b2daf4, RUNNING on voh5 at 04:08 UTC.
- Gap job: bench flexray_drr_gap UNSENT.

Owner's choices, 2026-10-27:
- 04:15 UTC: the comparison should run without CT masks. This is SchwingNet's next PR: render segmenter "none", a group flexray_drr_ct from the CT alone, fluxray_raw groups on none, and the gap job no longer refusing for missing mask folders (BENCH_SKIP_MASKS / --skip-masks).
- 04:31 UTC, card "Keep it running": do NOT pause the seg job. The one gap job goes after the seg job ends, on the merged mask-free code, and covers every group. No extra jobs.

CHECKPOINT 2026-10-27 ~04:58 UTC (owner's word 04:47): thread stopped. Mask-free work is SchwingNet draft #418 (branch claude/project-thread-d14v3r, head 1c0b55d, pushed with SKIP_GATE=1). Handoff: SchwingNet docs/checkpoints/2026-10-27-drr-comparison/HANDOFF.md, with study-brief.md beside it. The scheduled 05:39 seg check was deleted, so the next account does the grid steps.

Next steps:
1. Finish #418: remove BENCH_SKIP_MASKS, do the study part per study-brief.md, review, merge.
2. After 40799505 ends, send one status word, then the seg bench word once to read its report.
3. If it ends well, send bench flexray_drr_gap once.

HOLD lesson: a running or queued bench writes grid/logs/HOLD, which stops every word's pull, so the grid checkout stays at the running job's commit. A gap word sent while seg runs would run OLD code and read half-made $DATA/moose. Slurm also snapshots bench.sbatch at submit. A cancelled job can leave its HOLD, which only the next word's release_hold clears, and that word itself runs unpulled. So after a cancel or an end, send one status word first, then the real word.

**Why:** the owner's count is the whole permission. A word sent twice, before its code is on main, or while the checkout is held, breaks it.
**How to apply:** update the sent state at every send with the time and the Slurm id. See [[segmenter-block]].
