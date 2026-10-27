# Compare FleXray DRRs to real X-ray corpora: handoff of 2026-10-27

Source: the thread "Compare FleXray DRRs to real X-ray corpora" of the claude.ai project symphony. Written at about 04:55 UTC on 2026-10-27 on the owner's checkpoint word of 04:47 UTC: "YO PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF!"

Done since: the thread "Compare synthetic FluXray against real fluoroscopy" (2026-10-27, on the owner's restart word of 12:47 UTC) carried this branch's commits on its own branch, took BENCH_SKIP_MASKS out and finished the study part below in the pull request that supersedes #418, so what this page lists as unfinished is on main once that pull request is merged; the grid steps below still stand.

The earlier handoff of this work is docs/checkpoints/2026-10-26-drr-comparison/HANDOFF.md. The research is docs/research/drr-domain-gap/README.md (confidential). In public words it is symphony-template's docs/research/drr-domain-gap-method-2026-10-25.md. The memory is docs/memory/drr-domain-gap.md. This page points at them and carries none of their content.

## Done since the last handoff

- beethoven-qa 10.0.0 reads pyproject.toml by its keys. Adding an unproven entry no longer re-proves every module, which is what made #401's gate take 45 minutes.
  - beethoven-qa #15 was merged and tagged v10.0.0.
  - It reached SchwingNet with #413.
  - The owner chose that rule alone on 2026-10-27 at 03:08 UTC, and then asked at 03:09 UTC that every repository in the organization use it.
- Every repository in the organization that carries a copy of beethoven-qa is now on v10.0.0:
  - SchwingNet, through #413.
  - beethoven-research, through #8.
  - beethoven-agents, through #6, merged 04:28 UTC. The owner accepted its four new unproven entries at 04:12 UTC.
  - symphony-template #499 tells new copies to take v10.0.0.
- SchwingNet #414 (merged, 6b2daf4) gave the segmentation job's environment flexray 1.0.2 and nanodrr 0.1.5 beside moosez 3.2.2. The first run, job 40790826, had stopped at `No module named 'fxr'`.

## The grid (the owner's count of 2026-10-26 01:19 UTC: 2 fetches and 2 GPU jobs)

- **Fetches.** fetch moose_weights and fetch hf_flexray_data both completed on 2026-10-26.
- **Segmentation job.** `bench flexray_drr_seg` was sent at 03:39:47 UTC on 2026-10-27 and queued as Slurm 40799505 at commit 6b2daf4. It was RUNNING on voh5 at 04:08 UTC. It has a 12-hour limit; its length is not measured.
  - On 2026-10-27 at 04:31 UTC the owner chose to keep it running rather than pause it (decision card "Keep it running").
  - Earlier copies 40799410 and 40799494 started on the old commit and were cancelled.
- **Comparison job.** `bench flexray_drr_gap` is UNSENT. It is the one comparison job left in the count. It goes once, after the segmentation job ends and its report reads well, and it covers every group.
- **Next steps, in order:**
  1. Read logs/job-schwingnet-status.json on symphony-template's branch grid.
  2. Send the status word once. It clears the running job's grid/logs/HOLD and pulls main.
  3. Send `schwingnet-bench-flexray_drr_seg` again. This reads its report and queues nothing.
  4. If the report ends well, send `schwingnet-bench-flexray_drr_gap` once.
  - The dispatch is grid-accounts.yml on symphony-template (action job, the word, a request name). Read each answer under logs/job-<word>.json on its branch grid.
- **Never send the comparison word while the segmentation job runs.** A running bench's HOLD stops every word's pull, so the grid's checkout stays at 6b2daf4. A comparison sent then would run the old code, which refuses nothing once a moose folder exists and would read half-made MOOSE masks.
- The SPINEPS production array is not approved, and SPINEPS is never run.

## Unfinished: the study running without masks (the owner's question of 04:15 UTC)

The owner asked: "does the CT need to be segmented for flexray drrs to be compared to real xrays? im not saying stop because i have use for them, but i think they tests im doing should be able to run without them".

The answer, checked in FleXray's code:
- No. A DRR's pixels are a projection of the CT. nanodrr scatters each ray sample into its label's channel, background 0 included, and fxr's render_drr sums the channels.
- With the attenuation off, the blocks engine passes no label at all.
- The masks enter only through what FleXray's recipe does with them:
  - crops weighted by the structures they hold, and empty crops dropped;
  - the isocentre placed on a structure's centroid;
  - per-structure attenuation factors.
- They also enter through the replication test, the segmenter pair, and the CT choice and the grid word's refusals, which are code, not physics.

This branch, claude/project-thread-d14v3r, SchwingNet draft pull request #418, carries three commits:

- **2636862, render blocks.** A render-only segmenter value `none`:
  - Not in schwingnet.segmenters.SEGMENTERS, the training blocks or the experiments panel, which need masks.
  - `reads_labels`, a rule that `none` goes only with a recipe reading no labels, and the preset `physical-ct`: FleXray's pose, projection, windowing and axial crops, every crop kept and drawn uniformly, the isocentre the crop's centre.
  - The flexray-runtime engine refuses `physical-ct` under pose flexray-moose (ENGINE_PRESETS).
  - The module gate passed with no counterexample.
- **e1d96d4, render tools.** segmenter `none` renders every CT with no masks folder, keeps every planned crop, and records that no masks were read. Tests prove three things:
  - a view's pixels are identical under none, moose and spineps for the raw recipe, through both engines;
  - render_drr with a label volume equals render_drr with label None;
  - physical-ct keeps every crop and aims at the crop's centre.
  - Results: 282 passed with kornia installed and nothing skipped. tests/test_domain_gap_run.py and tests/schwingnet/test_blocks.py: 72 passed.
- **37b4005, grid.** bench flexray_drr_gap no longer refuses for a missing $DATA/spineps or $DATA/moose, and it reports each segmenter's masks as read or absent. tests/test_gate.py: 128 passed.
  - It ALSO added BENCH_SKIP_MASKS, which tells the job to leave MOOSE out while bench flexray_drr_seg is live. **Remove it before this merges.** word_bench already queues the comparison afterany on a live segmentation job, as on every job that holds the checkout. So the comparison starts after the segmentation ends, when MOOSE's masks are finished, and skipping them then would drop the replication groups for good.
  - Remove the mechanism:
    - drr_gap_masks's skip and BENCH_SKIP_MASKS in grid/gate.sh's word_bench;
    - mask_state's skipped branch and the BENCH_SKIP_MASKS parsing in grid/bench.sbatch;
    - the two tests and the skip_masks_hpcworker wrapper in tests/test_gate.py;
    - the README line's sentence.
  - Keep the per-segmenter "read from" or "not at" lines.

Still to do, the study part: study-brief.md beside this page is the brief, written for an agent. In short:

- segmenters_named leaves `none` out.
- `--skip-masks NAME` for a local run.
- A render group whose segmenter's masks folder is missing is skipped with that reason, while the others render.
- The folder's CT choice is made among CTs with masks under the segmenters still required, or among every CT.
- In groups.json:
  - a new group flexray_drr_ct, the physical-ct recipe, after flexray_drr;
  - fluxray_raw and fluxray_raw_reference on `segmenter=none`. Their pixels are unchanged; the FluXray raw preset itself keeps MOOSE for a replication with masks.
- The pair (flexray_drr_ct, flexray_drr) after the worded pairs, and flexray_drr_ct as a primary endpoint beside flexray_drr and fluxray. It is added before any number was seen.
- The summary stays within 80 lines with 23 groups.
- The research note's sections, and the memory line.
- Then:
  1. An adversarial review written into the PR body under "## Adversarial review".
  2. Mark the PR ready in a call of its own.
  3. Merge on green with the head sha copied from git.
  4. Update the public note in symphony-template, method only.
  5. Then the grid steps above.

**Groups and masks:**
- No masks: flexray_drr_ct, fluxray_raw, fluxray_raw_reference, and every non-render group (fluxray, ts_drr_project, devcorpus, fluorogen and the real corpora).
- MOOSE's masks: flexray_drr, flexray_replica and flexray_reference.
- SPINEPS's existing masks: flexray_spineps.

## How things were run here

- **Python.** A venv with numpy, torch on the CPU, fxr 1.0.2 with kornia, nanodrr, beartype, icontract, scikit-learn, nibabel and crosshair. Run tests as `PYTHONPATH=src:vendor/beethoven-qa/src python -m pytest -q <files>`, and the module gate as `python -m beethoven_qa gate --module schwingnet.<module>`. download.pytorch.org is refused by the proxy, so torch came from PyPI.
- **This push skipped the pre-push gate.** It was made with SKIP_GATE=1 at the checkpoint, since the gate would have held the push for many minutes. CI's check and gate run on the draft and are the verdict.
- **Merging.** Merge a SchwingNet PR with `gh api -X PUT repos/OpenSpineConsortium/SchwingNet/pulls/N/merge -f sha=<head from git> -f merge_method=merge`, under the standing permission. Mark one ready with `gh api -X POST repos/OpenSpineConsortium/SchwingNet/pulls/N/ccr/ready_for_review`.
