# Handoff: the SPINEPS to FleXray anomaly route of #391, at the checkpoint of 2026-10-27 04:47 UTC

Source: the thread "Plan the FleXray audit for #391" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written at the owner's checkpoint of 2026-10-27 04:47 UTC ("YO PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF!"). It replaces docs/checkpoints/2026-10-26-morning/anomaly-route.md, which still holds the stage plan word for word; where the two differ, this page holds. The route's design and record are docs/research/spineps-anomaly-route.md; the public plan is symphony-template's docs/research/flexray-audit-plan-2026-10-25.md and its confidential companion docs/research/flexray-audit-companion.md here.

## 1. Where the route stands

| Stage | Class | Code | Grid |
| --- | --- | --- | --- |
| select | batch | #398, merged 2026-10-25 | sent 2026-10-25 23:42 UTC, Slurm 40785048, exit 0: 1,004 CTs, 890 for training and 114 COBRA test-only (logs/job-schwingnet-anomaly-select.json on symphony-template's branch grid) |
| timing | gpu | #403, merged | sent 2026-10-26 00:16 UTC at commit 074e3bf, Slurm 40785227. The status read of 2026-10-27 04:08 UTC lists it as FAILED after 30 min 32 s, exit 1, on node voh3. Its report, logs/ANOMALY-timing.md on the grid, is not read yet, so why it failed is not known |
| pack | batch | #410, merged 2026-10-26 03:11 UTC | not sent; the gate refuses it until a timing report ends in exit 0 (anomaly_inputs_missing in grid/gate.sh) |
| render, figure, tune, eval | gpu | not built | not sent |
| tune_f1 to f4, eval_f1 to f4 | gpu | not built | not sent; only after the main tune and eval look sane |

The owner's count for the route is 15 jobs, 2 CPU and 13 GPU, no fetch (2026-10-25 21:22 and 22:30 UTC). Two are sent, and the second failed. The production SPINEPS array, every selected CT that lacks a mask, has no count; the timing report's estimate goes to the owner once, as a decision card, before anything of it is sent.

Nothing of this route was sent between the two checkpoints. The thread stopped at 2026-10-26 03:25 UTC and was idle until now. From about 21:00 UTC on 2026-10-26 to 03:10 UTC on 2026-10-27 no GitHub Actions job in the organization started, for a billing limit the owner then raised (project-memory/actions-billing-block-2026-10-26.md), so no grid word could have been sent in that window anyway.

## 2. What the next session must know before it sends the timing word again

- Sending `schwingnet-anomaly-timing` again does two things at once. It prints the failed report, and, because the report names commit 074e3bf and the gate's checkout has moved since, it queues the stage once more at the checkout's commit (word_anomaly and bench_failed_on_older_code in grid/gate.sh). The gate treats a failed stage as having decided nothing, so the rerun is the same stage's one job of the count, not a new one; still, say so to the owner in the same reply.
- If the report shows a fault in the code rather than the node (a traceback in tools/anomaly_timing.py or grid/anomaly.sbatch, a missing input), cancel the queued rerun at once with the word `cancel <job>` (grid-accounts.yml, action job, word `schwingnet-cancel-<job>`), fix the fault by pull request, merge it, send `update`, and send the timing word again. If it shows exit 4 (a Blackwell node the spineps environment's torch cannot use), the rerun the gate queued is the right answer and nothing else is sent.
- While the DRR comparison thread's segmentation job (bench_flexray_drr_seg, Slurm 40799505, running on voh5 at 04:08 UTC on 2026-10-27, a 12-hour limit) holds grid/logs/HOLD, the gate's checkout stays at 6b2daf4. That commit carries the pack stage and everything this route has merged, so a rerun queued then runs the current route code. Read the status record first and send nothing while that record is older than the last send, as always.

## 3. The next session, in order

1. Read SchwingNet's board, then logs/job-schwingnet-status.json on symphony-template's branch grid. The newest read is 2026-10-27 04:08 UTC (request drr-status-0407-d14v3r): 4,393 GB of room, nothing owed, the DRR segmentation job running. Send the status word once if that record is older than the last send to the grid.
2. Send `schwingnet-anomaly-timing` once and act on its report as section 2 says. Once a timing report ends in exit 0, put its estimate (median seconds per CT, the CTs still lacking a mask, the hours and array tasks) on a decision card for the production SPINEPS array's count, and send nothing of that array before the answer.
3. Once a timing report ends in exit 0, send `update` (so the gate's hpcworker clone knows the pack word; #410's word reached main after the last `update`) and then `schwingnet-anomaly-pack` once, and tell the owner. The pack admits itself under the size rule before a byte lands; exit 5 in its report means the rule refused the room, and the next send queues it again.
4. When the pack stage's code next changes, take the VerSe alphabet from src/schwingnet/segmenters.py, which is on main since #401 merged (5303418): tools/anomaly_pack.py still spells it itself, L6's id 25 included, and the DRR comparison thread asked on 2026-10-26 at 11:12 UTC that both read one table. It is not needed before then.
5. Build the later stages one pull request each, every job sent once its code has merged and the stage before ended well: render (fxr-render over the two packages; copy the validation draw's digest into data/splits/anomaly-validation.json as its comment says), figure (Benzel-style line figures from recorded inputs, the code committed), tune (FleXray's fine-tune on schwingnet_spine, with schwingnet_spine_partial under a loss that learns no absence from a partial mask), eval (the held-out anomaly truth, reported apart by collection), then the four folds of tune and eval only after tune and eval look sane. The route note's section 5 lists each stage's inputs and words; the design the later stages build on is docs/checkpoints/2026-10-26-morning/pack-stage-design.md, sections 7 to 11, and project-memory/anomaly-pack-stage-design.md.
6. The owner's rules that shape every stage stay as before: only full-spine CTs countable from C2 to the pelvis are ground truth (2026-10-26 00:16 UTC); SPINEPS for production reusing the masks on the grid, MOOSE only to replicate FleXray's own dataset, the segmenter a configurable block (00:17 and 00:26 UTC); figures in Benzel's style from committed, runnable code (01:17 UTC). The owner's newer gold and silver tiers (2026-10-27 03:06 UTC, project-memory/corpus-tiers-census.md) decide which corpora a power figure may count; the tiers thread owns them.
7. Folded into this thread with no count: the six 20-epoch trials and #385, the scaling study. Ask the owner once, as a decision card, only if either becomes necessary.

## 4. Where the thread's files are

- Merged: #398, #403, #407, #410, #412 (docs/checkpoints/2026-10-26-morning/); symphony-template #488, #491 and #498 (the restart page of 2026-10-26); hpcworker #49.
- This page and the folder around it: the pull request from branch claude/project-thread-x16ebc that adds docs/checkpoints/2026-10-27-morning/, until it merges.
- Not in git: the FleXray paper's LaTeX source, which the owner uploaded at 2026-10-26 00:28 UTC (arXiv 2609.26756v2); the facts the stages need from it are docs/checkpoints/2026-10-26-morning/flexray-paper-facts.md. A thread that needs the whole paper asks the owner to upload it again, once.
