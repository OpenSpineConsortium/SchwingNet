# Handoff: improving the trainer as swappable blocks (#205, draft PR)

Source: the project thread "Improve SchwingNet training and review end-to-end status", 2026-10-24. It was checkpointed when the owner said to stop at once. Everything below is committed and pushed. Nothing lives only in the session that wrote it.

## What landed

- #200 (merged): one decode per frame in tools/train.py's load_crops. It also added docs/research/training-review.md, the ranked review of the trainer and the end-to-end status table.
- #201 (merged): seed_everything sets CUBLAS_WORKSPACE_CONFIG and turns cudnn.benchmark off, so GPU runs reproduce.
- #203 (merged): the trainer's building blocks.
  - Seven parts are chosen by `--block KEY=VALUE`: normalise, augment, optimiser, schedule, sampler, loss_weights and select.
  - Naming no block gives version 1's training to the bit.
  - tools/block_sweep.py plans a sweep and submits nothing; its `compare` command reads only the validation part.
  - docs/memory/training-blocks.md describes it.
- symphony-template #439 (merged): the general pointer, docs/research/trainer-building-blocks.md, with nothing confidential in it.

## Where it stopped

Issue #205 is on branch claude/205. It adds `--init <checkpoint>` to tools/train.py, passed through by tools/flow.py, so a run can start from a parent checkpoint: the incremental run of docs/research/retraining-plan.md, section 3.4.

- Written and pushed:
  - the code;
  - tests/test_train_init.py (5 tests);
  - the memory line;
  - this page.
- Checks run:
  - tests/test_train_init.py and tests/test_train_blocks.py pass in a torch CPU environment (23 tests);
  - `bash scripts/check.sh` passes in a scratch worktree.
- The claim file docs/agents/claims/205.md is still on the branch.

## Next steps, in order

1. Read the draft pull request for claude/205 and add an "## Adversarial review" section to its body. Two places to check:
   - warm_start compares the parent's normalise and size only when the parent's checkpoint.json sits beside it;
   - parent_of reads RUN.json two folders up.
2. Finish the claim:
   - delete docs/agents/claims/205.md in a commit of its own and push;
   - mark the pull request ready in a separate call;
   - label #205 in-review.
3. When auto-merge merges it, close #205 by hand. The bot's merge leaves the issue open (docs/memory/auto-merge-starts-no-workflow.md).

## What waits on the owner's word (nothing below was started)

- Which blocks the version 1 rebase uses. docs/research/training-review.md, section 1, gives the order: imagenet normalise and augment first.
- Any sweep, with its job count from `tools/block_sweep.py plan`.
- Recording grid run e4f7054848f5 (21/21 test crops) with `flow.py record --freeze`. It is not yet under docs/research/v1-demo/runs.
- Latency jobs 40702515, 40702516 and 40702517 have been pending since 2026-10-22. Read why with squeue %r, or resend them.
- The counting-prior grid words (#72, #73).
- A detector stage. There is none yet, and no code path takes the patient's own preoperative CT.
