---
name: autoanatomist-screen-ready
description: the auto-anatomist screen is merged (SchwingNet #483 -> 69371c2); its first smoke (job 40884715) died on a V100 compile, so PR 500 (merged, 432489a) sends every GPU part to galhp's L40S cards and the smoke went again as job 40885678; greg pre-approved sending smoke and screen while he is in the OR
metadata:
  type: project
  modified: 2026-10-30T18:56:12.009Z
---

SchwingNet PR 483 (bordercall PR 40 vendored at afe1952 under grid/autoanatomist/) and bordercall PR 40 were merged on greg's word "Can u merge them wtf?" (2026-10-30 18:03 UTC). SchwingNet main is 69371c2, bordercall main a87e0b3.

greg, 18:05 UTC, going into the OR: "assume I approve of whatever you need to get a training run on gold tier data going for when I'm out, whichever will me the most testable and likely to work". So the session sends the words itself: `autoanatomist gold3_latent_smoke` (one GPU job), and only once that smoke's report ends in `- exit 0`, `autoanatomist gold3_latent_screen` (a GPU array of 8 trials and a CPU join).

First smoke, job 40884715 at 69371c2, 18:26 UTC: it landed on voh5 (gvohp, Tesla V100-SXM2-16GB) and both trials stopped at their first compile, "JaxRuntimeError: INTERNAL: Failed to get configs for: 46 out of 218 instructions" (JAX 0.10.2's GPU autotuner on Volta). Fix: SchwingNet PR 500 sets AUTOANATOMIST_PARTITION=galhp in grid/gate.sh (L40S cards, as alh3 showed in the DRR study's job 40859208), recorded as item 1 of docs/research/autoanatomist-screen/DEVIATIONS.md, and adds the plots' numbers to the join's SUMMARY.md so they come off the grid in the gate's report. The gate resends a plan whose report failed at an older commit by itself (bench_failed_on_older_code); no AUTOANATOMIST_RERUNS entry. PR 500 merged at 19:08 UTC (main 432489a); the smoke was sent again at 19:12 UTC as job 40885678 on galhp (the gate's own resend of a plan that failed on older code). Whether the L40S compiles the trials is not known until that job's report.

The frozen PREREG must never be edited (CI's registry check, flows/stage_registry.py frozen): the second screen's arms (cyclic, adaptive, overlapping rungs, restraint; bordercall PR 48 at 8e966e4) left PR 500 and come back as their own pull request with a NEW PREREG file and its own freeze. The earlier attempt sits in the local branch `local/second-screen-wip` (c15800c) of the session that wrote it, which a new session does not have.

Send through symphony-template's grid-accounts.yml (workflow_dispatch on main, action=job, job=schwingnet-autoanatomist-<plan>); the answer lands at symphony-template branch `grid`, logs/job-<job>.json, about a minute later.

**Why:** a new session must not re-run the reviews, re-ask for the count, or wait for greg to send.

**How to apply:** read the smoke's second report before anything else; keep greg's status short and plotted. A Colab T4 (pre-Ampere, like the V100) may hit the same compile failure in the demo (bordercall PR 48). See [[greg-screen-arms-in-parallel]], [[greg-job-count-latent-prior]], [[demo-ask-2026-10-29]].
