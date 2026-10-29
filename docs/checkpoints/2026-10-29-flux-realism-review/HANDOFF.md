# Handoff: the FluXray reproduction, paused mid-review

Source: the thread "Reproduce the FluXray dataset", 2026-10-29, paused at 12:07 UTC when the owner ranked the threads ("The threads evaluating the Bayesian generator and the data are the most impoetanr, then the autoanatomist, then the gold tier ct data, the rest are low priority"). Nothing restarts until the owner names this work again.

## Where it stands

- The count (the owner's tap of 2026-10-29 02:35 UTC): three fetches and two GPU jobs. The three fetches were sent once each at 02:55 to 02:57 UTC and all ended COMPLETED 0:0 (labels 40860402, 12 GB; CT 40860413, 198 GB; klein-9B 40860425, 53 GB; status read 03:51 UTC). They are spent and are never sent again. The two GPU jobs, `realism edit` and then `realism stats`, have never been sent.
- The code: draft pull request #456, branch claude/project-thread-bft0k4. It freezes docs/research/flux-realism/PREREG.md (sha256 580c4528... beside it), runs both stages as RealismFlow (flows/realism.py) through flows/launch.py, and writes and checks the run's CLAIM 2024 and REFORMS report (tools/realism_report.py, the study flux-realism of tools/report.py).
- The branch carries #454's head (45a145c, the launcher's frozen-PREREG hold, flows/stage.py) merged in, because the flow is written against that API. #456 must never merge before #454; the DRR thread's #455, which also changes tools/report.py, lands before both (agreed 03:50 UTC).

## The review

An adversarial review of #456 (five lenses, two skeptics each) confirmed 17 findings and refuted 10. They are in review-findings.json beside this file, grouped by the files that fix them: tool, grid, report and flow (the flow key repeats the findings the flow's part answers).

Fixed on this branch, each with tests, but no independent check has read them yet (the checking agents were cut by the usage limit, then stopped on the owner's ranking):

- tool (tools/realism.py, tests/test_realism_tools.py, 36 pass): the permutations shuffle labels within each sample's images where the two sets show the same samples, subjects whole elsewhere; every comparison records the principal components it used and the strata; a subject is eligible only with 4 samples on the paper's grid, and inputs, split and the draw refuse a short sample; every .npy and JSON is written whole through a .part and os.replace, a sample counts as rendered or edited only with its manifest or edits.jsonl row and its files, and a half-written one is redone; kept/ holds exactly the filter's kept edits; a new `environment` subcommand records the stats job's own versions and the weights' sha256.
- grid (grid/gate.sh, grid/realism.sbatch, tests/test_gate.py, 154 pass): a killed job's unfinished report is printed and queues nothing at the same commit; the job writes its report on TERM; the flow's lines reach the report through Metaflow's prefix; the report names only its own run's folder and summary.
- flow (flows/realism.py, tests/test_realism_flow.py, 10 pass): each run keeps its own folder, <stage>-<key>-<run id>, so a resume carries on where it began and a new run starts empty; the edit's key reads the ThunderDB, the CTs and the truth, the stats' key the bundle and the ImageNet weights; the stats start records its environment; RECORD.json names the run that made the folder and the run that ended it; an edit short of its draw ends with verdict 1, so the stats refuse it.
- DEVIATIONS.md holds three dated entries after the freeze, decided before any image or number: the permutations by sample, min(64, dimension) components (physics 57), eligibility needing 4 on-grid samples.

Not fixed: the report group (findings in review-findings.json under report, and the owner's word of 03:35 UTC on the DRR study, "why would I answer these question instead of having a real meta flow run generate them?", which asks the report to answer by code every item the run's files hold). A first attempt rewrote tools/realism_report.py whole and stopped before running anything; the rewrite is realism-report-rewrite.patch beside this file, against the branch's version, untested, and written before the tool's and the flow's changes above. The branch keeps the earlier, tested report, which still mixes the two jobs' environments and reads a dirty tree as met.

## Next, in order, once the owner names this work

1. Read the board and the open pull requests: whether #455 and #454 merged, and what #454 changed after 45a145c.
2. Finish the report group: apply realism-report-rewrite.patch to tools/realism_report.py, make it read what the tool and the flow now write (stats.json's components and strata, environment.json, RECORD.json's ended_in, where and short, ENDED.json's run and started_run, DEVIATIONS.md's three entries), update tests/test_realism_report.py and trim data/reporting/studies/flux-realism.json to the owner's own items; then delete the patch and review-findings.json from this folder.
3. Run one independent adversarial check of all four groups' fixes, and fix what it confirms.
4. Merge main in once #455 and #454 have merged, run the realism tests and `bash scripts/check.sh` in a scratch copy, write the review into #456's "## Adversarial review" section, mark it ready in a call of its own, and merge once green.
5. Only then, after a status word: `schwingnet-realism-edit` once, and `schwingnet-realism-stats` once after the edit ends 0:0, each through symphony-template's grid-accounts.yml (action job). Record each send in the thread's memory.
