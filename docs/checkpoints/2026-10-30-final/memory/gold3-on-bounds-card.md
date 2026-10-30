---
name: gold3-on-bounds-card
description: Gold tier 3 covariates join (job 40878978) scored on the bounds card; pedicle failures are the pre-PR-44 engine, disc failures unexplained; what waits on greg.
metadata:
  type: project
  modified: 2026-10-30T14:46:54.416Z
---

The gold tier 3 covariates join (SchwingNet gate word `morphometry covariates`, job 40878978, 2026-10-30, the one CPU job greg counted at 08:55 UTC) is spent. Its report (aggregates only) is committed at bordercall research_notes/synthetic-validation/records/gold3/report.txt and scored by synthval/gold3.py on PR 38's branch claude/project-thread-o3ng22-all-measures.

Result (at 40 people a cell): autoPET 857 adults and TotalSegmentator 133 pass means and SDs, fail steps (0.79, 0.83 against 0.89). Body and end-plate steps pass; disc and pedicle steps fail. Pedicle failures (T10-T12 and from L3 down) are the engine's known defects: the join ran the engine pinned before bordercall PR 44's pedicle rework. Disc failures (step to L4-L5, T10-T12) have no known engine cause; L4-L5 discs narrow fastest with age, so they may be the cohort. Sex sign kept at 127 of 130 cells; size under-covered (79% and 81% inside). VerSe got no sex.

**Why:** greg asked (03:38 UTC) whether the literature can bound a generator; real cohorts measured by the same engine are the test.

**How to apply:** do not resend the covariates job without greg's new word (COVARIATES_RERUNS is his). Re-running the join on the engine with PR 44's pedicles, and scoring disc steps within age bands, are grid work on greg's word and count. On 2026-10-30 14:39 UTC greg said every session should finish what it is on and stop, so one session can resynthesize and plan ([[greg-patient-sex-is-known]], [[threads-talk-to-each-other]]).
