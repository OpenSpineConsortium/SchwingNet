---
name: anomaly-route-thread-state
description: Where the #391 anomaly route stood at the checkpoint of 2026-10-27 04:47 UTC: timing job 40785227 FAILED (report unread), pack blocked on it, two of fifteen jobs sent; restart pages checkpoint-4 and SchwingNet docs/checkpoints/2026-10-27-morning/
metadata:
  type: project
  modified: 2026-10-27T04:57:45.367Z
---

State at the owner's checkpoint of 2026-10-27 04:47 UTC (thread "Plan the FleXray audit for #391"):

- Merged: SchwingNet #398, #403, #407, #410 (pack stage), #412 (checkpoint folder of 2026-10-26); symphony-template #488, #491, #498; hpcworker #49.
- Grid: select sent 2026-10-25 23:42 UTC (Slurm 40785048, exit 0, 1,004 CTs); timing sent 2026-10-26 00:16 UTC at 074e3bf (Slurm 40785227) and FAILED after 30 min 32 s, exit 1, on voh3 (status read 2026-10-27 04:08 UTC). Its report logs/ANOMALY-timing.md is unread. Resending `schwingnet-anomaly-timing` prints the report AND queues timing again at the gate's checkout (bench_failed_on_older_code); cancel with `schwingnet-cancel-<job>` if the report shows a code fault. Pack is refused by the gate until a timing report ends in exit 0. 13 of 15 approved jobs unsent. Nothing sent between the checkpoints.
- When the pack stage next changes: import the VerSe alphabet from src/schwingnet/segmenters.py (on main since #401), per the DRR thread's note of 2026-10-26 11:12 UTC.
- Restart pages of this checkpoint: symphony-template docs/research/handoff-2026-10-27-checkpoint-4.md (public entry point) and SchwingNet docs/checkpoints/2026-10-27-morning/ (README, anomaly-route.md, project-memory/), both from branch claude/project-thread-x16ebc.

**Why:** the owner asked at each checkpoint that a new account's project can pick up from git alone.

**How to apply:** a restarted thread reads checkpoint-4, then anomaly-route.md, then the grid status record before any send; see [[anomaly-pack-stage-design]], [[grid-status-reads-and-pr-watching]].
