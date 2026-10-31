---
name: correlation-prior-2026-10-30
description: the gold tier correlation prior (bordercall #50 code, fitted on the grid 2026-10-31, records/prior-2026-10-31), its refit on the finished morphometry rows, and what is still open about it
metadata:
  type: project
  modified: 2026-10-31T06:49:17.402Z
---

greg, 2026-10-30 21:44 UTC (thread "Train on randomized spine phantoms"): use the gold tier only for population priors with correlations between levels, and train on phantoms with known random parameters plus learned real noise. He chose "Prior only for now" at 22:47 UTC.

- Code: bordercall #50 (8ae5db9), schwingcheck/correlation.py: a matrix normal (level corr kron measure corr, flip-flop MLE, 5% shrink), used as `draw_columns(correlation=prior)`; the default stream is bit-identical. The generator's own assumption is levels at 0.25, measures at 0.
- Fitted on the grid by the gate word `morphometry prior` (SchwingNet grid/prior/gold3_prior.py): job 40902475 at 02:36 UTC, recorded in bordercall records/prior-2026-10-31/ (#64, 2cc9971). ENHANCE.PET 693 whole spines (C3..L5), TotalSegmentator 67, VerSe too few to fit; held-out gain 13.78 nats a spine (SE 1.34) for ENHANCE.PET.
- 05:15 UTC: the morphometry thread said all reruns were in on one code stamp (enhance 40900765, verse 40902026, covariates 40902924). The refit, job 40903052 at SchwingNet 386b407, reproduced the 02:36 report line for line, so the recorded prior stands on the finished rows.
- Gate quirk: the word refits whenever main's commit moved, not only when the prior's code changed, so every read after a merge queues another 10-second CPU fit (job 40903082 was one). Harmless but wasteful; fix by judging the prior's files, as GOLD4_CODE does for gold 4.
- 06:40 UTC, the within-vertebra question (design workflow plus three critiques): R_measure is a level-whitened separable quantity, not the same-level correlation, so it cannot be read as how the two plates move together. The Kronecker form explains at most a third to half of the gap to the literature (0.76 to 0.99); the measures themselves (rim-to-rim widths 9 to 10 mm wide, the neck cut, two-layer slabs on 3 to 5 mm slices, site/protocol offsets) are joint leading suspects with a whole-spine shared factor. The generator's per-column size factor g (scale_sd 0.07) counts size twice on top of a fitted prior. Nothing in production draws from the prior; in a reduced copy run_naming's primary answer (no k up to 6 reaches 0.90) is the same with plates coupled at 0.8. Keep the measure part held. A trimmed diagnostic job (grid/prior/prior_check.py, docs/research/gold3-prior-check/) is being built in SchwingNet, to be sent with `morphometry prior` once Actions runs again.
- FleXray had no real spine images in training (47.5% rendered CTs, 37.5% FluXray, 4% real radiographs, none of a spine).
- The phantom (autoanatomist/phantom.py) draws no ribs, so it cannot show the rib-defined anomaly families.

**Why:** a later thread picks up the prior without re-deriving which fit is current.
**How to apply:** cite records/prior-2026-10-31 as the current prior. Grid jobs need no word since 2026-10-30 23:03 UTC. Related: [[gold4-totalseg-sent]] [[xray-stage-flexray-chain]]
