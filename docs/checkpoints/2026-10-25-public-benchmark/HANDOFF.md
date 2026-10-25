# Handoff: benchmarking the public spine and pelvis models (FleXray, xvr)

Source: the project thread "Compare lab's X-ray learning to SchwingNet", 2026-10-25. The owner checkpointed the thread at 92 percent of the weekly limit. Everything below is committed and pushed, and nothing lives only in the session that wrote it.

## Goal

Score the public models that name spine levels or segment the pelvis, as their authors published them, against this record's own numbers. The owner gave the word and the count on 2026-10-25 at 03:24 UTC ("ok yes absolutely do those experiments"): three fetches and three GPU jobs, no more. None of the jobs trains or tunes anything. FleXray's weights are CC-BY-NC and xvr's data is CC-BY-NC-ND, so they are benchmark rows only and never part of a SchwingNet network.

The plan and its reasoning are docs/research/public-spine-and-pelvis-models-to-benchmark.md (#286, corrected in #288). The question that matters is section 2's job 1. It asks whether FleXray names lumbar levels on C-ArmLSpine from one frame, as the reported stack does (96.4 percent lateral, 43.7 percent AP), or fails, as FluoroSAM did on the twin (Dice 0.16 to 0.25).

## What landed

- #279 and #281 (merged): the analysis of the Unberath and Killeen lab's X-ray learning, and the passage that cites FluoroSAM directly.
- #286 (merged): the benchmark plan note.
- #288 (merged, closing #287) added:
  - three fetch words on the owner's list in grid/run-platform-fetch.sh;
  - the gate word `bench <name>` (grid/gate.sh), which queues one GPU job per model and keeps its report;
  - the job itself, grid/bench.sbatch, which installs `flexray==1.0.2`, or xvr at a pinned commit, into a throwaway environment beside train-gpu's;
  - the scoring, tools/bench_public.py with tests/test_bench_public.py;
  - the note corrected: job 3 is xvr on DeepFluoro alone, because xvr's Ljubljana is the cerebral set.
- symphony-template #464 (merged): grid-accounts.yml can send `schwingnet-bench-<name>`.

## Where it stopped

The thread sent the three fetches at 09:28 UTC on 2026-10-25, on the owner's ask in the thread. Each was submitted, with the size rule's room read first:

| Fetch word | Slurm job | Size the source states |
|---|---|---|
| hf_flexray_weights | 40780681 | about 0 GB |
| hf_xvr_data | 40780691 | 4.8 GB |
| hf_xvr_models | 40780696 | 3.7 GB |

The gate reported about 4.4 TB free under the quota at the time. The submissions are recorded on symphony-template's branch grid, in logs/job-schwingnet-fetch-<id>.json. Whether the fetches have finished was not read before the checkpoint.

No bench job has been sent. The owner approved all three, but they wait for their fetches. The gate refuses a bench job, with exit 2 and the name of the missing fetch, until its inputs are there.

## Next steps, in order

1. Send `schwingnet-status`. In symphony-template's Actions, open grid-accounts.yml (https://github.com/OpenSpineConsortium/symphony-template/actions/workflows/grid-accounts.yml), press Run workflow, and enter action `job` and job `schwingnet-status`. Read the result on the grid branch: `git fetch origin +refs/heads/grid:refs/remotes/origin/grid && git show origin/grid:logs/job-schwingnet-status.json`. Confirm that jobs 40780681, 40780691 and 40780696 have ended and their data roots hold files. Never resend a fetch without reading the status first.
2. Once the three fetches are in, send each bench word once, the same way:
   - `schwingnet-bench-flexray_carmlspine`
   - `schwingnet-bench-flexray_deepfluoro`
   - `schwingnet-bench-xvr_deepfluoro`

   A thread may dispatch these itself on the owner's ask; the owner's word and count already cover them.
3. When a bench job ends, send its word again. That prints grid/logs/BENCH-<name>.md and queues nothing. Results also land under the bench root of each job.
4. Write the numbers into section 2 of the note by an issue and a pull request of their own:
   - accuracy over detected bodies and over all bodies, with Wilson intervals set beside the record's own intervals, never mixed with them;
   - every FleXray member and the ensemble;
   - DeepFluoro Dice under both intensity readings, against the published 0.916;
   - xvr's median mTRE against the published 1.1 mm.
5. Follow-ups that are not counted and need the owner's word first:
   - the spine Ljubljana 2D-3D-GS level bank, from its given poses (no GPU);
   - FluoroSAM's weights and the twin's frames, which wait on #163.

## First prompt for the next account

"Read docs/checkpoints/2026-10-25-public-benchmark/HANDOFF.md in OpenSpineConsortium/SchwingNet and carry on from its Next steps: check the three fetches with schwingnet-status, send the three bench words once they have landed (already approved, one job each), then write the results into docs/research/public-spine-and-pelvis-models-to-benchmark.md by pull request."
