# Handoff: workflow state, smoke dispatch and dataset tasks (2026-10-25)

Thread "Build workflow state and synthetic XR artifact", checkpointed at the owner's word of 2026-10-25 14:23 UTC. The research is docs/research/workflow-brief-2026-10-25.md; this page says only where things stand and what comes next.

## Done

- The workflow brief (docs/research/workflow-brief-2026-10-25.md) and the owner's private page "SchwingNet workflow state" (https://claude.ai/artifact/VAur1wartsVQR6a1rJj4P9, version 3): the block workflow, the packaging plan (#293), the selector rerun, the synthetic render methods M1 to M6 and tiers T0 to T4, the videos with their grid paths, an interactive workflow map and a dataset explorer.
- The MAID licence: Marcin Budka set OSF z2jby to CC BY-NC 4.0 on 2026-10-25; data/sources/bournemouth_*_qf.json, data/licences.json, data/LICENCES.md, data/choice/CHOICE.json, the inventory page and chapter 35's figures carry it (PR #311, this branch).
- Selector rerun, counting unheld sets as obtainable and cine sets toward the test: 755 test persons against 381 needed (432 without Pittsburgh).
- Tasks: #310 is the umbrella; #315 to #384 are one task per unheld dataset or unknown licence, labelled priority:P1 (15), P2 (6) or P3 (49); FluoroCap's licence is left alone on the owner's word. #385 is the render-count scaling study (log-spaced budgets, per pose bin, broken power-law fit); its jobs are not sent.
- The owner chose case134 as the video to run on.

## Grid jobs sent (on the owner's "can you do this?", 13:15 to 13:23 UTC, at main fc027a6)

- Sweep A synthetic, job 40781593; sweep B real, 40781617; bank vindr_spinexr 40781621 with its catalog 40781623; sweep C two_source 40781628, waiting on the catalog. 3 GPU and 2 CPU jobs of the owner's 3 + 3; one CPU job of the count is left.
- State at the checkpoint: not read since dispatch. Read it with the status word (symphony-template grid-accounts.yml, action job, job schwingnet-status) and the answer at logs/job-schwingnet-status.json on symphony-template's branch grid, before any resend. Results land under /rs/rs_grp_oschome/go2432/smoke/<plan>/.

## Waiting on the owner

1. The W&B key: the run failed because the environment secret is missing. Add WANDB_API_KEY at https://github.com/OpenSpineConsortium/symphony-template/settings/environments (grid, Add environment secret), then grid-accounts.yml with action key, name wandb.
2. The six trials (grid/sweeps/trials.json): one GPU job, 6 rows of 20 epochs, word schwingnet-sweep-trials, only after the smoke results and on the owner's count.
3. The jobs of #385, each with its count.

## Next

1. PR #311: auto-merge is armed; if the board says "main moved", use the API's update-branch (PUT /repos/OpenSpineConsortium/SchwingNet/pulls/311/update-branch) and wait for check.
2. Read the smoke status, record the results (#268), then start #293's packaging.
3. Work the P1 dataset tasks from #310, letters only on the owner's word.

## Continuing in another account

Open a thread in that account's Claude project on OpenSpineConsortium/SchwingNet and give it this first prompt: "Read docs/checkpoints/2026-10-25-workflow-state/HANDOFF.md and continue from its Next list; send no grid job without my word and count."
