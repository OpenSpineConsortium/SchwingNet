---
name: enhance-pet-whole-count
description: ENHANCE.PET 1.6k masks read 2026-10-27: 1,557 whole (1,560 with 3 repaired), rib results on the lumbar variants, the SchwingCheck test set in /mnt/project-files/enhance-pet-repair/
metadata:
  type: project
  modified: 2026-10-27T21:54:35.163Z
---

On 2026-10-27, on the owner's cards (vertebra masks 16:05 UTC, rib masks 17:41 UTC), ENHANCE.PET's 1,597 vertebra masks (381,439,888 bytes) and rib masks (312,882,241 bytes) were read in the cloud container only, never the grid. bordercall holdings/count_enhance_pet.py recounts everything; notes are bordercall holdings/gold-tier-3.md and SchwingNet docs/research/enhance-pet-gold-tier-3.md.

**1,557 whole C2-to-sacrum**: autoPET 979 (865-900 persons), Leipzig 379, Careggi 199 (no person ids). 1,517 strict; 39 have L4 on the sacrum; 0529 names L6 in L5's place (skipped label); 68 name L6; 37 no C2. Gold 3 = the 1,557 with published labels. Leipzig+Careggi whole CTs = 45,207,300,328 bytes (not held).

Owner rule, 17:10 UTC: "these should absolutely not be excluded they may be examples of sacralization anomalies if the sacrum is view!" Never drop a spine for a missing or extra lumbar label.

Ribs (lowest rib's contact tally; two scripts agree on 420 sides): controls 96 rib 12 on T12, 3 rib 11 on T11, 1 no contact. Four-lumbar 39: 24 twelve ribs on T12 (sacralization candidates; ribs can't tell from a short column), 8+1 eleven ribs, 4 no contact, 2 shifted labels (0005 open, 0245 error). L6 67: 51 twelve ribs, 14 rib 13 on the L1 label (no T13 in the scheme; ribs cannot place the extra body), 2 off (0603 split T6 = error, 1336 open). Errors: 0529, 0245, 0603; open: 0005, 1336. 3-D: in all 39 no-L5 spines L4 touches the sacrum (0.7-1.2 mm); controls never under 2.3 mm across a labelled L5. Small L5 labels for a look: 0179, 0213, 0270, 1240. Merged SchwingNet #434 and bordercall #16 (holdings/count_enhance_pet.py).

The 3 left out, repaired (owner 17:42 "try to repair these with whatever segmentation model generated the spinal masks dont just throw them away"; 17:54 "dont forget these 3 because i want to use them as a test of SchwingCheck's ability to correct segmentations"): 1347 lower T1 piece is T9; 1134 has 11 rib-bearing vertebrae (T1-T11, L1-L5), a real variant; 1283 MOOSE rerun plus stray cleanup (machine mask). All three held at gold 4 until a person checks. MOOSE clin_ct_vertebrae (moosez-v.3.1.3, sha256 a1ad0e8c...) was trained on all 1,683 incl. these. Nine more unrepaired candidates listed in the test-set README: 0529, 0005, 0245, 0603, 1336, 0816, 1273, 0040 (weak), 1463 (weak).

Related: [[findings-corpus-and-data]], [[owner-science-rules]].
