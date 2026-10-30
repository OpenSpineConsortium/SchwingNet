---
name: greg-count-covariate-join
description: greg's word and count of 2026-10-30 08:55 UTC: one CPU grid job joining the gold tier 3 morphometry rows with each person's sex and age, sent after the VerSe morphometry job ends
metadata:
  type: project
---

greg, 2026-10-30 08:55 UTC (thread "Continue Bayesian synthetic validation"), tapped "1 CPU job after VerSe ends" on the card "Send one CPU job joining the morphometry rows with each person's sex and age?". The card's option read: the join (autoPET headers, VerSe and TotalSegmentator tables) is sent once VerSe's rows land, and only counts, means and SDs leave the grid.

**Why:** every grid job needs his word and the number of jobs ([[owner-rules]]); this is both, for exactly one CPU job.

**How to apply:** the job is SchwingNet's `morphometry covariates` (grid/morphometry-covariates.sbatch, tools/gold3_covariates.py), built on branch claude/project-thread-f81hh9 and merged by pull request before the send; send it only after morphometry verse (job 40877151, sent 08:25 UTC) has ended with exit 0; a second job, a rerun or a fetch for missing demographics needs a new count. See [[greg-patient-sex-is-known]].
