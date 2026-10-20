---
name: validation-harness-progress
description: Where PLAN.md Phase 1 (the validation harness in symphony-protocol) stands, step by step; step 6 is a draft PR checkpointed with three soak leads
metadata:
  type: project
  modified: 2026-10-14T01:33:02.452Z
---

Phase 1 builds symphony-protocol's validation harness in the order of validation/DESIGN.md section 14, one PR per step. validation/README.md on main says what each step built; read it first.

- Steps 1 to 5 merged 2026-10-13: #15 (foundations; F13, F14 found), #16 (mutation lane), #17 (board run as the workflow makes it; the one library change since 0.4.1, cli.plan_board/act_on_board, rides the next release), #18 (fast lane), #19 (traces F1 to F14, known.json; merge ad3c8aa). oracle.AS_BUILT = F2, F9, F12, F13, F14. A fix in the library removes its known.json entries in the same PR.
- Step 6 (deep lane + git world): DRAFT symphony-protocol#21, branch claude/validation-harness-step-6-mm6b8t, head 126b9b9, checks green, NOT merged: the owner ran out of usage on 2026-10-14 01:10 and asked for a checkpoint, to review next session. Built: git_store.py, deep.py, shrink.py, soak.py, gate_search.py, lanes.py, `scripts/validate.py deep` and `--world git`, the deep job in validate.yml, known.json "searches" (F7 in E-faults). Library unchanged.
- The first full deep run died at about 2,670 s in a container restart; its output is committed at validation/runs/2026-10-14-partial (README there). Green: E-faults depth 4, the gate (depth 8, S05g, 40 git sequences with 20 merges), all scenarios and traces over git, the guard re-record. Unfinished: E-deep (6.9 million states) and E-two (6.2 million), still growing; conformance did not start.
- LEADS: the soak (no careless workers, no lease, so not F7) met G1 on seeds 585 and 959 ("the board names e for claude/5, whose holder is b", after close, reopen, rename-back, merge) and G9 on seed 427 (a second run with nothing new posted a comment, after push-old-head and rename-back). Each may be a harness model fault or a library finding. shrink.py left them at over 100 steps; it needs chunk removal before single steps.
- Next for #21, in order: judge the three leads (replay in memory and with --world git, shorten); fix shrink for long walks; run the adversarial review again (it died in the restart); run the deep lane to the end, detached, with setsid and nohup; fill the <<...>> placeholders in README.md and DESIGN.md; mark ready and merge.
- Then step 7 (the monthly canary on the owner's new canary repository; needs its name and permissions) and step 8 (the report).

**Why:** the next thread must not redo step 6, and must not merge #21 before the leads are judged and the measurements are filled in.

**How to apply:** continue on the same branch. Keep changes in validation/, tests/ and validate.yml so no release follows. A container restart kills background runs, so keep deep.json and the logs somewhere that is committed. See [[symphony-project]].
