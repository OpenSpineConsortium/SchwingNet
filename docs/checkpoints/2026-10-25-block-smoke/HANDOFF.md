# Handoff: the block smoke test (#252, draft pull request #253)

Source: the project thread "Build plug-and-play training experiment framework", 2026-10-25. It was written at 09:50 UTC, when the owner's account reached 92 percent of its weekly limit and the owner asked every thread to hand its work to another account. Everything below is committed and pushed on claude/252; nothing lives only in the session that wrote it. The research is in docs/research/block-smoke/README.md, docs/research/experiment-framework.md and docs/research/experiment-framework-analogues.md; this page points to them and does not repeat them.

## Goal

The owner's asks of 2026-10-24, from 21:11 to 21:20 UTC: smoke-test on the grid every route data takes through the training blocks, on every dataset held, so that any combination of blocks the rules allow is known to work and the annotated and unannotated sets are passed as they should be; keep the results under /rs/rs_grp_oschome/go2432/smoke/ in folders predictable from the configuration; show progress live with what the tools give natively; checkpoint and resume the preprocessing with Metaflow's own resume, enforced; audit the data input for formats; then choose five trial combinations that reproduce a literature benchmark, with citations, and a sixth that the results in the textbook favour; and carry the results into the textbook's interactive experiments page. On 2026-10-24 at 22:27 UTC the owner asked for Metaflow's native resume to be used and enforced. On 2026-10-25 at 04:24 UTC the owner chose to wait for every confirmed review finding to be fixed before anything is dispatched. On 04:26 UTC the owner asked for the framework to be exportable as other researchers share workflows: that is #293, after this and the smoke, private until the filing.

Done is: #253 merged; the smoke's jobs run (the owner's count of 2026-10-24 22:12 UTC: 3 GPU and 3 CPU jobs); the results read into the textbook and the experiments page (#268); and the six trials (grid/sweeps/trials.json) sent only on the owner's own count for them.

## Where it stands

- #253 holds everything: the covering plans and the check (tools/block_sweep.py, src/schwingnet/blocks.py, grid/sweeps/), the Metaflow flows and the launcher (flows/, src/schwingnet/pipeline.py), run folders named by the code they run (tools/run_code.py), reuse and resume (tools/flow.py, tools/train.py), the strong augment block, the grid words sweep and bank, and the docs and memory.
- Two adversarial rounds: the first gave 28 distinct real findings and the second 24, all fixed with a test that failed first; reading the second round's fixes found one more, fixed too (4695158, a preempted Slurm job polled for ever). The pull request's body holds the record.
- A third, focused review of the second round's fixes was started and stopped to save the account's budget; it found and kept nothing.
- Rehearsal: at 61ef174 the synthetic plan ran end to end through flows/launch.py and Metaflow on a CPU, one epoch a row, in 21 minutes: of its 27 rows 22 ran, 3 were refused and 2 were not applicable (no ImageNet file was given here; the grid holds one), none failed, and every row did what the check predicted. Its state folder took 1.7 GB.
- Checks at 61ef174 (the commits after it add only this page, research and main's #301, which changes tools/folder_report.py and its test alone): `bash scripts/check.sh` passed (2,157 tests, 341 skipped for want of torch or wandb), the gate's 247 tests, ruff, mypy and the six standards. The torch and Metaflow modules, which CI never runs, passed one at a time in the train-cpu environment: test_train_resume 42, test_train_blocks 42, test_block_sweep 37, test_flows 29, test_flow_reuse 19, test_bank_dicom 11, test_wandb_log 9 and test_train_init 5.
- #253 was then marked ready with its claim file deleted and its review record in the body, #252 was labelled in-review, and GitHub's auto-merge was armed, so it merges once its checks are green. Nobody watches its checks after the handoff.
- Nothing was dispatched to the grid.

## Next steps, in order

1. See whether #253 merged. If it did, see that #252 closed, and close it by hand if not. If a check failed, read the failure and fix it on claude/252: merge main in if it moved (never rebase), run `bash scripts/check.sh` in a scratch copy (docs/memory/run-the-checks-in-a-throwaway-copy.md) and the eight torch modules above one at a time with `SCHWINGNET_WANDB=off pixi run --locked -e train-cpu python -m unittest tests.<module>`, push by name, and let auto-merge take it; merging once green is the owner's standing permission.
2. Optional, as its own issue: the focused third review that was stopped, of the merges 288e41a (the grid: the bank job's admission for its frames' pixel bound, status-page.awk, the sweep rows' reasons in status, the bench's hold, the bank's wait for its landing) and c826bd9 (the run flow: the ledger's lock, last.pt bound to its bytes, checkpoint.json held to best.pt, the catalog check, Slurm jobs recorded at submission), and 4695158. The size rule must never loosen, and status must never show a file name or a case's number.
3. Clean nothing up on the grid; the old account's container held only scratch copies.
4. After the merge, stage the textbook again, since chapters 2, 18 and 35 changed: `python3 tools/textbook_reader.py stage --clone <a clone of main>`.
5. Read the grid's state: dispatch OpenSpineConsortium/symphony-template's grid-accounts.yml with action `job` and job `schwingnet-status` (a thread may send this word alone) and read logs/job-<id>.json on the grid branch. Note whether the environments match pixi.lock (else the first sweep word also queues a setup job), whether the ImageNet file is there (else a weights job), and the room under the quota.
6. Give the owner numbered steps, each word clicked by the owner at https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid-accounts.yml with action `job` (not `log`), with what each costs: `schwingnet-sweep-synthetic` (GPU job A, up to 4 hours), `schwingnet-sweep-real` (GPU job B, queued after A, since each sweep holds the checkout), `schwingnet-bank-vindr_spinexr` (two CPU jobs, the bank of 10,466 DICOM films, 36.0 GB raw, held 72 GB while it waits and admitted before it writes for the larger of that and its frames' pixel bound, and the catalog build after it), then `schwingnet-sweep-two_source` (GPU job C, after the catalog build). Send real before bank, since the bank adds a source to the catalog real reads. A setup or weights job counts against the three CPU jobs, and a cut sweep resumes only by its word sent again, which is another job and needs the owner's word. Each plan's state folder is about 2 to 3 GB by the local runs. The live W&B view needs the owner's click of action `key`, name `wandb`.
7. While the jobs run, status shows each plan's PROGRESS.txt and RESULTS.md says why each row that did not run did not. Afterwards, record the results into the textbook and the experiments page (#268; `python3 tools/experiments_panel.py write` after recording runs), and ask the owner for a count for the six trials.
8. #293, the framework as an importable package, comes after the smoke and stays private until the provisional is filed.

## What waits on the owner's word

- Every grid word but status, and the count for the trials.
- The W&B key click.
- Whether a cut sweep is sent again.

## First prompt for the next account

Open a Claude Code session on OpenSpineConsortium/SchwingNet and give it:

> Read docs/checkpoints/2026-10-25-block-smoke/HANDOFF.md and continue issue #252 from its next steps. Finish pull request #253 and merge it once its checks are green, then read the grid's status and give me the click steps for the block smoke test, three GPU and three CPU jobs as I chose on 2026-10-24. Send no grid word but status yourself.
