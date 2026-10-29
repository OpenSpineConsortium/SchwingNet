---
name: bordercall-grid-count
description: The owner's count for the bordercall measurements on the grid (2026-10-25 23:56 UTC): two CPU jobs, a pilot over a few hundred countable SPINEPS masks, then the full corpus; nothing else approved for bordercall
metadata:
  type: project
  modified: 2026-10-25T23:58:32.242Z
---

On 2026-10-25 at 23:56 UTC the owner chose, on a decision card in the thread "Finish CNS slides with junction predictor", **two CPU jobs** for the bordercall measurements over the existing SPINEPS masks on the grid: one pilot over a few hundred countable cases (C2 present), read with the status word, then one job over every countable mask if the pilot's countable count is above 0. No resegmentation; the masks are the ones already on the grid (CTSP ~/bench/spineps/native, ~/bench_ts for TotalSegmentator v2 and VerSe, the anomaly harvest, COBRA).

**Why:** the owner's bordercall prompt (23:48 UTC) says measure a few hundred cases first and stop if countable is 0; the grid rule is one count per word, asked once.

**How to apply:** since the owner's order of 2026-10-27 05:48 UTC both jobs wait for the second item of that order, gold 1/2/3 data ([[next-account-priority-panjabi]]); send nothing before the owner says that item starts. Then: the SchwingNet gate word is `bordercall <stage>` (stages pilot and full), passed through symphony-template's grid-accounts.yml as `schwingnet-bordercall-<stage>`; send `update` after the hpcworker side merges, then the pilot, read the report, and send `full` only after the pilot's report shows countable above 0. A third job needs a new card. See [[grid-counts]] in the index for the other approved counts.
