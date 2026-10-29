---
name: findings-flexray-flux-drr
description: What FleXray is and did on C-ArmLSpine, the settled answers of issue #391, how FluXray was made (zero-shot, no realism model trained), the Flux realism programme, and the DRR domain-gap study's first run
metadata:
  type: project
---

Sources: the restart kit's FINDINGS.md sections 6 to 8; SchwingNet docs/research/flexray-audit-companion.md, docs/research/flux-realism/README.md, docs/research/drr-domain-gap/README.md, docs/checkpoints/2026-10-28-drr-comparison/HANDOFF.md (#442).

- FleXray (greg's fork OpenSpineConsortium/FleXray): one 2D UNet at 256 px with 61 sigmoid channels, C1 to L5 plus the sacrum and other anatomy; no L6 or T13 channel (an L6 body was learnt as not a vertebra). Code MIT; weights and FluXray CC BY-NC 4.0.
- On C-ArmLSpine (Slurm 40781570), given the 1,627 truth boxes, the flagship named 99.14% (Wilson 98.56 to 99.49), the ensemble 99.63%, flux000 (no FluXray) 98.22%: naming given a body, not detection; the view split unread; L6 boxes left out.
- #391, settled by greg on 2026-10-25 20:49 UTC: the window is the exposure field in vertebral bodies and the offset the commanded step; the test sweeps 0.5 to 4 bodies of overlap in quarter steps; the non-optimal settings are the minima either side of the maxima, rounded to half bodies; nine-inch field main, twelve-inch secondary. The linker (spine-program's sweep_map.py) must be ported into SchwingNet first.
- FluXray: 138,063 edited renders of 143,730 (1,597 MOOSE-segmented ENHANCE.PET CTs x 90 poses), FLUX.2 klein-9B zero-shot (4 steps, one prompt), stored at 256 px (a pixel is 1.25 to 2.21 mm); held on the grid since 2026-10-26; never fetch it again.
- Flux realism: reproduce the edit, measure the gap, train a LoRA on klein-base-4B by subject split (src/schwingnet/realism.py, tools/realism.py, grid word `realism <stage>`); code on main; nothing sent; klein-9B needs greg's licence click; klein-9B's outputs are non-commercial, klein-4B is Apache 2.0.
- DRR domain-gap study: first run 2026-10-28 03:08 to 03:26 UTC (716 of 716 units, 26 CTs a render group). Six of the ten synthetic groups are told from real fluoroscopy and film in every feature space (AUC lower bound 0.82 to 1.00), the test near its ceiling (real against real median 1.00 in FleXray's space). FluXray and the Flux-edit pair are not measured. "Not replicated" rests on q 0.048 over the contrasts alone; the family greg chose at 16:28 UTC ("Rerun, family as PREREG says") most likely lifts it over 0.05. DeepFluoro's 14 persons are DICOM ids over 6 specimens. No result is final; the CLAIM report waits for greg's 39 answers; the rerun needs the gate fix ([[grid-words-and-counts]]).
- Renders transfer for naming, not detection: a render-only detector finds 71.67% of bodies on film against 99.14% for a film-trained one.

**Why:** each of these was re-derived at least once by a thread that had not read the notes.
**How to apply:** read the programme note before touching FleXray, realism or the DRR study, and the grid record before any send; see [[paused-threads]].
