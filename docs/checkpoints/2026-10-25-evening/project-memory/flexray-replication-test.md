---
name: flexray-replication-test
description: Owner's ask 2026-10-25 22:20 UTC: rendering as a block part and an integration test replicating a statistics-sized sample of FleXray's dataset from the same raw CTs
metadata:
  type: project
  modified: 2026-10-25T22:28:07.415Z
---

On 2026-10-25 at 22:20 UTC, in the thread "Compare FleXray DRRs to real X-ray corpora", the owner asked whether the DRR domain-gap study fits "the nice block schema" (SchwingNet's training blocks, src/schwingnet/blocks.py) and asked for an integration test: replicate the dataset of the FleXray paper by expressing its workflow in the block configuration and selecting the same raw data source, "not the whole thing but enough to calculate statistics".

Answer given: yes. Rendering becomes a block part with FleXray's recipe as one named configuration. The test has three groups in the one GPU job (bench flexray_drr_gap): a replica (our render blocks set to FleXray's recipe), a reference (FleXray's own runtime on the same CTs and pose draws) and FluXray as shipped. It passes when the replica is indistinguishable from the reference. Replica against FluXray measures the FLUX.2 edit, which is not in the fork. FluXray is 1,597 MOOSE 3.0 CTs x 90 poses and MOOSE's sites are unnamed, so the job matches FluXray's subject ids to held CTs after the flexray-data fetch, falling back to TotalSegmentator with a note. Size: 250 CTs x 4 poses a group. Count unchanged: 1 fetch + 1 GPU job.

**Why:** the owner wants evidence that the block pipeline reproduces FleXray's data before building on it.
**How to apply:** keep the render blocks in the training blocks' pattern (names in a pure module, torch side in a table); see [[flexray-fork-facts]] and [[anomaly-route-approved-jobs]] (the audit thread's pack/render route is a separate path).

Checkpointed 2026-10-25 22:40 UTC at the owner's word, mid-build: SchwingNet PR #401 and symphony-template PR #493 (drafts, branch claude/project-thread-7ltron); handoff SchwingNet docs/checkpoints/2026-10-25-drr-domain-gap/HANDOFF.md (copy in /mnt/project-files/handoffs/). Grid wiring not written, renderer untested, nothing sent to the grid.
