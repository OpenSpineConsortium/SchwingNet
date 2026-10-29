---
name: grid-words-and-counts
description: How a grid word is sent and read, the HOLD and billing traps, every count greg approved with what was sent ; nothing is sent beyond greg's named counts
metadata:
  type: project
---

The hold on grid/WSU-data use is lifted for every thread (greg, 2026-10-29 15:32 and 17:05 UTC, [[hold-lifted-2026-10-29]]); his word and the count per job still decide every send.

- Send: dispatch https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid-accounts.yml on main with action `job` (never `log`), job `schwingnet-<word>` (status, anomaly-<stage>, bench-<name>, realism-<stage>, bordercall-<stage>, census-tiers, fetch-<row>, literature-<list>, cancel-<slurm id>, update) and a request id of your own; one dispatch per word. Read the answer on symphony-template's branch grid: `git fetch origin +refs/heads/grid:refs/remotes/origin/grid`, then logs/job-<job>.json.
- Before any send read logs/job-schwingnet-status.json there; send the status word only when a stage needs a fresher read. Newest read 2026-10-28 17:10 UTC: 17,602.29 GB used of 21,990.23 GB, 4,387.95 GB free; no gate job live.
- HOLD: a live bench or anomaly job writes grid/logs/HOLD, so later words run unpulled at the held commit; after an end or a cancel send one status word first. A realism word whose last report FAILED re-queues the stage by itself once the checkout has moved: send it only when the fix is on main.
- A word that failed unstarted on billing never ran and may be sent once more.
- `update` brings the gate's hpcworker clone to hpcworker main; it is needed once before the first bordercall word. hpcworker main 9930031 admits `schwingnet realism <stage>` and the gate's clone is at it (update of 2026-10-28 00:32 UTC), so no update is needed for realism (checked 2026-10-29 02:38 UTC).

Approved by greg's word:
- bordercall: 2 CPU (2026-10-25), pilot then full only if the pilot's countable count is above 0; unsent; decision 1 of [[decisions-2026-10-28]].
- Anomaly route of #391: 15 jobs (2 CPU, 13 GPU); 2 sent: select (40785048, exit 0, 1,004 CTs) and timing (40785227, failed after 30 min, report unread).
- #391 item 13's test: 1 GPU + 1 CPU; unsent. FleXray and xvr benchmark reruns on DeepFluoro: unsent.
- DRR study: run 1 prepare 40828920 (2026-10-28); run 2 prepare 40859208, array 40859209, merge 40859211, sent once 23:42 UTC, all 0:0, bench word read 02:13 UTC: spent, never resend. Run 3 on Metaflow (greg's count 12:51 UTC 2026-10-29: 18 GPU, full recompute in flexray_drr_gap_run3, #461): SENT once 15:11 UTC (request drr-run3-18-1512, gate 28f0387): prepare 40867572, array 40867573 (16), merge 40867575; masks present, no drr_seg; never resend ([[fluxray-rerun]]).
- Flux realism, greg's count of 2026-10-29 02:35 UTC (3 fetches + 2 GPU, replacing 2026-10-26's): fetches sent 02:55-02:57 UTC as labels 40860402, CT 40860413, klein-9B 40860425, all COMPLETED 0:0; GPU edit SENT once 14:02 UTC 2026-10-29 (request fluxrepro-edit-1402, job 40865836): stopped at its input check (train-extra packages missing, 16 GB V100), re-queued by the gate as 40867482 after the checkout moved, same stop; the fix's third send of the same word is not a new count; stats once only after the edit ends 0:0 ([[flux-realism-restart]]). aws_enhance_pet_labels is 11,256,936,591 bytes and aws_enhance_pet_ct 197,321,490,975 bytes.
- Literature: keys and one fetch sent and spent ([[literature-keys]]); a re-send needs a new count.
- NHANES 2013-14 DXA: decision 3, a count of one fetch by reading only.

Not counted (ask once, on a card, when the work comes back): the production SPINEPS array, the tier census (1 CPU), gold tier 3's rebuild (the labels fetch, one CPU index job, the Leipzig and Careggi CTs of 45,207,300,328 bytes), the rest of the #391 audit, any segmenter rung of the ladder.

**Why:** greg's count is the whole permission; a word sent twice, before its code is on main, or under a HOLD breaks it.
**How to apply:** record every send with its time and Slurm id.
