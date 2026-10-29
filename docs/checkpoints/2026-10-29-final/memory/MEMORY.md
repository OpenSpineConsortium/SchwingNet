# MEMORY.md (the project symphony_4's memory as it stood at 17:45 UTC on 2026-10-29, copied for the final handoff)

Source: SchwingNet main 35a4b6f, docs/checkpoints/2026-10-29-checkpoint/memory/ (#452, merged 02:21 UTC 2026-10-29; every file verbatim, newer than the 2026-10-28-final copy, with figure-format added) with its MEMORY.md below as the index; the two files under "Newest" are this thread's, and grid-words-and-counts carries the rerun's end. The four older files of 2026-10-27 were replaced; two ENHANCE.PET detail files are kept at the end.

## Newest (2026-10-29), read before the rest
- [fluoro-tasks-plan](fluoro-tasks-plan.md): the real-time fluoroscopy task plan checkpointed 17:27 UTC 2026-10-29 as SchwingNet draft PR 467 (handoff docs/checkpoints/2026-10-29-fluoro-tasks/); no issue created yet; the twelve-task draft order and the panel rules.
- [metaflow-words-port](metaflow-words-port.md): the 2026-10-29 17:25 UTC checkpoint of moving every grid DL word onto launched flows: DRR and v1 merged, experiment and latency on draft PR #466 with the handoff's seven review items, bench, anomaly timing and the gate refusal decided and unwritten.
- [hold-lifted-2026-10-29](hold-lifted-2026-10-29.md): greg lifted the attorney hold on grid/WSU use for the Bayesian work at 15:32 UTC 2026-10-29 ("yes i want the hold lifted"); word and count per job still apply.
- [synthetic-validation-state](synthetic-validation-state.md): bordercall PR 29's synthetic validation note, its report page H82v6B1drWmpjTJhrWrLxv, how its records rerun, and f's all-106-measures extension (a new PR after 29).
- [checkpoint-2026-10-29](checkpoint-2026-10-29.md): every thread stopped on greg's word of 00:38 UTC; his answers of that night; the four pieces he restarted at 02:06 UTC (chain of levels, clinical reread, gold tier 3 completion, recording the FluXray rerun); the hold stands.
- [fluxray-rerun](fluxray-rerun.md): run 2 of the DRR study ran once (40859208), count spent, recorded in #453; report-by-code PR #455 (63 of 76 by code; greg's 13 accepted with "Accept 1-13" at 12:10 UTC, scoped to run 2) merged 12:41 UTC (137b3ef); run 3 on the launched flows sent once 15:11 UTC (prepare 40867572, shards 40867573, merge 40867575), prepare done, shards queued at the 17:22 UTC checkpoint; handoff docs/checkpoints/2026-10-29-drr-run3/HANDOFF.md.
- [dl-jobs-run-on-metaflow](dl-jobs-run-on-metaflow.md): greg's standing rule of 02:39 UTC: every deep learning job on the grid runs on his block-based Metaflow pipeline, frozen PREREG, REFORMS/CLAIM enforced, a browser progress page; port first, hold the job.
- [flux-realism-restart](flux-realism-restart.md): greg's count of 02:35 UTC 2026-10-29 to reproduce FluXray (3 fetches + 2 GPU jobs), replacing the 2026-10-26 count; its own thread.
- [autoanatomist](autoanatomist.md): greg's word of 02:17 UTC 2026-10-29 to build the auto-anatomist on a measurement oracle; the bordercall package (oracle protocol, gates and ladder, naming layer, dual encoder) on phantoms only, its limits, the JAX/Flax/optax packages to confirm, draft PR 27 opened 07:33 UTC and not marked ready.
- [morphometry-state](morphometry-state.md): gold tier 3 morphometrics, bordercall draft PR 30; run of 228 studies complete, status artifact 9SiGQnvxDGPsMsRKBqoNtQ, three measures held back, merge waits on suites and review.
- [gold3-spineps-completion](gold3-spineps-completion.md): the gold 3 completion checkpointed 17:30 UTC 2026-10-29 on greg's word (push all, stop every review): handoff in SchwingNet draft PR #470 (docs/checkpoints/2026-10-29-gold3-completion/), bordercall PR 28 at 810fef2 with four suites still to run, #458 at c838734, SPINEPS 13 of 34 done with masks in the project files, the one-CPU grid job (greg's count of 15:22 UTC) written but not wired or sent.

- [metaflow-required-for-grid-dl](metaflow-required-for-grid-dl.md): greg's rule of 02:39 UTC that every deep learning grid job runs on flows/launch.py with REFORMS/CLAIM enforced; which words are moved and what is open.
- [verse-genant-benchmark](verse-genant-benchmark.md): bordercall's body ratios on VerSe's 374 masks against Riedel's Genant grades (AUC 0.836); results only in the project files, never git.

The index of this folder, one line per file. A new project copies each file into its own memory as it stands, with this index. Read the Newest section first.

## In force now
- [hold-and-wrap-up](hold-and-wrap-up.md): the hold is lifted: greg's word of 2026-10-29 17:05 UTC ends the grid/WSU-data hold for every thread; each grid job still needs his word and its count.
- [decisions-2026-10-28](decisions-2026-10-28.md): his seven decisions of 20:40 UTC, each with what it still needs; none acted on; three wait for the hold.
- [owner-open-steps](owner-open-steps.md): the questions, words and clicks only greg can give, numbered.

## How greg works
- [owner-working-style](owner-working-style.md): idk means take the recommendation; one card per count; numbered steps with exact links; checkpoint means push and stop.
- [say-what-a-count-is](say-what-a-count-is.md): never a bare count; say what it is made of.
- [owner-science-rules](owner-science-rules.md): C2-countable truth, SPINEPS reused never re-run, a second arm never pooled, stay Bayesian, tiers, results not method.
- [figure-format](figure-format.md): line graphs default to the README build-up figure's format (ink, serif, lettered panels, line and marker per series); anatomical graphs in Benzel's style.
- [owner-direction-2026-10-28](owner-direction-2026-10-28.md): his ten prompts of 19:07-19:08 UTC verbatim: the auto-anatomist, the degradation ladder, survival into fluoroscopy.

## Where the work stands
- [item-p-state](item-p-state.md): Panjabi in PyMC, steps a to e merged; the chain of levels (PR 31), the one-vertebra evaluation (PR 32) and the fixed-k NUTS review with the corrected categorical step (PR 33) merged 2026-10-29; the PyMC upstream report drafted on greg's tap (PR 34), posting it is his; why only 32 of the papers' measures.
- [clinical-reread](clinical-reread.md): landed on bordercall main 2026-10-29 (PR 26, 6409164): 43 notes, 44 PDFs, the synthesis, the 106-key measure set (vocabulary.csv, measures.md, series.csv); next the round-2 data faults, validation, prior art.
- [closed-papers-check](closed-papers-check.md): spine-program #239, ready and green, merges only on greg's word.
- [parallel-accounts](parallel-accounts.md): the datamining and model-improvement accounts of 2026-10-27, their handoffs; nothing of theirs on GitHub.
- [paused-threads](paused-threads.md): every stopped or paused piece of work with its PR and handoff; none restarts until greg names it.
- [bordercall-state](bordercall-state.md): bordercall's layout and pull requests at the wrap-up; SchwingNet's pinned copy.

## Findings (all synthetic unless a file says otherwise)
- [findings-naming](findings-naming.md): the exact rule, neighbour identity, level identifiability, the junction predictor.
- [findings-buildup-and-chain](findings-buildup-and-chain.md): the build-up over 32 measures, table size, measurement error, L6/T13, the chain, speed, cadaver power.
- [facets-measure-relations](facets-measure-relations.md): which facets-paper angles mirror or duplicate another, so none is scored twice.
- [findings-corpus-and-data](findings-corpus-and-data.md): the gold and silver tiers (two counts of gold 3), greg's open disagreement, cohorts, licences, data rules.
- [findings-flexray-flux-drr](findings-flexray-flux-drr.md): FleXray on C-ArmLSpine, #391 settled, FluXray, Flux realism, the DRR study's first run.

## Mechanics
- [repo-mechanics](repo-mechanics.md): the four repositories, how to check, push, mark ready and merge in each; the cloud session's limits.
- [grid-words-and-counts](grid-words-and-counts.md): how a grid word is sent and read, the traps, every approved count; nothing sent while the hold stands.
- [papers-in-hand](papers-in-hand.md): where the papers are (never in git); which 20 a script may fetch, which 19 greg uploads again.
- [literature-keys](literature-keys.md): where the Elsevier and Semantic Scholar keys live (secrets, never their values), the open 403.
- [cloud-environment](cloud-environment.md): a new project needs an environment with Full network access; what stays refused even then.

## Older detail kept (2026-10-27/28, superseded where the files above disagree)
- [enhance-pet-whole-count](enhance-pet-whole-count.md): ENHANCE.PET masks read 2026-10-27: 1,557 whole (autoPET 979, Leipzig 379, Careggi 199), ribs on the lumbar variants, the 3 repaired, the SchwingCheck test set.
- [gold3-ct-dataset](gold3-ct-dataset.md): the gold tier 3 CT dataset, #437 and bordercall #17 merged 2026-10-28 06:20 UTC, private page XDGjjGKVcdi2xDht7a689w, reader verdicts not imported.

## gold3-full-spine-rule2
- 2026-10-29: rule 2 (admit every CT whose field shows C2 to the sacrum). SchwingNet #451 merged ~12:30 UTC (main a555855, #443 with it): gold 3 = 1,726 (ENHANCE.PET 1,557, VerSe 18, TotalSegmentator 151 of which 6 to complete), 11 border cases; completion lists sent to the VerSe thread; one grid card posted, wait recommended, nothing sent. File: gold3-full-spine-rule2.md.

## verse-masks-on-grid
- 2026-10-29: VerSe's 374 chosen masks as lossless int16 copies on the grid's data root as verse_masks_2026_10_29 (378 files, 387,949,238 bytes, landed and checked 14:11 UTC; SchwingNet #460); read these instead of fetching VerSe again. File: verse-masks-on-grid.md.
