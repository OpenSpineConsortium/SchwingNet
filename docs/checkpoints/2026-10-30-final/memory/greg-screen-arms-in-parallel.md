---
name: greg-screen-arms-in-parallel
description: greg's rule of 2026-10-30 02:46 UTC for the auto-anatomist arms: fit the block-style Metaflow pipeline, then screen as many arms as possible in parallel on short 50-epoch runs for feasibility, before any long run
metadata:
  type: feedback
  modified: 2026-10-30T02:49:51.182Z
---

greg, 2026-10-30 02:46 UTC (thread "Plan evaluating latent shape priors against explainable metrics"), asked seven design questions: "i have no idea / whatever you do just make sure it fits into the block style metaflow pipeline and then you can just evaluate as many in parallel as possible on short 50 epoch runs that will give you some idea of the feasability of each or at least evaluate the performance".

**Why:** he will not pick arms or bars by hand; he wants every candidate head, prior and feature set as a block value of bordercall's autoanatomist, run as one plan of SchwingNet's launched Metaflow flow, and compared side by side on short runs before anything long is sent.

**How to apply:** design questions on the arms are the thread's to settle and record (bordercall research_notes/latent-shape-prior-evaluation/README.md section 12 lists the decisions taken in his place); every arm is a KEY=VALUE block; a screen stage (one plan, a Metaflow foreach over trials, 50 epochs each, one seed, a training subset, validation only, one GPU array job) comes before the full run; the full run takes what the screen keeps and reads the test persons once. The job counts still wait for his word and number (see [[owner-rules]]). The block interface was put to the auto-anatomist thread, which owns SchwingNet PR 483's flow.
