---
name: dl-jobs-run-on-metaflow
description: greg's standing rule of 2026-10-29 02:39 UTC - every deep learning job on the grid runs on his block-based Metaflow pipeline, under a frozen PREREG, with the REFORMS/CLAIM report enforced and a browser progress page
metadata:
  type: feedback
  modified: 2026-10-29T02:39:34.258Z
---

2026-10-29 02:39:01 UTC, greg, on finding the Flux realism stages ran as plain Slurm jobs (grid/realism.sbatch) outside his Metaflow pipeline: "dude wtf was the point of me making that pipeline if you arent using it! that should be a fucking requirement for all deep learning jobs i run on the grid". The coordinator added it to the project instructions.

The rule: every deep learning job sent to the grid runs as a Metaflow flow of SchwingNet's block-based pipeline (flows/, started by flows/launch.py, blocks named as tools/train.py's --block KEY=VALUE are), under a PREREG.md frozen and hashed before the run, with the REFORMS/CLAIM report enforced (the DRR domain-gap study's pattern: PREREG, DEVIATIONS, timestamped run log, CLAIM report, check-recorded), and with an HTML page that shows the run's progress in the browser.

**Why:** he built the pipeline so every run is reproducible, resumable and auditable; a job outside it is a run he cannot trust or reproduce.
**How to apply:** before any GPU or training word, check the stage is a Metaflow flow with a frozen PREREG and the CLAIM checks; if not, port it first and hold the job. Data fetches are not deep learning jobs and may go first. First case: the Flux realism edit and stats stages ([[flux-realism-restart]]), held until realism is a flow.
