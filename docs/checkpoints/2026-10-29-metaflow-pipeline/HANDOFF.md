# Handoff: finish and smoke test the Metaflow pipeline (2026-10-29, 23:07 UTC)

Thread "Finish and smoke test the Metaflow pipeline" of the claude.ai project symphony_2, written on the owner's word of 23:05 UTC ("im about to run out of fable please just write what you have now"). Confidential with the rest of this repository.

## Done and merged

- #484 (merged 19:24 UTC; #466 closed as superseded): ExperimentFlow and LatencyFlow on main, the seven review fixes of docs/checkpoints/2026-10-29-metaflow-words/HANDOFF.md section 3, docs/research/experiments/PREREG.md frozen a second time, and grid/gate.sh's submit refusing, with exit 90, any gpu-class job whose script flows/registry.txt does not name in its fourth column. `bench` for the three public models (bench.sbatch) and `anomaly timing` (anomaly.sbatch) are refused until each is moved onto a flow (that handoff's section 4, items 3 and 4, still to build).
- The pipeline's grid smoke had already passed on 2026-10-25: `sweep synthetic` (40781593) and `sweep real` (40781617), verdict 0 through flows/launch.py.

## On the grid, waiting

- `sweep synthetic` at main d6f244d, job 40870220, sent on the owner's pick of 18:42 UTC; at 23:02 UTC it waited on Priority for a GPU.
- On the owner's word of 22:52 UTC DRR run 3 was moved behind it: shards 40867573 and merge 40867575 cancelled (prepare 40867572 had completed), the study re-sent as prepare 40872122, shards 40872123 and merge 40872125, afterany 40870220, 40870822 (gold tier 3 completion) and 40872077 (morphometry enhance). The DRR run 3 handoff's job ids are superseded by these.

## Next

1. Read the status word (symphony-template grid-accounts.yml, action job, job schwingnet-status; logs/job-schwingnet-status.json on its branch grid), no faster than every 20 minutes, and report the sweep's verdict.
2. Once the auto-anatomist thread's #483 merges with AutoanatomistFlow, send `autoanatomist phantom_smoke` as one CPU job: the owner's pick on the card of 18:39 UTC.
3. Port `bench` (public models) and `anomaly timing` onto flows, as the metaflow-words handoff section 4 says.
