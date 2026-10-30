---
name: totalseg-complete-sent
description: The gold tier 3 C2 and sacrum completion (gate word `totalseg complete`) ran as job 40882547 and failed on an import clash (tools/profile.py shadows stdlib profile); greg gave one more GPU job at 16:49 UTC for the fixed rerun.
metadata:
  type: project
  modified: 2026-10-30T16:44:55.838Z
---

On 2026-10-30 at 15:55 UTC the SchwingNet gate word `totalseg complete` queued job 40882547 (one GPU job, voh4 V100, at SchwingNet 2fe153f), the TotalSegmentator and MOOSE completion of C2 and the sacrum for the gold tier 3 CTs that lack them. greg's word and count: "Add sacrum and c2 w total seg", 2026-10-30 08:54 UTC, one GPU job; greg handed the send to the thread "Continue Bayesian synthetic validation" at 14:49 UTC.

It failed at 15:59:25 UTC (exit 1): 38 asked, 37 prepared, all 37 errored with "AttributeError: module 'profile' has no attribute 'run'", 0 targets kept. Cause: tools/gold3_totalseg_grid.py runs as a script, so tools/ is sys.path[0], and SchwingNet's tools/profile.py hides the standard library's profile when TotalSegmentator's imports load cProfile. Other tools strip tools/ from sys.path first (domain_gap.py:99 and five more). ENHANCE.PET 1379 was not prepared: no Vertebrae mask under aws_enhance_pet_labels. The report stands as logs/TOTALSEG-complete.md, so the gate prints it and queues nothing.

Three gates had to know the word: SchwingNet grid/gate.sh (#495), symphony-template's grid-accounts.sh (#510) and hpcworker's tools/grid_gate.sh (#53, then the job word `update`).

**Why:** the first count was one job and it is spent. greg's second count: his tap of 2026-10-30 16:49:40 UTC on "Fix and rerun (one GPU job)", one more GPU job, committed as TOTALSEG_RERUNS="complete:40882547" in SchwingNet grid/gate.sh by the fix's pull request; it is spent once that rerun is queued.

**How to apply:** greg, 2026-10-30 16:59 UTC: "please stop fucking asking me everytime you submit a job to the grid and stop making it a big deal"; so a rerun of work he asked for is sent without asking, and the gate's TOTALSEG_RERUNS line is a code detail, not a question for him. The gate still refuses a second job until TOTALSEG_RERUNS names the job a standing report or record belongs to (or complete:lost after a lost answer; the mark logs/TOTALSEG-complete.sent stands from before a submission until its answer names the job). A resend only reads a standing report whose job the line does not name. The counts go to SchwingNet by a follow-up pull request after a good run ([[gold3-on-bounds-card]]).
