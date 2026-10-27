# Handoff: the Flux realism edit, its measurement and its finetune (2026-10-26)

Written 2026-10-26 about 03:05 UTC from the project thread "Finetune Flux Realism for X-rays", at the owner's checkpoint of 03:01 UTC ("please push as much as possible now im running out of tokens then write a handoff for checkpointing asap!"). The work is on the branch claude/project-thread-vd6p1l, pull request #406, marked ready with its adversarial review in the body and auto-merge armed by the SymphonyBoard App. Nothing was sent to the grid by this thread: no fetch, no job, no training. The counts the owner approved are listed below as approved and unsent, so the next session sends them in order once #406 is on main and never asks for them again.

## State at the second checkpoint, 2026-10-27 04:50 UTC

Written at the owner's checkpoint of 2026-10-27 04:47 UTC ("PLEASE CHECKPOINT ALL SESSIONS AND PUSH ALL FILES AND WRITE A HANDOFF SO A NEW ACCOUNT CAN PICK UP WHERE THESE LEFT OFF!"). Where this section and the rest of the page differ, this section holds; the rest is kept as it was written on 2026-10-26.

- #406 merged on 2026-10-26 at 03:51 UTC (its last head 3ffaa05, on main since): src/schwingnet/realism.py, tools/realism.py, grid/realism.sbatch, the word `realism <stage>`, the fetch rows and this page are all on main. Nothing of this work is left on a branch.
- FluXray has landed: the DRR comparison thread sent `schwingnet-fetch-hf_flexray_data` under its own count on 2026-10-26 (Slurm 40788810, completed in 4 min 28 s), and the status read of 2026-10-27 04:08 UTC (request drr-status-0407-d14v3r) shows hf_flexray_data at 19 GB under the data root. It is not to be fetched again.
- Still approved and still unsent, by the owner's tap of 2026-10-26 01:58 UTC: the fetches aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB), hf_flux2_klein_4b and hf_flux2_klein_base_4b; hf_flux2_klein_9b once the owner has accepted its licence; then the GPU jobs realism edit, stats, lora and eval, each once and in turn. The grid record lists no fetch job of any of them and no realism job, so none was sent by any thread. The thread stopped at the first checkpoint and sent nothing after it.
- The room at 2026-10-27 04:08 UTC: 4,393 GB free, nothing owed to running fetches; the DRR comparison thread's job bench_flexray_drr_seg (40799505) was running. The size rule decides each fetch again on the node when its job starts.
- The next session starts at step 2 of How to restart below; step 1 is done.

## Goal

The owner's ask of 2026-10-25 23:2x UTC: find and implement CSAIL's trained version of Flux realism, then reproducibly make a finetuned instance whose X-rays are numerically indistinguishable from the FluXray dataset, addressing the LinkedIn review's limitations, resolution first. The programme that holds the method is docs/research/flux-realism/README.md (confidential, this repository); the public findings are symphony-template's docs/research/flux-realism-for-xrays-2026-10-25.md (its #497, merged 2026-10-26 01:35 UTC). The project memory is docs/memory/flux-realism-edit.md.

## Done

- Settled: CSAIL trained no realism model. FluXray is FLUX.2 klein-9B run zero-shot over DRRs of the MOOSE-labelled ENHANCE.PET CTs, with the settings the programme note records from the paper's appendix; the paired-Dice filter's raw-only U-Net is unreleased and the flux000 member stands in. The reproducible object is therefore the recipe, pre-registered before any run.
- In #406 (head b901774 at this checkpoint; main merged in twice, the second time resolving grid/gate.sh against #404's bordercall word): src/schwingnet/realism.py (contracted, proven by the gate, 31 tests), tools/realism.py (poses, split, render, edit, filter, fluxray-export, stats, pairs, lora-config, measure; 15 tests), grid/realism.sbatch and the gate word `realism <stage>` (edit, stats, lora, eval; one GPU job each; refused until its inputs have landed and the stage before it ended in exit 0), the owner-list fetch rows in grid/run-platform-fetch.sh, grid/enhance-pet-labels.json, ENHANCE.PET 1.6k reclassified non-commercial in data/licences.json with the derived pages written again, pyproject.toml's unproven entry for lora_config, the programme note, the memory and its index line.
- CI on head b901774 at 03:00 UTC: check, standards and owner-ok green; the gate job was running (started 02:35 UTC). GitHub merges the pull request when the gate ends green, since auto-merge is armed. The commit that carries this handoff restarts CI on the branch; the gate is skipped at the push (SKIP_GATE=1, said in the commit) because the module was proven an hour earlier and CI's gate is the verdict.

## Approved and unsent

The owner's tap of 2026-10-26 01:58 UTC on the thread's decision card, "5 fetches + 4 GPU jobs", approved:

- Fetches, each once, each through symphony-template's grid-accounts.yml (action job, job `schwingnet-fetch-<id>`): aws_enhance_pet_ct (177 GB), aws_enhance_pet_labels (2.5 GB), hf_flux2_klein_4b and hf_flux2_klein_base_4b now; hf_flux2_klein_9b only after the owner has accepted the FLUX Non-Commercial License on https://huggingface.co/black-forest-labs/FLUX.2-klein-9B under the account whose token the grid holds, or the hub refuses the download.
- GPU jobs, each once, in turn, each after the one before ended sane: `schwingnet-realism-edit` once the fetches have landed (the gate refuses before), then `schwingnet-realism-stats`, `schwingnet-realism-lora`, `schwingnet-realism-eval`. Every stage prints its report logs/REALISM-<stage>.md on the next send.
- The FluXray fetch (hf_flexray_data, 19 GB) is not this thread's: the DRR comparison thread sends it once under its own card (01:19 UTC, "2 fetches + 2 GPU jobs"), after #401 and #406 are on main. The realism stats, lora and eval stages read it, so they wait for that landing too.

None of these was sent. The grid record last read (symphony-template branch grid, logs/job-schwingnet-status.json, 2026-10-25 23:41 UTC, request anomaly-route-status-2342) showed 4,416 GB of room and no running fetch; the size rule on the node decides each fetch again when its job starts.

## How to restart

1. Done: #406 merged on 2026-10-26 at 03:51 UTC. Fetch and read the board before anything else all the same.
2. Read logs/job-schwingnet-status.json on symphony-template's branch grid; send the status word again only if a stage needs a fresh read.
3. Dispatch the four fetches, one run each: workflow grid-accounts.yml on OpenSpineConsortium/symphony-template, ref main, inputs action=job, job=schwingnet-fetch-aws_enhance_pet_ct, request=realism-<id>; the same for aws_enhance_pet_labels, hf_flux2_klein_4b and hf_flux2_klein_base_4b. Tell the DRR comparison thread when they go, so the two threads' reads of the room do not cross.
4. When the owner says the klein-9B licence is accepted, send schwingnet-fetch-hf_flux2_klein_9b.
5. Once the fetches have landed (the fetch jobs' logs, read by the status word), send schwingnet-realism-edit, then each later stage after the report of the one before ends in exit 0.
6. Record each send in the thread's checklist and in the project memory, and never send a word twice for one read.

## Open

- Settled: the gate passed and #406 merged on 2026-10-26 at 03:51 UTC; FluXray landed the same day by the DRR comparison thread's send.
- Whether the owner has accepted the klein-9B licence; until then the edit stage runs on the Apache klein-4B, as the recipe's deviation notes say.
- The owner's decision on the licence split (item 15 of #391), never a blocker. #401, the DRR domain-gap study, is merged and its FluXray fetch has landed.
