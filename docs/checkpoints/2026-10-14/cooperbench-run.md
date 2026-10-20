# CooperBench run with Symphony workers: checkpoint, 2026-10-15 10:40 UTC

Thread: "CooperBench" of the symphony project, carrying item 2 of the
2026-10-15 handoff (docs/checkpoints/2026-10-15/handoff.md), which
continued the 2026-10-14d handoff's item after the owner's weekly usage ran
out. The owner asked (2026-10-13 23:04) to start CooperBench benchmarking
with the workers automatically, working, and reporting every statistic
needed to compare against the CooperBench paper and its follow-ups. The run
lives in OpenSpineConsortium/coordbench's own GitHub Actions. coordbench's
main is 5028999.

## Landed (merged, CI green)

- coordbench#11 (merge 0de6a70): the kit runs on any Docker host and run.py
  scrubs the agents' token from every file a pair leaves.
- coordbench#12 (merge a581d02): .github/workflows/bench.yml with modes
  fake, survey and real, its jobs and actions, PLAN.md (the
  pre-registration), pairs.txt and METRICS.md.
- coordbench#13 (merge dd9aa2d): the protocol library named by its current
  repository, symphony-protocol.
- coordbench#14 (merge 99cd576): the Actions kit fixed from the
  after-the-fact review of #12 (the review's notes:
  docs/checkpoints/2026-10-14d/notes/coordbench-review-14.md).
- coordbench#15 (merge a5ddac2): the pair list fixed from the survey
  (bench.yml in survey mode, tag survey-1, run 38549172370): all 20 tasks
  and 50 pairs of CooperBench's flash subset grade on GitHub's runners.
- coordbench#16 (merge 5e4860e): the protocol's own counts (claims, pull
  requests, merge attempts, merges, conflicts, time to first merge) beside
  the emergent rates in the report, the gap METRICS.md named.
- coordbench#17 (merge 5028999): the read-back before upload opens every
  layer of a pair's files by its bytes, so a token packed or committed under
  any name is caught, and refuses what it cannot open
  (bench/cooperbench/README.md says what it opens and what it leaves). Six
  commits, each after an adversarial review of the one before; the sixth,
  5bf26be, is the fourth review round of the fifth commit run again, as the
  handoff asked: six findings, each reproduced by its own verifier and fixed
  with a test that fails on the commit before
  (docs/checkpoints/2026-10-15/notes/coordbench-review-17-round6.md; rounds
  four and five are under docs/checkpoints/2026-10-14e/notes/). `bash
  scripts/check.sh` passes on Python 3.12 (1115 tests).

## The fake run (fake-1)

bench.yml dispatched on main in fake mode (mode fake, pairs
@bench/cooperbench/pairs.txt, arms solo,coop,coop-git,team,sdlc, tag
fake-1, survey_tag survey-1), run 38718383737:
https://github.com/OpenSpineConsortium/coordbench/actions/runs/38718383737.
No usage was spent. Every one of the 250 runs, 50 pairs under each of the
five arms, finished and was scored: the Pass rates table shows 50 pairs and
0 in the Errors column for every arm, every pair fail, as a fake agent
writes no patch, and the Runs table one pair per run at 0.4 to 2.8 minutes
of wall time; 255 jobs, all green, 17 minutes from dispatch to report
(10:10 to 10:27 UTC). The read-back ran over every pair's files for the
stand-in and refused none, since a refusal fails the run's job. The report
is the artifact report-fake-1-38718383737 of that run and the report job's
log; the per-pair table of 50 rows ends it.

## Then, in order

1. The owner's steps below.
2. A real dispatch on pallets_click_task/2068 first (the pilot), approved
   on its run's page (Review deployments, tick bench, Approve and deploy), its
   report read; then the full list, @bench/cooperbench/pairs.txt. No real run
   before the owner's steps.

## What the read-back does not open (bench/cooperbench/README.md)

A marker encoded another way (base64); a stream that starts partway
through other bytes; a zip after a git loose object or pack; a zip whose
directory zipfile cannot read (a non-UTF-8 name under the UTF-8 flag),
refused in a work tree and searched as it is in history; a v7 tar with a
broken first header; a split zip's first and middle parts in history; a
path staged and never committed in a git index of version 4. zstd, 7z,
rar, lz4, .Z and lzip are refused.

## The owner's steps before a real run (in this order)

1. coordbench Settings > Environments > New environment, named bench, with
   the owner as required reviewer (Prevent self-review left unticked,
   deployment branches limited to main):
   https://github.com/OpenSpineConsortium/coordbench/settings/environments
   The plan job refuses a real run until this exists with a reviewer.
2. One organization secret per Claude account, SYMPHONY_CLAUDE_1,
   SYMPHONY_CLAUDE_2, ... (up to 8), each the output of `claude setup-token`
   run while signed in to that account, Repository access set to Selected
   repositories with coordbench ticked:
   https://github.com/organizations/OpenSpineConsortium/settings/secrets/actions
3. Repository variable SYMPHONY_CLAUDE_ACCOUNTS on coordbench, the slots in
   use, e.g. 1,2,3 (three accounts let one dispatch hold all 50 pairs
   under five arms):
   https://github.com/OpenSpineConsortium/coordbench/settings/variables/actions
4. Later: remove COORDBENCH_CLAUDE_TOKEN from the claude.ai cloud
   environment, which the Actions run no longer needs.

## Rules the thread kept

Scrub and leak tests plant only the stand-in PLANTED in ordinary files,
never a link to /proc/self/environ or a real environment file; reviewer
prompts frame the work as a coverage audit of the project's own check.
