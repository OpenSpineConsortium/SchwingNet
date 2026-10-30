# Deviations from the frozen PREREG.md

Each departure from PREREG.md after its freeze, dated, with its reason. The freeze itself is held by flows/stage_registry.py frozen, which lets this file only grow.

## 1. 2026-10-30 09:33 UTC: MOOSE draws ENHANCE.PET's levels, and each arm file carries its release's own label id

The owner's word, in the thread "Complete gold tier 3 census" at 09:33 UTC: "itd be better to keep segmentations consistent if moose can segment sacrum and c2 you should use that for the enhance pet scans, and you can do total segmentator for the 10 total segmentator and verse but you will need to make sure the labels are consistent as well". PREREG.md section 2 named TotalSegmentator for every study. From this deviation, before any job of this arm was sent:

- ENHANCE.PET's study (1379 at the freeze) is drawn by MOOSE's vertebrae model (moosez 3.2.2, clin_ct_vertebrae, the weights `fetch moose_weights` landed on 2026-10-26, unpacked as tools/flexray_render.py segment unpacks them), since ENHANCE.PET's release masks were made by MOOSE; the VerSe series and the TotalSegmentator subjects stay with TotalSegmentator 2.18.0 as section 2 says. The tool's subcommand moose-one runs in MOOSE's own environment; run cuts vertebra_C2 (MOOSE id 2) and sacrum (28) out of its multilabel file, and the check of section 3 and the bars of section 4 apply unchanged.
- Each kept arm file carries the level at its release's own label id, so a reader of the release reads the arm the same way: VerSe's scheme (C2 at 2, the sacrum at 26), ENHANCE.PET's MOOSE ids (2 and 28, grid/enhance-pet-labels.json), and TotalSegmentator's one file per structure with value 1. The record carries the id and the scheme; the file name carries the segmenter.
- The count the owner gave at 09:34 UTC: "yes send two jobs or however many u need". MOOSE's weights were on the data root already, so the arm stays two jobs, `fetch totalseg_weights` (sent 09:34 UTC) and `totalseg complete`.
