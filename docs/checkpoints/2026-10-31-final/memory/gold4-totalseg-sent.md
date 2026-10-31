---
name: gold4-totalseg-sent
description: the gold 4 TotalSegmentator chain sent 2026-10-31 04:00 UTC (array 40902775, merge 40902777), where its records land, and what is still open about it
metadata:
  type: project
  modified: 2026-10-31T05:06:00.000Z
---

2026-10-31 04:00 UTC, thread "Train on randomized spine phantoms" (symphony_3), on greg's word of 00:55 UTC: the gate word `totalseg gold4` (grid-accounts.yml job schwingnet-totalseg-gold4, request gold4-send-1) ran at SchwingNet main 89bac53 (#523). Array 40902775 (16 GPU tasks, up to 1,328 CTs, 0 label maps before it) and merge 40902777 afterany it, under /rs/rs_grp_oschome/go2432/gold4-totalseg/chains/40902775. Plan: SchwingNet docs/research/gold4-totalseg/PREREG.md (frozen, sha256 16850555...).

- Records when the merge ends: /rs/rs_grp_oschome/go2432/gold4-totalseg/records.jsonl (labels/, units/ beside it; owner-only folder). The pipeline thread ("Build NMDID segment-and-encode pipeline") was told the path and asked to chain afterany 40902777; tell it again when the merge ends.
- Reading the result: send the word again. While the jobs last it prints each task's last line; after, it prints logs/TOTALSEG-gold4.md and queues another chain only where the report does not end in exit 0 and the last send made headway.
- Open: greg was asked (03:31 and 04:01 UTC) whether he would rather reuse the census's arm A September maps; a yes means cancel 40902775 and 40902777 (job schwingnet-cancel-<job>) and a DEVIATIONS.md entry. The run departs from his 2026-09-27 census rule "recycle the census segmentations" on his later word, and the PREREG says so.
- Recorded: SchwingNet docs/research/gold4-totalseg/DEVIATIONS.md item 1 (PR #526, 05:00 UTC, before any record was read): part 3's "every corner voxel within 0.01 mm" is checked per axis (at most 0.017 mm straight-line), which changes no result. Later departures go below it; the file only grows.

**Why:** a later thread can read or resume this run without asking greg what was sent.
**How to apply:** use concordant units by default; held_out (C-ArmLSpine and every real_frames=1 CT or person, COBRA and SpineSAC among them) is never trained on. Related: [[totalseg-rerun-fix-505]] [[ctsp-not-a-trusted-reference]]
