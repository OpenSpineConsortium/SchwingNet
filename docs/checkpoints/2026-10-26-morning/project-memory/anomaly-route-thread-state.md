---
name: anomaly-route-thread-state
description: Where the SPINEPS-to-FleXray anomaly route (#391, SchwingNet #398) stands after the restart of 2026-10-25 23:35 UTC, which grid words were sent, and the timing stage PR
metadata:
  type: project
---

Thread "Plan the FleXray audit for #391" (restarted 2026-10-25 23:35 UTC in project symphony, chan_014WUU19NHgHPhf7QetT9cbS).

- SchwingNet #398 merged at 23:40 UTC as bd6fdab: data/splits/anomaly-holdout.json, tools/anomaly_route.py (freeze, score, select, check), grid/anomaly.sbatch, the gate word `anomaly select`, docs/research/spineps-anomaly-route.md, and docs/checkpoints/2026-10-25-evening/ (confidential, stays in SchwingNet).
- Grid words sent by this thread (symphony-template grid-accounts.yml, action job): `update` 23:40 UTC (hpcworker gate clone 16414858..9ea69bb5, framework 28); `schwingnet-status` 23:41 UTC (nothing live, 4,416 GB free); `schwingnet-anomaly-select` 23:42 UTC, submitted as Slurm job 40785048 at commit bd6fdab (1 CPU job of the 15 approved). Read its report by sending `schwingnet-anomaly-select` again once the job ends (logs/ANOMALY-select.md); every later send only reprints it.
- Select's report (job 40785048, exit 0, read 00:07 UTC): VerSe screen frozen (a0cb756c2ef7); 1,004 CTs (890 train at 30.0% variants, 114 test-only cobra2026: 2 L6 + 112 normal), pack bound 188.2 GiB, selection.csv sha256 bdc9d9ae8f9dd41b under /rs/rs_grp_oschome/go2432/anomaly/select/; finder L6 sensitivity 22/83, VERIDAH 36/83; folds 19/18/18/18; train L6 from 14 collections (verse 73, abdomenatlas3_mini 68, idc 27, ctsp 22, panorama 21).
- Stage 2, timing: tools/anomaly_timing.py (gpu, inventory, pick, estimate), the timing branch of grid/anomaly.sbatch (exit 4 on a Blackwell node, SPINEPS via spinesurg-ct-nnunet benchmark/run_spineps_cases.py in the spineps conda env), gate class gpu `--cpus 8 --mem 64G --time 04:00:00`, refused until ANOMALY-select.md ends "- exit 0 ".
- #403 merged 2026-10-26 ~00:12 UTC (main 074e3bf); `schwingnet-anomaly-timing` sent once at 00:16 UTC (request anomaly-timing-x16ebc, symphony-template grid-accounts.yml run 40248523239): Slurm job 40785227 at commit 074e3bf, a GPU job (2 of the 15 approved jobs now sent: select and timing); read its report by sending the word again once the job ends (logs/ANOMALY-timing.md); an exit 4 report (Blackwell node) means send once more.
- The owner's words of 00:16 and 00:17 UTC (C2-countable truth only, SPINEPS never TotalSegmentator, reuse existing masks) are in [[owner-trusts-only-c2-countable-spines]] and shape the pack stage: countability per CT recorded in the pack, uncountable rows train nothing by default, decision card to the owner.
- Stage 3, pack: its design decisions are [[anomaly-pack-stage-design]]; built from 01:30 UTC on branch claude/project-thread-x16ebc, PR to follow.
- Remaining approved and unsent: pack (CPU), render, figure, tune, eval (GPU), then tune_f1..f4 and eval_f1..f4 after main tune and eval look sane. Each goes only after its PR merges and the stage before looks sane. The SPINEPS production array is NOT approved; the timing report's estimate is the number for the owner's decision card.
- SPINEPS on the grid: conda env `spineps` (~/mambaforge/envs/spineps, spineps 2.1.1, torch 2.6 cu124) and /rs/rs_grp_oschome/go2432/envs/spineps212; models in ~/spineps_models; Blackwell nodes ymh3/ymh4 (sm_120) cannot run it (symphony-template docs/checkpoints/2026-10-20-claude-code/topic-memories/ruleclass-super-detector-run.md).
- The corpus search for the owner's 22:31 question is answered: SchwingNet #407 (docs/research/full-spine-corpora-with-reader-counted-variants.md, 2026-10-26 01:55 UTC, ready): fourteen closed cohorts with per-case reader counts over both junctions, Hofmann's labels the one open addition; pushed from a scratch clone since the main checkout carries the uncommitted pack build (the pre-push hook refuses a tree with anything uncommitted).

**Why:** the owner's count is one job per stage; a second send of a word for one read, or a stage sent before its predecessor is sane, breaks the count.
**How to apply:** before any grid send read logs/job-schwingnet-status.json on symphony-template branch grid; send a stage word once; see [[grid-counts]] in MEMORY.md for the approved counts.
