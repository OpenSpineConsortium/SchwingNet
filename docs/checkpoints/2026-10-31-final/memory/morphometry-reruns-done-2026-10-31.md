---
name: morphometry-reruns-done-2026-10-31
description: greg's 14:33 three-job morphometry count is spent; enhance, verse and covariates all reran on code stamp 1cee7ea83e4c28db by 04:48 UTC 2026-10-31
metadata:
  type: project
  modified: 2026-10-31T05:14:21.151Z
---

On 2026-10-31 the morphometry reruns finished on bordercall engine 9c85de1, all under code stamp 1cee7ea83e4c28db. They ran after the resynthesis (SchwingNet #509).
- Enhance: job 40900765, 1,597 studies, exit 0 at 01:19 UTC.
- Verse: job 40902026, VerSe 374 and TotalSegmentator 159, exit 0 at 01:52 UTC.
- Covariates: job 40902924, exit 0 at 04:48 UTC, checked against the earlier join 40878978. 11 autoPET blocks were withheld.

The old reports are kept as logs/MORPHOMETRY-<set>-<oldjob>.md, and the old rows are under morphometry/<set>/kept/<oldjob>/.

The MORPHOMETRY_RERUNS and COVARIATES_RERUNS words are now spent.

Since SchwingNet #514 (merged 01:43 UTC), grid/logs/HOLD has one line per run, so jobs share the pinned checkout instead of waiting for each other.

Still to do:
- plot the old rows against the new
- rescore bordercall #38's card
- refit the #50/#52 prior on the new rows; the phantoms thread was told at 05:15 UTC

Related: [[grid-use-not-restricted]] [[gold-tier-covariates]]
