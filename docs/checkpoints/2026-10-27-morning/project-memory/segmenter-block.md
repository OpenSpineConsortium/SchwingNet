---
name: segmenter-block
description: The owner's words of 2026-10-26 on CT segmentations (MOOSE only when replicating FleXray's dataset, SPINEPS for production, the segmenter a configurable block) and the spelling agreed between the DRR comparison and anomaly-route threads
metadata:
  type: project
  modified: 2026-10-26T00:45:49.085Z
---

Owner's words (greg, 2026-10-26): 00:17 UTC "MAKE SURE THESE USE SPINEPS SEGMENTATIONS AS WELL NOT TOTAL SEGMENTATOR! EXISTING ONES IF POSSIBLE"; 00:26 UTC "WHEN REPLICATING THEIR DATA SET YOU SHOULD USE MOOSE BUT FOR MY PRODUCTION RUNS I WANT SPINEPS, FURTHER THE SEGMENTATION MODEL ON THE UNANNOTATED DATA SHOULD DEFINITELY BE A CONFIGURABLE BLOCK! MAKE SURE THE DIFFERNCE IN THE LABELS IS HANDLED CORRECTLY EVERYWHERE!"

Agreed spelling (DRR comparison thread and anomaly-route thread, 00:27 to 00:29 UTC): block key `segmenter`, values `spineps` (default, production) and `moose` (only when replicating FleXray's own dataset); TotalSegmentator is not a value. SPINEPS masks are read in the VerSe alphabet (C1..L5 = 1..24, L6 = 25, sacrum 26, coccyx 27, T13 = 28) and rewritten to vertebra_c1..c7, vertebra_t1..t13, vertebra_l1..l6, sacrum; `moose` reads MOOSE ids through FleXray's configs/datasets/MOOSE.yml stored_labels (vertebra_l6 = 83, no T13). The one home for names, alphabet, ids and maps is src/schwingnet/segmenters.py (SchwingNet #401, branch claude/project-thread-7ltron); blocks.py and render_blocks.py import it; tools/render_blocks.py reads a mask file by scheme. Existing masks only; SPINEPS is never run (its production array is not approved); MOOSE masks do not exist on the grid, so the replication needs a moosez run as its own GPU job (bench flexray_drr_seg) and a fetch of moosez's model zips (row moose_weights), both awaiting the owner's word (decision card in the DRR thread, 00:4x UTC).

FleXray paper facts (arXiv 2609.26756v2, uploaded by the owner): "MOOSE" is the ENHANCE-PET 1.6k dataset (1,597 whole-body CTs) labelled by running moosez; FluXray's raw renders used 90 fixed poses (y 650/900/1150 mm, z -300..200 by 100, alpha 0/+-45/+-90, x 0, beta gamma 0, SDD 1250, 0.6 mm pixels, 1024 px, volume-centre isocentre, attenuation randomisation off) before the FLUX.2 klein 9B edit; the packs' crops are 512x512x256 at 50 percent overlap.

**Why:** two threads build on the same block; a second spelling would split the pack and the render.
**How to apply:** import from segmenters.py rather than spelling a label; name the segmenter in a group's or a stage's blocks; never run a segmenter inside a pack or a render.
