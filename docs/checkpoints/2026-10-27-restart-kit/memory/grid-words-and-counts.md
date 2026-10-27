---
name: grid-words-and-counts
description: How a grid word is sent and read, the HOLD and billing traps, every count the owner approved with what was sent (state at the newest status read, 2026-10-27 04:08 UTC); nothing is sent while the Panjabi priority holds
metadata:
  type: project
---

Nothing goes to the grid until the owner says otherwise ([[priority-panjabi-first]]); the approved counts below wait for their item.

- Send: dispatch https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid-accounts.yml on main with action `job` (never `log`), job `schwingnet-<word>` (status, anomaly-<stage>, bench-<name>, realism-<stage>, bordercall-<stage>, census-tiers, fetch-<row>, cancel-<slurm id>, update) and a request id of your own; one dispatch per word. Read the answer on symphony-template's branch grid: `git fetch origin +refs/heads/grid:refs/remotes/origin/grid`, then logs/job-<job>.json.
- Before any send read logs/job-schwingnet-status.json there; send the status word only when a stage needs a fresher read, never twice for one read. Newest read 2026-10-27 04:08 UTC: 17,596.87 GB used of 21,990.23 GB, 4,393.36 GB room, 0 owed, DRR seg job 40799505 running on voh5. (The 05:36 UTC record there is the artifacts sync, not a job.)
- HOLD: a live bench or anomaly job writes grid/logs/HOLD, so later words run unpulled at the held commit; after an end or a cancel send one status word first, then the real word.
- A word that failed unstarted on billing never ran and may be sent once more.
- `update` brings the gate's hpcworker clone to hpcworker main; last sent 2026-10-25 23:41 UTC (installed hpcworker #49, every anomaly stage). It is needed once before the first bordercall word (hpcworker #50 merged after it). No realism word passes hpcworker's grid gate (tools/grid_gate.sh JOBS_RE) until an hpcworker PR admits it, then `update`.

Approved by the owner's word, and sent:
- Anomaly route of #391: 15 jobs, 2 CPU and 13 GPU, no fetch (2026-10-25 21:22 and 22:30 UTC). Sent 2: select 2026-10-25 23:42 UTC (Slurm 40785048, exit 0, 1,004 CTs); timing 2026-10-26 00:16 UTC at 074e3bf (Slurm 40785227, FAILED after 30 min 32 s, exit 1, node voh3, report logs/ANOMALY-timing.md unread). Resending timing prints the report and requeues it (same code); pack waits for a timing exit 0 (handoff in [[paused-threads]]).
- #391 item 13's test: 1 GPU + 1 CPU, every setting in one job (2026-10-25 20:49 UTC); unsent.
- FleXray and xvr benchmark reruns on DeepFluoro: approved 2026-10-25, fixes on main, unsent, no thread holds them.
- bordercall: 2 CPU (2026-10-25 about 23:56 UTC), pilot then full only if the pilot's countable count is above 0; unsent; belongs to bordercall TODO.md item 5.
- DRR comparison: 2 fetches + 2 GPU (2026-10-26 about 01:19 UTC). Fetches moose_weights (40788796) and hf_flexray_data (40788810, 19 GB) landed 2026-10-26. Seg word sent four times: 40790826 failed (no module fxr, fixed by #414), 40799410 and 40799494 cancelled, 40799505 sent 2026-10-27 03:40 UTC at 6b2daf4, kept running on the owner's word of 04:31 UTC; whether the others spent the count is the owner's to say. Gap job unsent: once, after the seg job ends well, on the merged mask-free code.
- Flux realism: 5 fetches + 4 GPU (2026-10-26 about 01:58 UTC): aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB), hf_flux2_klein_4b, hf_flux2_klein_base_4b, hf_flux2_klein_9b after the owner's licence click; then realism edit, stats, lora, eval, each once in turn. None sent; FluXray itself landed through the DRR thread and is never fetched again.

Not counted (ask once, as a decision card, when the work comes back): the production SPINEPS array (with the timing estimate), the tier census (1 CPU), scoring the naming rule on real segmentations, the rest of the #391 audit (1 fetch, 5 GPU, 3 CPU), the six 20-epoch trials and SchwingNet #385.

**Why:** the owner's count is the whole permission; a word sent twice, before its code is on main, or under a HOLD breaks it.
**How to apply:** record every send here with its time and Slurm id.
