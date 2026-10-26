---
name: flux-realism-thread-state
description: Flux realism thread (SchwingNet realism module, grid word realism <stage>, fetch rows for klein, FluXray and ENHANCE.PET); no CSAIL-trained model exists; counts not yet approved
metadata:
  type: project
---

Thread "Finetune Flux Realism for X-rays" (cmsg_014WUU19NHgHPhf7QetT9cbSAe6wnnSqEmg92SHjFbih8K), 2026-10-25 to 2026-10-26.

- Settled: CSAIL trained no realism model. FluXray (VictorButoi/flexray-data, folder FluXray, 19 GB, CC BY-NC 4.0) is FLUX.2 klein-9B run zero-shot (4 steps, bf16, guidance 1.0, one prompt, 90 poses, SDD 1250 mm, 0.6 mm pixels at 1024, stored at 256) over DRRs of ENHANCE.PET 1.6k CTs with MOOSE labels, filtered by a paired soft-Dice rule; the filter's raw-only U-Net is unreleased.
- SchwingNet draft PR #406 (branch claude/project-thread-vd6p1l; commits 039bb7b, dade124, 2b70220 review fixes); symphony-template #497 merged 2026-10-26 01:35 UTC as cf72392: src/schwingnet/realism.py, tools/realism.py, grid/realism.sbatch, gate word `realism <stage>` (edit, stats, lora, eval; GitHub word schwingnet-realism-<stage>, symphony-template #497), fetch rows hf_flexray_data, hf_flux2_klein_4b/9b/base_4b/base_9b, aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB) in grid/run-platform-fetch.sh OWNER_LIST (fetch word schwingnet-fetch-<row>). Programme note: SchwingNet docs/research/flux-realism/README.md (confidential); public note symphony-template docs/research/flux-realism-for-xrays-2026-10-25.md.
- Counts APPROVED by the owner's tap at 2026-10-26 01:58 UTC ("5 fetches + 4 GPU jobs"): fetches aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB), hf_flux2_klein_4b, hf_flux2_klein_base_4b now and hf_flux2_klein_9b once the owner has accepted the FLUX NC licence on the hub; GPU jobs realism edit, stats, lora, eval, each once, in turn, after the one before ends sane; all sent only once SchwingNet #406 is on main, each send after reading logs/job-schwingnet-status.json on symphony-template branch grid. Earlier state: The FluXray fetch (hf_flexray_data) is approved under the DRR comparison thread's card (01:19 UTC, "2 fetches + 2 GPU jobs") and that thread sends it once, after SchwingNet #401 and the realism rows are on main. The realism ask (five more fetches, four GPU jobs) was answered by the owner's tap at 01:58 UTC (option A); do not ask again.
- ENHANCE.PET 1.6k reclassified non-commercial in data/licences.json (autoPET and Tuebingen sites CC BY-NC 4.0; Leipzig, Careggi, UC Davis CC BY 4.0).
- klein-9B is gated under the FLUX Non-Commercial License: the owner accepts it on huggingface.co under the account whose token is ~/.hf/token.env on the grid before hf_flexray's 9B fetch can land; the Apache klein-4B and klein-base-4B need no click.

**Why:** a later thread or the coordinator otherwise re-derives the recipe, re-asks the owner for counts already asked, or sends the FluXray fetch twice.

**How to apply:** read the programme note before touching realism; coordinate any FluXray fetch with the DRR comparison thread; see [[grid-status-reads-and-pr-watching]] for the status word and [[schwingnet-pre-push-gate-duration]] before pushing to SchwingNet.
