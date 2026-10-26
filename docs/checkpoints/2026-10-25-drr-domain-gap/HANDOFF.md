# Handoff: FleXray DRRs beside the real X-ray corpora (2026-10-25)

Thread "Compare FleXray DRRs to real X-ray corpora", checkpointed at the owner's word of 2026-10-25 22:35 UTC, mid-build. The design is docs/research/drr-domain-gap/README.md (confidential); the public method and count are symphony-template's docs/research/drr-domain-gap-method-2026-10-25.md. This page says only where things stand and how to restart. Nothing has run on the grid and no fetch or grid job was sent.

## The asks

1. The owner's first ask: plot FleXray's synthetic DRRs beside every held X-ray corpus, plain film and fluoroscopy, in t-SNE and other maps, with the separation tests an ML reviewer expects. Results are confidential and stay in this repository.
2. The owner's second ask (22:20 UTC): rendering as a block part like the training blocks, and an integration test that replicates a statistics-sized sample of FleXray's dataset from the same raw CTs through the blocks. Answered yes in the thread: three groups in the one GPU job, a replica (our blocks at FleXray's recipe), a reference (FleXray's own SegmentationDRRRuntime on the same CTs) and FluXray as shipped; it passes when replica and reference are indistinguishable (the C2ST AUC's lower bound at most 0.6 and the MMD's BH q at least 0.05); replica against FluXray measures the FLUX.2 edit, which the fork does not hold. 250 CTs x 4 poses a group. The count stays 1 fetch + 1 GPU job.

## Done (on the branch claude/project-thread-7ltron)

- data/domain_gap/groups.json: 17 groups (5 synthetic, 3 fluoroscopy, 9 film), each with licence, person rule, cap and a note; the exclusions with reasons are in the README's section 2.
- tools/domain_gap.py: the orchestrator (plan from samples.sqlite, decode, render, three feature spaces, the analysis, an 80-line summary, figures, W&B). tests/test_domain_gap_run.py passes, a whole run on fake corpora included.
- tools/domain_gap_stats.py and tests/test_domain_gap_stats.py: the numerics (grouped C2ST with bootstrap and permutation, MMD, FD64 at equal sizes, KID64, PRDC, silhouette, purity, maps with trustworthiness); 27 tests pass.
- src/schwingnet/domain_gap.py and tests/schwingnet/test_domain_gap.py: the pure module (group specs, the plan, the words). Its writer was stopped while running the gate, so its gate verdict is not known.
- src/schwingnet/render_blocks.py and tests/schwingnet/test_render_blocks.py: the render blocks (hu_window, air_clamp, crop, crop_sampler, pose, isocentre, projection, attenuation, scale, edit; views, detector, ray_samples), DEFAULT is FleXray's MOOSE recipe and PHYSICAL the same with attenuation off; plan_crops and crop_weights copy FleXray's plan_z_crops (max_overlap 0) and inverse_label_frequency_weights (tau 0.5, max). 13 tests, ruff and mypy pass. The gate runs clean but for one line: plan_crops' precondition `1 <= depth <= 100_000` is reported as one CrossHair cannot meet, so either restate it or list it under [tool.beethoven-qa.unproven] with that reason.
- tools/flexray_render.py: the renderer writer's file, stopped mid-way (606 lines, it parses; render_subjects is there). It has no test file yet and is unread by me; treat it as a draft.
- docs/research/drr-domain-gap/README.md, its line in docs/research/README.md, docs/memory/drr-domain-gap.md with its MEMORY.md line.
- symphony-template, same branch name: docs/research/drr-domain-gap-method-2026-10-25.md and its README line.

The commit was pushed with SKIP_GATE=1 (the pre-push hook's own knowing skip, said in the commit message), since the checkpoint came mid-build; CI's gate on the draft is the real verdict.

## Not done, in order

1. Read tools/flexray_render.py whole, finish it and write tests/test_flexray_render.py (skip when fxr is missing); then refactor it to take a RenderBlocks, load the TotalSegmentator v2 masks under MOOSE names (vertebrae_C1 to vertebra_c1, clavicula to clavicle and so on), and add the reference path through fxr's SegmentationDRRRuntime with the MOOSE profile and protocol all_structures_flexray_v4 on fxr's own ct_crops output. Keep the torch side in a tools/render_blocks.py table, one function per block name, as tools/train_blocks.py is for the training blocks.
2. A unittest under tests/ holding plan_crops and crop_weights equal to fxr's own functions (skipIf fxr is missing).
3. Extend the pure module's GroupSpec (extra forbid) with the blocks words, an engine (blocks or flexray-runtime) and subjects_from (fluxray or empty); add the groups flexray_replica (DEFAULT) and flexray_reference to groups.json; flexray_drr becomes PHYSICAL.
4. Add the replication section to the analysis and the summary (replica against reference, against the split-half null; replica against FluXray), with the word "replicated" fixed as above.
5. The grid wiring, never written: grid/bench.sbatch's id flexray_drr_gap (the existing `bench` gate word, no change in symphony-template), grid/gate.sh, tests/test_gate.py, grid/README.md, and grid/run-platform-fetch.sh's hf_flexray_data row; check bench.sbatch's time limit for the larger job. The job builds a venv with --system-site-packages pinning `flexray[train]==1.0.2 nanodrr==0.1.5 scikit-learn==1.9.1 umap-learn==0.5.12 numpy==2.4.6`; only the summary leaves the grid, through grid/redact.sed.
6. Update the confidential README (render blocks, the replication test, MMD calibration by BH q, equal-size FD) and the public method note.
7. Adversarial review (statistics, code, grid rules and redaction) into the PR body, `pixi run --locked lint`, `typecheck`, `test` and `python -m beethoven_qa gate --module schwingnet.domain_gap --report-all` (and render_blocks), the unittests under tests/, and bash scripts/check.sh only in a throwaway copy, never this clone (docs/memory/run-the-checks-in-a-throwaway-copy.md). Then mark ready and merge once green.
8. Ask the owner once, as a decision card: 1 fetch (hf_flexray_data, its exact size read first, refused whole by the size rule if it would pass the quota) and then 1 GPU job (bench flexray_drr_gap); the alternatives are the GPU job without FluXray, or hold. Read the grid status from symphony-template's branch grid before any send and never resend the status word.
9. After the run: copy the summary into the README's section 6, draw the figures, report in the thread.

## How to restart

1. Open a session on SchwingNet and symphony-template (the project symphony_3, or claude --cloud on SchwingNet with symphony-template added).
2. In each: `git fetch origin claude/project-thread-7ltron && git checkout claude/project-thread-7ltron`.
3. In SchwingNet: `export PATH="$HOME/.pixi/bin:$PATH"`, then `pixi run --locked python -m pytest -q tests/schwingnet/test_render_blocks.py tests/schwingnet/test_domain_gap.py`; the tools' unittests need numpy, torch, scikit-learn and fxr: make a venv, `pip install 'flexray[train]==1.0.2' scikit-learn==1.9.1 umap-learn==0.5.12`, and run `python -m unittest tests/test_domain_gap_run.py tests/test_domain_gap_stats.py`.
4. Read this page, then the README, then work the list above from step 1. The draft pull requests are the record.
