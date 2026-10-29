---
name: metaflow-words-port
description: Where moving every grid DL word onto launched Metaflow flows stands at the 2026-10-29 17:25 UTC checkpoint, which words are done, what the draft PR holds and what is decided for bench, anomaly timing and the gate refusal
metadata:
  type: project
  modified: 2026-10-29T17:27:07.766Z
---

The thread "Require Metaflow for every grid DL job" (SchwingNet) put greg's rule of 02:39 UTC into code one gate word at a time: a flow flows/launch.py starts (flows/registry.txt), a frozen PREREG, the CLAIM/REFORMS report checked at the end, a progress page.

- Done and merged: the DRR study and its MOOSE step (#461), version 1's `start`/`v1` (V1Flow, #464, squash fade5aa, 15:47 UTC).
- On the draft PR of branch claude/project-thread-ugyqtg (opened at the checkpoint, 17:2x UTC, unfinished): `experiment <issue>` (ExperimentFlow, commit 458e6ea) and `latency` (LatencyFlow, parts gpu/cpu/sweep, commit 36ea8cf), every test passing. Its handoff is docs/checkpoints/2026-10-29-metaflow-words/HANDOFF.md: seven review findings on the experiment port with a decided fix each (the big one: a request naming another architecture gets the ResNet-18 file and the trainer refuses it; decided to refuse such a request in words before any frame is read), the latency review not reported, the decided shape of the bench port (kind bench, PREREG docs/research/public-benchmarks/ with Covers, driver+body script like drr-seg.sbatch, a report study "public-benchmarks" in tools/report.py), of anomaly timing (split into grid/anomaly-timing.sbatch, kind anomaly_timing, no CLAIM report, SPINEPS run inside the container) and of the gate's refusal of any gpu-class script the registry does not name.
- greg asked one PR per word; the branch carries two words because it is the thread's one branch. Nothing was sent to the grid.

**Why:** the next session must not redo the two ports, re-review from scratch, or re-decide the bench and anomaly shapes.
**How to apply:** read the handoff first, apply its section 3, then its section 4 in order. See [[dl-jobs-run-on-metaflow]], [[repo-mechanics]], [[grid-words-and-counts]].
