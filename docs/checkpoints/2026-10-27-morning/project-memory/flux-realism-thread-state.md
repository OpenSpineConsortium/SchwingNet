---
name: flux-realism-thread-state
description: Flux realism thread: #406 merged, FluXray landed, 5 fetches + 4 GPU jobs approved 2026-10-26 and still unsent at the 2026-10-27 checkpoint; handoff #417 merged
metadata:
  type: project
---

Thread "Finetune Flux Realism for X-rays" (cmsg_014WUU19NHgHPhf7QetT9cbSAe6wnnSqEmg92SHjFbih8K), 2026-10-25 to 2026-10-26.

- Settled: CSAIL trained no realism model. FluXray (VictorButoi/flexray-data, folder FluXray, 19 GB, CC BY-NC 4.0) is FLUX.2 klein-9B run zero-shot (4 steps, bf16, guidance 1.0, one prompt, 90 poses, SDD 1250 mm, 0.6 mm pixels at 1024, stored at 256) over DRRs of ENHANCE.PET 1.6k CTs with MOOSE labels, filtered by a paired soft-Dice rule; the filter's raw-only U-Net is unreleased.
- SchwingNet PR #406 (branch claude/project-thread-vd6p1l, ready, auto-merge armed); symphony-template #497 merged 2026-10-26 01:35 UTC as cf72392: src/schwingnet/realism.py, tools/realism.py, grid/realism.sbatch, gate word `realism <stage>` (edit, stats, lora, eval; GitHub word schwingnet-realism-<stage>), fetch rows hf_flexray_data, hf_flux2_klein_4b/9b/base_4b/base_9b, aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB) in grid/run-platform-fetch.sh OWNER_LIST (fetch word schwingnet-fetch-<row>). Programme note: SchwingNet docs/research/flux-realism/README.md (confidential); public note symphony-template docs/research/flux-realism-for-xrays-2026-10-25.md.
- Counts APPROVED by the owner's tap at 2026-10-26 01:58 UTC ("5 fetches + 4 GPU jobs"): fetches aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB), hf_flux2_klein_4b, hf_flux2_klein_base_4b now and hf_flux2_klein_9b once the owner has accepted the FLUX NC licence on the hub; GPU jobs realism edit, stats, lora, eval, each once, in turn, after the one before ends sane; all sent only once SchwingNet #406 is on main, each send after reading logs/job-schwingnet-status.json on symphony-template branch grid. The FluXray fetch (hf_flexray_data) is the DRR comparison thread's to send once (its card of 01:19 UTC), after #401 and #406 are on main. Do not ask the owner again.
- ENHANCE.PET 1.6k reclassified non-commercial in data/licences.json (autoPET and Tuebingen sites CC BY-NC 4.0; Leipzig, Careggi, UC Davis CC BY 4.0).
- klein-9B needs the owner's licence click on the hub under the grid token's account; the Apache klein-4B and klein-base-4B need none.

**Why:** a later thread or the coordinator otherwise re-derives the recipe, re-asks the owner for counts already asked, or sends the FluXray fetch twice.

**How to apply:** read the programme note before touching realism; coordinate any FluXray fetch with the DRR comparison thread; see [[grid-status-reads-and-pr-watching]] for the status word and [[schwingnet-pre-push-gate-duration]] before pushing to SchwingNet.

## State at the second checkpoint, 2026-10-27 04:55 UTC
- #406 MERGED 2026-10-26 03:51 UTC (head 3ffaa05); the realism code, grid word, fetch rows and the handoff docs/checkpoints/2026-10-26-flux-realism/HANDOFF.md are on main.
- FluXray LANDED 2026-10-26 (DRR thread's send, Slurm 40788810, 19 GB); never fetch it again.
- Still approved and UNSENT (grid branch logs hold no realism or ENHANCE/klein fetch record at 04:48 UTC): fetches aws_enhance_pet_ct, aws_enhance_pet_labels, hf_flux2_klein_4b, hf_flux2_klein_base_4b; klein-9B after the owner's licence click; then realism edit, stats, lora, eval in turn. Room 4,393 GB at 04:08 UTC.
- Handoff update is SchwingNet #417, MERGED 2026-10-27 04:57 UTC (branch claude/project-thread-vd6p1l restarted from main b8367ee, commit b890bf4; also corrects docs/memory/flux-realism-edit.md's "no count"). Thread stopped at the owner's checkpoint of 04:47 UTC.
- Dispatch: actions_run_trigger run_workflow, OpenSpineConsortium/symphony-template, grid-accounts.yml, ref main, inputs {action: job, job: schwingnet-fetch-<id>, request: realism-<id>}, one dispatch each; the gate refuses the edit until its inputs have landed.
