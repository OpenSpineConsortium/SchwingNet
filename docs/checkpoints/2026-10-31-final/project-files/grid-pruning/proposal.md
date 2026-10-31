# Grid dataset pruning: proposal for greg's yes

Source: thread "Prune unused grid datasets", 2026-10-31. Sizes are the measured bytes in spine-datasets' storage feed
(snapshot of 2026-10-25, committed in SchwingNet as docs/textbook/figures/22/storage-plan.json); the volume was at
17.9 of 22.0 TB at 00:36 UTC. Nothing has been deleted.

Rule used: keep every set the gold tier 3 and 4 CT shape work uses (ENHANCE.PET, VerSe, TotalSegmentator and every
census.gold4 collection: AbdomenAtlas 3 mini, all SPINEPS-masked IDC collections, PANORAMA, Quadra HC, CURVAS, DEEP-PSMA,
AortaSeg60, AMOS22, WAW-TACE, COBRA, RibFrac, ...), every set the X-ray fluoroscopy project uses (C-ArmLSpine, DeepFluoro,
LUMOS, VinDr-SpineXR, NHANES II, BUU, the X-ray chain's sets, PolyPose, the DRR banks), and every CT with the spine in view
that TotalSegmentator could add to the gold tier. Remove CT sets whose record says the spine is not in view (or that are
chest-only, so they can never pass the C2-to-sacrum field test) and that no job, flow, census or recipe reads.

## A. Remove (2.32 TB)

| set | size | what it is | why it goes |
| --- | ---: | --- | --- |
| rsna_rspect | 980.2 GB | RSNA pulmonary embolism CTPA, chest | chest only, no level truth, read by nothing |
| idc_ldct_and_projection_data | 862.7 GB | low-dose CT raw projection data, chest | chest only, read by nothing |
| aws_stoic2021 | 264.3 GB | STOIC COVID chest CT | chest only, read by nothing |
| zenodo_unitochest | 84.1 GB | chest CT nodules | chest only, read by nothing |
| zenodo_ts_task_liver_lesions | 39.0 GB | liver lesion CT task | spine not in view, read by nothing |
| zenodo_medpelvis3d | 31.4 GB | pelvis CT | spine not in view, read by nothing |
| idc_nsclc_radiomics | 27.0 GB | lung cancer chest CT | chest only, read by nothing |
| zenodo_ts_task_hip_implant | 9.1 GB | hip implant CT task | spine not in view, read by nothing |
| zenodo_ts_task_pleural_effusion | 9.0 GB | pleural effusion CT task | chest only, read by nothing |
| idc_midrc_ricord_1b | 8.7 GB | COVID chest CT | chest only, read by nothing |
| cadica | 3.1 GB | coronary angiography video | not spine, read by nothing |

Each of these appears in the code only as a fetch row (grid/run-platform-fetch.sh), so the same pull request drops those
rows to keep them from being fetched again. Every set can be fetched again later from its source.

## B. Your call (0.48 TB)

| set | size | for keeping | for removing |
| --- | ---: | --- | --- |
| zenodo_vsd_fullbody | 252.2 GB | whole-body CT, spine in view, could join gold 4 once TotalSegmentator runs | no masks, no level truth, non-commercial |
| idc_nsclc_radiogenomics | 90.9 GB | some whole-body studies, spine in view | mostly chest, no masks |
| idc_cptac_luad | 38.9 GB | some whole-body studies | mostly chest, no masks |
| idc_cptac_lscc | 29.5 GB | some whole-body studies | mostly chest, no masks |
| cathaction | 56.2 GB | real fluoroscopy video (catheter), a realism reference | cardiac, no spine |
| aariz_cephalograms | 6.3 GB | films with the upper C-spine | head films, not the target |
| scidb_mtddh | 4.1 GB | films | hip, not spine |

## C. Not proposed yet: the 9.9 TB of derived files

The feed counts 7.6 TB as datasets and 9.9 TB as other files (banks, renders, archives, run outputs). The census of
2026-10-22 shows likely duplicates there, for example raw zips beside their unpacked copies (rsna_2022_cspine zips
189 GB, deepfluoro zips 35.6 GB, pengwin task 2 zip 32.6 GB, NIH ChestX-ray14 archives 42 GB) and two FluoroCap trees of
about 200 GB each. These need a fresh read-only listing on the grid before any of them is named for deletion.

## Running jobs

None of the sets in A or B is read by any sbatch script, flow, census, split or recipe in SchwingNet or bordercall, so
the enhance rerun (40900765), the TotalSegmentator completion and the other running jobs cannot be reading them. The live
squeue was not read from this thread; the removal request runs only after a status check.
