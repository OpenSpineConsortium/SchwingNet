# Handoff: the SPINEPS to FleXray anomaly route of #391, at the checkpoint of 2026-10-26 03:00 UTC

Source: the thread "Plan the FleXray audit for #391" in the claude.ai project symphony (chan_014WUU19NHgHPhf7QetT9cbS), written at the owner's checkpoint of 2026-10-26 03:01 UTC ("please push as much as possible now im running out of tokens then write a handoff for checkpointing asap!"). The route's design and record are docs/research/spineps-anomaly-route.md; the public plan is symphony-template's docs/research/flexray-audit-plan-2026-10-25.md and its confidential companion docs/research/flexray-audit-companion.md here. This page says only where the route stands and what the next session does, in order.

## 1. Where the route stands

| Stage | Class | Code | Grid |
| --- | --- | --- | --- |
| select | batch | #398, merged 2026-10-25 23:40 UTC | sent 23:42 UTC, Slurm 40785048, exit 0: 1,004 CTs selected, 890 training and 114 COBRA test-only (the report is logs/job-schwingnet-anomaly-select.json on symphony-template's branch grid) |
| timing | gpu | #403, merged | sent 2026-10-26 00:16 UTC, Slurm 40785227; its report is not read yet |
| pack | batch | #410, merged 2026-10-26 03:11 UTC (main 49df713) | not sent |
| render, figure, tune, eval | gpu | not built | not sent |
| tune_f1 to f4, eval_f1 to f4 | gpu | not built | not sent; only after the main tune and eval look sane |

The owner's count for the route is 15 jobs, 2 CPU and 13 GPU, no fetch (2026-10-25 21:22 and 22:30 UTC): select and pack are the CPU jobs; timing, render, figure, tune and eval the first five GPU jobs; the eight fold jobs the rest. Two are sent, thirteen are not. The production SPINEPS array, every selected CT that lacks a mask, has no count: the timing report's estimate (median seconds per CT, the CTs still lacking, the hours and array tasks) is what a decision card to the owner carries, once, before anything of it is sent.

The owner's rules that shape the stages from here (2026-10-26, word for word in project-memory/): only full-spine CTs countable from C2 to the pelvis are trusted as ground truth (00:16 UTC), so CTSpinoPelvic1K's training rows are uncounted and the holdout's CTSP persons are reported apart; the production segmenter is SPINEPS, reusing the masks on the grid, MOOSE only to replicate FleXray's own dataset, the segmenter a configurable block and the label-scheme difference handled everywhere (00:17 and 00:26 UTC; the DRR comparison thread owns the block, src/schwingnet/segmenters.py on #401); figures in Benzel's style from committed, runnable code (01:17 UTC).

## 2. What #410 built

The pack stage: tools/anomaly_pack.py (rows, guard-list, size, rewrite, split, trainval, manifest), tools/nifti_label.py, grid/flexray/configs/{protocols,models}/schwingnet_spine_v1.yml, grid/venv.sh, the pack branch of grid/anomaly.sbatch, the gate's pack word, data/splits/anomaly-validation.json, docs/memory/the-anomaly-pack.md, 183 tests. The design it was built from is pack-stage-design.md beside this page; the decisions a later stage builds on are in project-memory/anomaly-pack-stage-design.md: whole volumes, two packages under the landing flexray_pack (schwingnet_spine, schwingnet_spine_partial), 28 canonical ids, countable and complete measured per CT, the frozen validation rule, no HOLD. The pull request's body carries the adversarial review; its one correction here: the room at the last status read (2026-10-25 23:41 UTC) was 4,416 GB, not the 8.8 TB the body's census line says, which was the test's stand-in figure; the census of a few hundred gigabytes still fits, and the size rule decides.

## 3. The next session, in order

1. Read SchwingNet's board. #410 merged at 03:11 UTC, so main carries the pack stage; #412, this folder, merges on its own once green, and a red check on it is fixed on the branch claude/project-thread-x16ebc and pushed once.
2. Read the grid's status record, logs/job-schwingnet-status.json on symphony-template's branch grid (last read 2026-10-25 23:41 UTC, nothing live, 4,416 GB free). Send the status word (grid-accounts.yml, action job, job schwingnet-status) once if that record is older than the sends above, which it is.
3. Send `schwingnet-anomaly-timing` once more to read the timing report, logs/ANOMALY-timing.md, as the send of 00:16 UTC said. If the report ends in exit 4 (a Blackwell node, which the spineps environment's torch cannot use), send it once more; the gate queues the stage again at the same commit. Put its estimate on a decision card to the owner for the production SPINEPS array's count, and send nothing of that array before the answer.
4. Once #410 is on main and the timing report ends in exit 0, send `update` (so the gate's hpcworker clone knows the pack word) and then `schwingnet-anomaly-pack` once, and tell the owner. The gate refuses it naming what is missing if G3's split (~/split_final.json), the selection or conda are not where the defaults say; a path fix is one line in grid/gate.sh and grid/anomaly.sbatch. The pack admits under the size rule before a byte lands; exit 5 in its report means the rule refused the room, and the next send queues it again.
5. Build the later stages one pull request each, every job sent once its code has merged and the stage before it ended well: render (fxr-render over the two packages; copy the validation draw's digest into data/splits/anomaly-validation.json as its comment says), figure (Benzel-style line figures from recorded inputs, the code committed), tune (FleXray's fine-tune on schwingnet_spine, with schwingnet_spine_partial under a loss that learns no absence from a partial mask), eval (the held-out anomaly truth, reported apart by collection), then the four folds of tune and eval only after tune and eval look sane. The route note's section 5 lists each stage's inputs and the words.
6. Folded into this thread with no count: the six 20-epoch trials (at most one GPU job, only if the plan needs SchwingNet's own baseline) and #385, the scaling study. Ask the owner once, as a decision card, if either becomes necessary.

## 4. Where the thread's files are

- Merged: #398 (holdout, folds, select), #403 (timing), #410 (pack, 03:11 UTC), #407 (docs/research/full-spine-corpora-with-reader-counted-variants.md, the owner's question of 22:31 UTC answered), symphony-template #488 and #491 (the plan and the word's pass-through), hpcworker #49.
- Open: #412, this folder.
- Not in git: the FleXray paper's LaTeX source, which the owner uploaded to the project at 00:28 UTC (arXiv 2609.26756v2, 19.9 MB); the facts the stages need from it are flexray-paper-facts.md beside this page. The cloud sessions cannot reach arxiv.org, so a thread that needs the whole paper asks the owner to upload it again, once.
