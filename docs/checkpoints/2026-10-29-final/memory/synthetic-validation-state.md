---
name: synthetic-validation-state
description: The synthetic validation note (bordercall PR 29, first part) and the all-106-measures extension (its own draft PR), checkpointed on f's word at 17:22 UTC 2026-10-29; the handoff is HANDOFF.md on the extension branch
metadata:
  type: project
  modified: 2026-10-29T17:33:40.606Z
---

bordercall research_notes/synthetic-validation/: the generator's synthetic spines held to the clinical reread's papers. Checkpointed 2026-10-29 17:45 UTC on f's words ("push all work and checkpoint and write handoffs now"; "stop all adversarial review and push").

- First part (Panjabi's 32): branch claude/project-thread-o3ng22, draft PR 29, head 83c70e5. Code, records, figures and README finished; records deterministic but RECORD.json; tables check passes; every bordercall suite passed (root 292 has one flaky Monte Carlo test, main's code). Left: prose corrections from the fourth check (listed in HANDOFF.md; two applied), then tables check, suites, mark ready, merge on standing permission. Not merged on purpose: 18 corrections were unapplied when f said stop.
- Report page (private): https://claude.ai/artifact/H82v6B1drWmpjTJhrWrLxv, built by report/build.py (now in git on the extension branch) from the README; republish to the same URL after the corrections; behind the README by two sentences and build.py's F3/F4.
- Second part (all 106 measures of the reread; f's ask of 15:18 UTC): branch claude/project-thread-o3ng22-all-measures, a draft PR; code and snapshot (main 6409164, 4,357 rows) committed, run_all.py never run, no tests, records, figures or README yet. Tables: A Panjabi 42 measures/782 cells, B papers 53/694 (292 Tan-only), C both 75/1,054; 46 of 106 keys have usable series.
- A reread fix for series.csv n-faults is coming; re-cut the snapshot (papers_table.write_snapshot_all) before the final run.
- Every record rerun is deterministic except RECORD.json (hashes every .py), so any code edit means run.py (about 30 min) and figures.py again.
- The venv for bordercall's suites needs pymc-extras==0.15.1 (pinned in requirements-schwingcheck.txt).

**Why:** f ranked the Bayesian-generator and data evaluation threads first (12:06 UTC 2026-10-29) and then checkpointed everything at 17:22 UTC.
**How to apply:** read HANDOFF.md on the extension branch first; finish PR 29's prose and merge it, then the extension; see [[clinical-reread]], [[hold-lifted-2026-10-29]], [[owner-working-style]].
