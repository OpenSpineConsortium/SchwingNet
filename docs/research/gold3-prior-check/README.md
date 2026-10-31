# The gold tier 3 prior check

Source: the thread "Train on randomized spine phantoms", 2026-10-31 (a design workflow with three critiques at 06:40 UTC, then a spec and a reading guide by 09:13 UTC). Status: designed and critiqued, not built, not run. The build stopped when the account hit its weekly limit; one partial module and the scratch it rests on are in docs/checkpoints/2026-10-31-gold4-xray-prior/scratch/.

## What was found

- The prior's measure part (R_measure, bordercall records/prior-2026-10-31) is a level-whitened quantity of a separable (Kronecker) fit, not the same-level correlation of two measures, so it cannot be read as how the two end plates move together.
- The separable form explains at most a third to a half of the gap between its within-vertebra correlations and the literature's 0.76 to 0.99. The measures themselves are joint leading suspects, with a whole-spine shared factor: rim-to-rim widths that read 9 to 10 mm wide, the neck cut of the body, two-layer slabs on 3 to 5 mm slices, and site and protocol offsets.
- The generator's per-column size factor (bordercall schwingcheck/columns.py, scale_sd 0.07) counts size twice on top of a fitted prior, and correlation.py's docstring, which says a draw keeps every cell's mean and SD, is wrong when it is on.
- Nothing in production draws from the prior. In a reduced copy, run_naming's primary answer (no k up to 6 names at 0.90) was the same with the plates coupled at 0.8.
- So the measure part stays held; the level part (levels one apart at 0.49 to 0.64) stands.

## The design

- SPEC.md: the diagnostic job, grid/prior/prior_check.py beside gold3_prior.py under the gate word `morphometry prior`, its sections S0 to S15, its line formats under the report's shape rules, the tests, the vendoring of bordercall schwingcheck/columns.py at 8ae5db9, and what is deferred (covariates, model choice) with the open questions.
- READING.md: how its lines are read, the bands calibrated on matched truths; to be frozen by its sha256 before the first send.
