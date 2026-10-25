# Handoff: benchmarking the public spine and pelvis models (FleXray, xvr)

Source: the project thread "Compare lab's X-ray learning to SchwingNet", 2026-10-25, checkpointed by the owner at 14:24 UTC. Everything below is committed or open as a pull request; nothing lives only in the session that wrote it.

## Goal

Score the public models that name spine levels or segment the pelvis, as their authors published them, against this record's own numbers. The owner's word and count of 2026-10-25 03:24 UTC ("ok yes absolutely do those experiments") was three fetches and three GPU jobs. On 2026-10-25 the owner added, on cards in the thread: one CPU setup job for the stale grid environments (before 13:12 UTC), one rerun of FleXray on DeepFluoro once its label reader is fixed (13:35 UTC), and one rerun of xvr on DeepFluoro once its compile step is fixed (14:17 UTC). Nothing trains or tunes. FleXray's weights are CC-BY-NC and xvr's data CC-BY-NC-ND: benchmark rows only, never part of a SchwingNet network.

The plan and its reasoning are docs/research/public-spine-and-pelvis-models-to-benchmark.md (#286, corrected in #288).

## What ran

| Job | What | State | Result |
|---|---|---|---|
| 40780681, 40780691, 40780696 | the three fetches | completed | inputs in place |
| 40781568 | setup (pixi environments rebuilt, #309) | completed in 2 min | |
| 40781570 | bench flexray_carmlspine | completed in 4.5 min | see below |
| 40781578 | bench flexray_deepfluoro | failed after 9 s | our bug, fixed by #314 |
| 40781587 | bench xvr_deepfluoro | failed after 4 min | Triton's gcc step, fix in #387 |

FleXray zero-shot on C-ArmLSpine (job 40781570, commit fc027a6, report grid/logs/BENCH-flexray_carmlspine.md on the grid, results under /rs/rs_grp_oschome/go2432/bench/flexray_carmlspine): 1,627 truth boxes, every one detected by the quarter-coverage rule. Accuracy over detected bodies, Wilson 95 percent intervals:

| Member | Correct | Accuracy | Interval |
|---|---|---|---|
| flagship (flux0375) | 1613 | 99.14 | 98.56 to 99.49 |
| flux000 | 1598 | 98.22 | 97.45 to 98.76 |
| flux025 | 1618 | 99.45 | 98.95 to 99.71 |
| flux050 | 1616 | 99.32 | 98.79 to 99.62 |
| flux075 | 1607 | 98.77 | 98.11 to 99.20 |
| ensemble | 1621 | 99.63 | 99.20 to 99.83 |

The lateral and AP split is in flexray-carmlspine.json under the results folder; the report printed only the pooled line. Not yet known: whether FleXray's training data held C-ArmLSpine. Its project page (flexray.csail.mit.edu) names no training sets, and its paper's PDF (arXiv 2609.26756) gave no text to the session's reader. Until that is read, the number is not a clean zero-shot result, and the note must say so.

The two failures:

- FleXray on DeepFluoro: `ValueError: invalid literal for int() ... 'dir-mat'`. The IPCAI 2020 file stores each view's gt-seg as an xreg image group (dir-mat, origin, pixels, spacing), and tools/bench_public.py read the group as an array. #314 reads its pixels, and also lets `bench <name>` queue a failed benchmark once more after the checkout moves past the commit its report names.
- xvr on DeepFluoro: on all six subjects, Triton's gcc compile of its cuda_utils.c helper failed inside the container (`subprocess.CalledProcessError`), then evaluate.py failed with `KeyError: 'dataset'` for want of results. #387 sets TRITON_LIBCUDA_PATH=/.singularity.d/libs, the usual cause under Apptainer's --nv (Inferred), and quotes the first compiler or linker error in the report, so a rerun prints the real cause if this guess is wrong.

## Open pull requests at the checkpoint

- #314 (closes #312): ready, auto-merge on, main brought in through the API. It merges by itself once green.
- #387 (closes #386): the xvr fix; its claim commit was pushed through the API, and the fix commit was being pushed through the 20-minute pre-push gate at the checkpoint. If the branch on origin holds only the claim commit, rebuild it from the issue's two changes to grid/bench.sbatch (the TRITON_LIBCUDA_PATH export after the PYTHONNOUSERSITE line, and a failure_of helper that greps `: (fatal )?error:|cannot find -l|undefined reference` before the last line), delete the claim file, write the body with its Adversarial review, mark it ready in a call of its own, then auto-merge.
- #389 (closes #388): this handoff.

## Next steps, in order

1. Check that #314 and #387 merged (`git log origin/main`). Bring main into either with the API's update-branch if the protocol check fails on a moved main.
2. Send `schwingnet-status` first (symphony-template, Actions, grid-accounts.yml, https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid-accounts.yml, Run workflow, action `job`, job `schwingnet-status`), read logs/job-schwingnet-status.json on the branch grid, and confirm no bench job is live.
3. Once #314 is on main, send `schwingnet-bench-flexray_deepfluoro` once. The gate keeps the failed report as BENCH-flexray_deepfluoro-40781578.md and queues one GPU job. This is the approved rerun.
4. Send `schwingnet-bench-xvr_deepfluoro` only once #387 is on main too. With #314 merged and #387 not, a send would rerun xvr on the unfixed code and spend the one approved rerun. Send it once.
5. One gate call a minute. When each job ends, send its word again to print its report; a report that ends in exit 0 queues nothing.
6. Write the numbers into section 2 of the note by an issue and a pull request of their own: every FleXray member and the ensemble, lateral and AP apart, over detected bodies and over all, with Wilson intervals beside the record's own and never mixed with them; DeepFluoro Dice under both intensity readings against the published 0.916; xvr's median mTRE against the published 1.1 mm; and the open training-data question.
7. Before stopping, a general pointer may go to symphony-template's docs/research; SchwingNet's notes and numbers stay in SchwingNet.
8. Not counted, and each needs the owner's word first: any further rerun; the spine Ljubljana 2D-3D-GS level bank from its given poses (no GPU); FluoroSAM's weights and the twin's frames, which wait on #163.

## First prompt for the next account

"Read docs/checkpoints/2026-10-25-public-benchmark/HANDOFF.md in OpenSpineConsortium/SchwingNet and carry on from its Next steps: see #314 and #387 through to main, check the grid with schwingnet-status, send the two approved reruns (FleXray on DeepFluoro after #314, xvr on DeepFluoro only after #387, one job each), read their reports, then write all three results into docs/research/public-spine-and-pelvis-models-to-benchmark.md by pull request."
