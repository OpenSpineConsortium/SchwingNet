---
name: greg-job-count-latent-prior
description: greg's count of 2026-10-30 03:20 UTC for the latent-shape-prior evaluation (2 CPU, 2 GPU screen, 2 full run, 1 short GPU smoke, the smoke being the auto-anatomist thread's gold3_latent_smoke); its annealer screen's 2 jobs have his separate yes of 08:56 UTC
metadata:
  type: project
  modified: 2026-10-30T07:14:14.880Z
---

greg, 2026-10-30 03:20 UTC (thread "Plan evaluating latent shape priors against explainable metrics"): "2 CPU 2 GPU 2 Full run plus 1 short GPU smoke is fine". That is the owner's word and number for the jobs of bordercall research_notes/latent-shape-prior-evaluation/README.md section 9: stage 1 export and stage 2 features (CPU), the screen's array and merge (GPU), the full run's array and merge (GPU), and one short gpu-class smoke to measure the step time.

The one short GPU smoke is the auto-anatomist thread's gold3_latent_smoke (SchwingNet PR 483, objective=mask, 4 ENHANCE.PET CTs, two 300-step trials on one card), counted once for both threads. That thread's annealer screen (plan gold3_latent_screen: a GPU array of 8 and a CPU join) is 2 more jobs outside the 03:20 count; greg gave his word for both on 2026-10-30 08:56 UTC ("Yes to both", answering the ask of 07:15), relayed to the auto-anatomist thread. They still wait for that thread's frozen PREREG.

**Why:** every grid job needs his word and the number of jobs ([[owner-rules]]); a job that grows beyond its line in section 9 needs a new count.

**How to apply:** none can be sent yet: they wait on the flow kind, the volume rows with a person key, the windowing, the head block and the frozen PREREG (section 10 of the note). The interactive figure he asked for is pipeline.html beside the note (https://claude.ai/artifact/8mfLZEEQupfs1wnGFKrASc), a Metaflow-style flowchart that also draws the annealer screen. Both runs keep one person split: this evaluation's listed test persons never train in the annealer run. See [[greg-screen-arms-in-parallel]], [[greg-one-network-swappable]].

2026-10-30 14:00 UTC: greg chose on a decision card that the stage 2 CPU job's count also covers the per-cell n, mean and SD the literature bounds check reads (PR 38's bounds card, scored off the grid; README section 7, bordercall commit 926bbcd). No new job.
