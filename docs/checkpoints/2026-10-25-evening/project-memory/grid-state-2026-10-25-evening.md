---
name: grid-state-2026-10-25-evening
description: Grid read at 19:42 UTC 2026-10-25: five smoke jobs final (A, B done; bank failed at ingest; catalog and C cancelled), bench fetches done, two approved bench reruns unsent, nothing live
metadata:
  type: project
  modified: 2026-10-25T19:46:53.525Z
---

Status word sent once at 19:42 UTC on 2026-10-25 (symphony-template grid-accounts.yml run 230, request smoke-status-1940); readout on branch `grid`, logs/job-schwingnet-status.json, commit e514e7a. Full note: symphony-template docs/research/grid-smoke-and-benchmark-state-2026-10-25.md (symphony-template #487, merged 2026-10-25 20:00 UTC).

- Smoke jobs (SchwingNet fc027a6): 40781593 sweep A synthetic COMPLETED 20 min; 40781617 sweep B real COMPLETED 12 min; 40781621 bank vindr_spinexr FAILED after 20 min, "ingest refused", reason withheld from the readout (in the job's log on the grid); 40781623 catalog and 40781628 sweep C two_source CANCELLED before starting. Of the owner's count (3 GPU + 3 CPU): 2 GPU + 1 CPU ran, 1 GPU + 1 CPU cancelled unstarted, 1 CPU never submitted.
- Benchmark fetches 40780681 (flexray weights), 40780691 (xvr data), 40780696 (xvr models): all COMPLETED. Bench jobs: carmlspine COMPLETED; flexray_deepfluoro and xvr_deepfluoro FAILED; fixes SchwingNet #314 and #387 are on main (f1dcf3c). The two approved reruns (one each) are still unsent as of 19:42 UTC.
- The status word pulls the gate's SchwingNet checkout to main (moved fc027a6 -> f1dcf3c on this call).
- Grid room: 4,416 GB free of the 21,990 GB volume quota (79.92 percent used), 0 running fetches.

**Why:** every thread that plans or sends grid work (the #391 plan, the public-benchmark reruns, the smoke results for SchwingNet #268) must start from this state and not resend the status word. See [[grid-status-word]].

**How to apply:** before any grid send, read logs/job-schwingnet-status.json on branch `grid` first; resend the status word only on the owner's ask. A rerun of the bank needs the owner's word and the ingest refusal's reason from the grid log.
