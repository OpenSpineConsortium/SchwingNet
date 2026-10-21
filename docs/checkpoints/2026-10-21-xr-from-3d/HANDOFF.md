# Handoff: from 3D to X-ray

Written 2026-10-21 about 20:35 UTC by the thread "3D CT priors for 2D detection", at the owner's ask of 20:17 UTC ("checkpointed and a handoff written"). The research is docs/research/xr-from-3d/README.md (the report), docs/research/ct-priors-for-2d-detection.md and docs/research/xr-annotation-format.md; this file only says where things stand and what the next worker does.

## Done

- PR #55: the CT note (eight uses of the segmented CTs, ranked).
- The pull request that carries this handoff: the counting prior (src/schwingnet/chain.py, tests/schwingnet/test_chain.py), the CT prior job (tools/chain_stats.py, with readers' CT column calls through --columns), the evaluator (tools/chain_eval.py, settings from validation only), the covariate census (tools/covariates.py), their unittest suites (tests/test_chain_tools.py and tests/test_covariates.py, run in the train-cpu environment), the X-ray format note and the report.
- Issues: #56 the parent, #57 to #70 the workstreams A to N.

## Not done, in order

1. #57 A: the grid job tools/chain_stats.py over the CT roots, through the "SchwingNet video demo plan" thread; the roots (TotalSegmentator v2 and v3, VerSe, CTSpinoPelvic1K) are listed from spinesurg-ct-nnunet's data platform first, since this session could not read it. Then tools/chain_eval.py over version 1's run when it exists.
2. #58 B after the leak checks; #59 C; #61 E layers 1 and 2: the work that can still move a number before 2 November.
3. #66 J: the covariate census job over every held X-ray source.
4. #63 G: the schema and converters, so readers can start.
5. The rest after the talk, D first.

## What waits on the owner

- Which collection is "the massive unannotated X-ray dataset" (#64).
- Whether DiffDRR or DeepDRR may be added (#59, #69; an issue first by the writing rule).
- COBRA's CC BY-NC 4.0 and commercial use: on his lawyer list already (#60).
- Who reads: the owner, Dr Tech as second reader, for the CT column calls (#62) and the screener's queue (#64).

## Things a next session should know

- The pre-push hook refuses a push from a tree with an untracked file; the session's .githooks/commit-msg shows as untracked, so this thread pushed from a clean worktree (git worktree add --detach) and removed it after.
- The beethoven-qa gate refuses a skipped test under tests/schwingnet, so the tool tests that need torch or pydicom are unittest suites under tests/.
- The decoder's dry run on the synthetic catalog with an untrained model (14 / 68 against 11 / 68) proves the plumbing only.
