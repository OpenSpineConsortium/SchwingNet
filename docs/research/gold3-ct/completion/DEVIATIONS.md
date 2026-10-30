# Deviations from the frozen PREREG.md

Each departure from PREREG.md after its freeze, dated, with its reason. The freeze itself is held by flows/stage_registry.py frozen, which lets this file only grow.

## 1. 2026-10-30 09:33 UTC: MOOSE draws ENHANCE.PET's levels, and each arm file carries its release's own label id

The owner's word, in the thread "Complete gold tier 3 census" at 09:33 UTC: "itd be better to keep segmentations consistent if moose can segment sacrum and c2 you should use that for the enhance pet scans, and you can do total segmentator for the 10 total segmentator and verse but you will need to make sure the labels are consistent as well". PREREG.md section 2 named TotalSegmentator for every study. From this deviation, before any job of this arm was sent:

- ENHANCE.PET's study (1379 at the freeze) is drawn by MOOSE's vertebrae model (moosez 3.2.2, clin_ct_vertebrae, the weights `fetch moose_weights` landed on 2026-10-26, unpacked as tools/flexray_render.py segment unpacks them), since ENHANCE.PET's release masks were made by MOOSE; the VerSe series and the TotalSegmentator subjects stay with TotalSegmentator 2.18.0 as section 2 says. The tool's subcommand moose-one runs in MOOSE's own environment; run cuts vertebra_C2 (MOOSE id 2) and sacrum (28) out of its multilabel file, and the check of section 3 and the bars of section 4 apply unchanged.
- Each kept arm file carries the level at its release's own label id, so a reader of the release reads the arm the same way: VerSe's scheme (C2 at 2, the sacrum at 26), ENHANCE.PET's MOOSE ids (2 and 28, grid/enhance-pet-labels.json), and TotalSegmentator's one file per structure with value 1. The record carries the id and the scheme; the file name carries the segmenter.
- The count the owner gave at 09:34 UTC: "yes send two jobs or however many u need". MOOSE's weights were on the data root already, so the arm stays two jobs, `fetch totalseg_weights` (sent 09:34 UTC) and `totalseg complete`.

## 2. 2026-10-30 22:46 UTC: a VerSe sacrum takes S1, and the arm takes three jobs

The review of the rerun path (RERUN-REVIEW.md, item 3) found that TotalSegmentator's sacrum leaves out S1, which it draws as a class of its own (vertebrae_S1), while VerSe's id 26 and the gold tier 3 release mean the whole sacrum, S1 included. As frozen, PREREG.md section 2's roi_subset (vertebrae_C2 and sacrum) would write a sacrum without S1 at the whole-sacrum id. The owner chose, on the thread "Continue Bayesian synthetic validation" at 22:46 UTC, "Yes, sacrum plus S1". From this deviation, before the rerun is sent:

- TotalSegmentator's roi_subset is vertebrae_C2, sacrum and vertebrae_S1. S1 lies in the same part, Dataset292, so no new weights are fetched.
- For a VerSe series the sacrum target is the union of TotalSegmentator's sacrum and vertebrae_S1, checked by section 3 and written at id 26 as one arm file; the record lists the parts.
- A TotalSegmentator subject's sacrum stays TotalSegmentator's sacrum alone, since that release keeps S1 as a class of its own and its file per structure is read the same way. MOOSE's sacrum (28) holds S1 already, so ENHANCE.PET is unchanged.
- The arm takes three jobs, not two: `fetch totalseg_weights`, the first `totalseg complete` (job 40882547, failed on an import clash), and the one rerun the owner allowed at 16:49 UTC (TOTALSEG_RERUNS in grid/gate.sh).

## 3. 2026-10-30 22:58 UTC: the sacrum is one full mask for every member, with no S1 class anywhere

The owner, on the same thread at 22:58 UTC, narrowing item 2: "No I don't want s1 I don't trust anyone's s1 class I just want unions sacrum full mask for all gold tier". Item 2's split, where a TotalSegmentator subject kept S1 apart, is withdrawn. Before the rerun is sent:

- Wherever TotalSegmentator draws, VerSe series and TotalSegmentator subjects alike, the sacrum target is the union of its sacrum and vertebrae_S1, checked by section 3 and written as one arm file at the release's sacrum id (VerSe 26, TotalSegmentator's value 1). No arm file carries S1 on its own.
- A TotalSegmentator release's own vertebrae_S1 is read as part of its sacrum when the drawn target is set against the release's levels, so S1 is never a level of its own on either side of the check.
- MOOSE has no S1 class, and its sacrum (28) is whole, so ENHANCE.PET is unchanged. The roi_subset and the three jobs stand as item 2 gives them.
