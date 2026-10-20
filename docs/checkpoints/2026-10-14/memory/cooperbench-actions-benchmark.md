---
name: cooperbench-actions-benchmark
description: State of the CooperBench-on-Symphony benchmark built in coordbench's own GitHub Actions (bench.yml), 2026-10-13/14, and what the owner must add before a real run
metadata:
  type: project
  modified: 2026-10-13T23:58:03.255Z
---

Thread "CooperBench run in Actions" (cmsg_01DwBZXhqgJsTCs7bpRxnwy4FKZjqfuawCCFyduZXuHt9i), 2026-10-13 late.

- coordbench PR #11 MERGED (0de6a70; branch claude/bench-kit-0fxuxy): kit runs on any Docker host (COORDBENCH_CLAUDE_BIN stand-in, CLAUDE_CODE_VERSION pin 2.1.296, proxy CA optional, COORDBENCH_SKIP_GRADEABLE) and run.py scrubs the agents' credential from a pair's files (scrub_credentials/scrub_pair/scrub_hub, in a finally; archives left whole; CredentialKept fails a pair). Adversarial review found 15 defects, all folded in.
- coordbench PR #12 MERGED 2026-10-14 01:39 (a581d02, on the owner's "push it its green"; branch claude/bench-actions-0fxuxy; its own smoke run is bench.yml in fake mode on pallets_click 2068 under solo, coop-git and sdlc): .github/workflows/bench.yml (modes survey/fake/real; plan/survey/run/run-real/report jobs; composite action bench/cooperbench/actions/run-pair; artifacts <tag>__<arm>__<repo>__<task>__f1_f6 for resume; concurrency bench-<account> queue: max; environment bench; secrets SYMPHONY_CLAUDE_<slot> for slots 1 to 8, named one by one in the workflow since secrets[format()] made CodeQL flag excessive-secrets-exposure; vars.SYMPHONY_CLAUDE_ACCOUNTS lists the slots in use), bench/cooperbench/fake_claude (POSIX sh stand-in agent), actions/plan.py, artifacts.py, pair.sh, survey_task.sh, report.sh, survey_report.py, free_disk.sh, PLAN.md (pre-registration), pairs.txt (43 pairs, 17 flash tasks), METRICS.md (paper/blog/ablation/Claim Plane metric map). A fake solo and a fake sdlc pair ran end to end locally through pair.sh. The review's fixes (second commit c246c4b): resume wants a scored pair with no agent in Error; smoke tag carries the run id; matrix capped at 256, queue at 100 only in real mode; survey exit from verdicts; fake agent fails loudly, follows the arm's patch.txt rule, and its --version carries its checksum so an edited stand-in reaches an already-overlaid image; actions/environment.py gates a real run on the environment bench having a required reviewer.
- Known gap (PLAN/METRICS say so): report.py has no Coordination section for the sdlc counters (claims, prs_opened, merge_attempts, merges, merge_conflicts, time_to_first_merge_seconds in metrics.json) or the team arm's metrics; next PR.
- CodeQL on coordbench PRs flags new tests that write the fake token constant SECRET to files (clear-text storage heuristics); checked by running the CodeQL bundle locally (no API access to alerts).

**Why:** the owner asked (2026-10-13 23:04) to start CooperBench benchmarking "using the workers automatically" with every statistic needed against the paper and follow-ups.

**How to apply:** owner's steps before a real run: org secrets SYMPHONY_CLAUDE_1, SYMPHONY_CLAUDE_2, ... (one slot per account, up to 8) from `claude setup-token` on each account, shared with coordbench, repo variable SYMPHONY_CLAUDE_ACCOUNTS with the slots in use (1,2,3), environment `bench` in coordbench with the owner as required reviewer; then dispatch bench.yml mode survey, fix pairs.txt, dispatch real on pallets_click_task/2068 first (pilot) and approve. Related: [[symphony-project]].

Checkpoint 2026-10-14 01:40 at /mnt/project-files/checkpoints/cooperbench-run.md: next is survey dispatch (tag survey-1), fix pairs.txt, fake dispatch, report.py Coordination section, then the owner's steps and the real pilot. Nothing after #12's merge was reviewed.
