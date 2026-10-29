---
name: autoanatomist
description: The auto-anatomist (bordercall autoanatomist/, merged PR 27) and the owner's asks of 29 Oct 2026 for it as a Metaflow block with search, RL, calibration and the 2-D transfer; where the design is written and what is built
metadata:
  type: project
---

State at the checkpoint of 2026-10-29 17:27 UTC (thread "Build the auto-anatomist on raw CT", stopped on greg's words of 17:22 and 17:27 UTC: push, hand off, no review):
- Built and merged: bordercall autoanatomist/ (PR 27, 14:07 UTC, d778a18): specs, oracle, phantoms, crops, gates, ladder, naming layer, dual encoder, trainer, smoke run (records/autoanatomist-2026-10-29/smoke.json: 38 ms per crop CPU, 2.98 mm, naming 9/12 oracle, 5/12 values alone, 0/12 with the 25 mm uncalibrated spread).
- Built, draft, unreviewed: bordercall branch claude/project-thread-wfwuc2, autoanatomist/project.py (nanodrr 0.1.7 camera to the bit, FluXray's 90 poses, projection of any reading or engine line, readability rules) with 21 tests; its draft PR is open.
- Designed, not built: blocks.py (KEY=VALUE for every training part), session.py (numpy-state resumable session, schedule in absolute steps, calibration of the spread on validation: scale or quantile), SchwingNet flows/autoanatomist.py (ledger-driven search: successive halving, REINFORCE controller, continue/anneal/add-data semantics, W&B ids), gate word `autoanatomist <plan>`, PREREG with Covers, venv_for environment with the jax pins. The full design: SchwingNet docs/checkpoints/2026-10-29-autoanatomist-flow/HANDOFF.md (branch claude/project-thread-wfwuc2, draft PR).
- Salvaged at 17:40 UTC: the prior art (60 entries, 4 groups, unverified) is SchwingNet docs/research/autoanatomist-search/prior-art.md; the measures-to-2d rows (51 of 106 keys, unverified) are bordercall research_notes/measures-to-2d/README.md with the 55 undrafted keys listed; the HPO and RL sweeps and every verify pass did not run (the account hit its weekly limit).

**Why:** greg's asks bind: Metaflow-native (no subprocess trainer, 15:00), all 106 reread measures not Panjabi's 32 (15:13, 15:18), engine constructions projected never a 2-D corner fit (15:16), resumability/status/W&B surviving RL runs with continue and add-data (15:30), calibration of the spread and the w schedule as blocks (17:09 paste).

**How to apply:** build in the handoff's order (bordercall blocks and session first, merge, re-vendor into SchwingNet grid/bordercall with KEEP += autoanatomist, then the flow); no grid job without greg's word and count; the phantom smoke search is the first count to ask for. Related: [[dl-jobs-run-on-metaflow]], [[morphometry-state]], [[repo-mechanics]].
