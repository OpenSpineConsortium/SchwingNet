---
name: morphometry-pr44-state
description: Morphometry thread handed off at 20:30 UTC 2026-10-30; bordercall draft PR 49 and SchwingNet draft PR 501 are unreviewed; the count of three is held by the owner until a resynthesis
metadata:
  type: project
  modified: 2026-10-30T20:18:00.858Z
---

The thread "Run morphometry on gold tier 3 masks" (project symphony_5) stopped at 20:30 UTC on 2026-10-30. The owner wrote at 20:06 UTC: "write a handoff and checkpoint ... do not more checking just push". So both branches were pushed with no review, no mutants and no check.sh run on their last state.

**Where to start:** SchwingNet docs/checkpoints/2026-10-30-morphometry-lines/HANDOFF.md (on branch claude/project-thread-gv744i until PR 501 merges). Its section 3 gives the steps in order.

**bordercall draft PR 49** (branch claude/project-thread-gv744i, head 3936bcd, over main 48e27f7, which holds the lines export of PR 47):
- morphoview/projection.py copies FleXray 1.0.2's camera on nanoDRR 0.1.5.
- `python -m morphoview project` reads a render manifest, a realism render (--realism --sample --ct) or a view file. With --edits and --filter it gives each FLUX edit's shift and the filter's verdict.
- morphoview/shapes.py: curves, arcs, splines, planes, polygons, volumes, and triangle surfaces with rims and sag.
- 94 tests passed in the plain environment. Still to do: Live with FleXray and torch, mutants, and a review.
- Its handoff is in research_notes/morphometry/handoff.md, entry of 20:30 UTC.

**SchwingNet draft PR 501** (same branch name, head 9d7792e):
- e95e5fa: the pin at bordercall ee495d5. This is NOT on main yet.
- 1c5e76a: the 15 gate fixes (MORPHOMETRY_RERUNS and COVARIATES_RERUNS, kept/<job>/, lost submissions, code-stamp checks, earlier joins).
- df667a1: main 432489a merged in.
- The checkpoint commits.
- The CI run is the first test of this state.

**Two cameras:** bordercall main a87e0b3 also holds autoanatomist/project.py (e751cbc, another thread), which projects onto FluXray's detector under nanoDRR 0.1.7's convention. morphoview/projection.py (PR 49) copies FleXray 1.0.2 on nanoDRR 0.1.5, held to FleXray's own renders. Nobody has checked which nanoDRR SchwingNet's renders use or whether the two agree; they should become one camera before either is trusted.

**Held:** the count of three (enhance, verse, covariates, 14:33 UTC) is unspent. Since the owner's 14:45 UTC hold, there are to be no grid sends, no report reads and no plots until the owner says the resynthesis is done.

**Old jobs:** enhance (Slurm 40872077) and verse (Slurm 40877151) ran the old engine, 16f7b40. Their sagittal angles, inclinations and spinous angles carry the old wall reading. The covariates join was job 40878978.

**Left after the two PRs:**
- Re-vendor bordercall with morphoview.
- Pass --lines in grid/morphometry.sbatch.
- Close bordercall PR 41 (the 16f7b40 tree).
- Tell PR 45's thread ("Plan the evaluation of latent shape priors", branch claude/project-thread-2akdys) through the coordinator.

**Why:** a later thread would otherwise resend a spent grid word, trust old-engine angles, or merge unreviewed work.
