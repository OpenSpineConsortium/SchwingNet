---
name: grid-words-and-counts
description: How a grid word is sent and read, the HOLD and billing traps, every count greg approved with what was sent (state at the status read of 2026-10-28 17:10 UTC); nothing is sent while the hold stands
metadata:
  type: project
---

Nothing goes to the grid while the hold stands ([[hold-and-wrap-up]]), save what greg names: on 2026-10-28 at 22:58 UTC he named the FluXray rerun. The other approved counts below wait for it and for their work.

- Send: dispatch https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid-accounts.yml on main with action `job` (never `log`), job `schwingnet-<word>` (status, anomaly-<stage>, bench-<name>, realism-<stage>, bordercall-<stage>, census-tiers, fetch-<row>, literature-<list>, cancel-<slurm id>, update) and a request id of your own; one dispatch per word. Read the answer on symphony-template's branch grid: `git fetch origin +refs/heads/grid:refs/remotes/origin/grid`, then logs/job-<job>.json.
- Before any send read logs/job-schwingnet-status.json there; send the status word only when a stage needs a fresher read. Newest read 2026-10-28 17:10 UTC: 17,602.29 GB used of 21,990.23 GB, 4,387.95 GB free; no gate job live. The last entry, 18:32 UTC, is the carry of the old project's folder (#444).
- HOLD: a live bench or anomaly job writes grid/logs/HOLD, so later words run unpulled at the held commit; after an end or a cancel send one status word first.
- A word that failed unstarted on billing never ran and may be sent once more.
- `update` brings the gate's hpcworker clone to hpcworker main; it is needed once before the first bordercall word. No realism word passes hpcworker's gate until an hpcworker PR admits it, then `update`.

Approved by greg's word:
- bordercall: 2 CPU (2026-10-25), pilot then full only if the pilot's countable count is above 0; unsent; decision 1 of [[decisions-2026-10-28]].
- Anomaly route of #391: 15 jobs (2 CPU, 13 GPU); 2 sent: select (40785048, exit 0, 1,004 CTs) and timing (40785227, failed after 30 min, report logs/ANOMALY-timing.md unread).
- #391 item 13's test: 1 GPU + 1 CPU; unsent. FleXray and xvr benchmark reruns on DeepFluoro: unsent.
- DRR comparison: first run prepare 40828920, 16 tasks of 40828921, merge 40828923 (2026-10-28 03:08 to 03:26 UTC). The FluXray rerun (greg's tap of 16:28 UTC, 18 jobs; his go of 22:58 UTC, "this project can run it now") is SENT and spent: SchwingNet #448 added BENCH_RERUNS, status read 23:41 UTC (no job live), word sent once at 23:42 UTC (request drr-gap-18-2342-m7gfac, commit 8889bd7): prepare 40859208, shard array 40859209 (16 tasks), merge 40859211. Never resend it; a rerun that writes no report needs greg's word before any resend. Prepare started 00:30 UTC on 2026-10-29 (alh3, L40S). Send `schwingnet-bench-flexray_drr_gap` once only after sacct shows all three COMPLETED 0:0: main has moved past 8889bd7, so a failed report would be queued again under #312's rule.
- Flux realism: 5 fetches + 4 GPU (2026-10-26); none sent; the records disagree on whether its stages are approved. aws_enhance_pet_labels is 11,256,936,591 bytes and aws_enhance_pet_ct 197,321,490,975 bytes, not the 2.5 GB and 177 GB once listed.
- Literature: keys and one fetch sent and spent ([[literature-keys]]); a re-send needs a new count.
- NHANES 2013-14 DXA: decision 3, a count of one fetch by reading only.

Not counted (ask once, on a card, when the work comes back): the production SPINEPS array, the tier census (1 CPU), gold tier 3's rebuild (the labels fetch, one CPU index job, the Leipzig and Careggi CTs of 45,207,300,328 bytes), the rest of the #391 audit, any segmenter rung of the ladder.

**Why:** greg's count is the whole permission; a word sent twice, before its code is on main, or under a HOLD breaks it.
**How to apply:** record every send with its time and Slurm id.
