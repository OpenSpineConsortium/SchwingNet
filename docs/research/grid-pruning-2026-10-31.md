# Grid pruning of 2026-10-31: which datasets went and why

Source: the project thread "Prune unused grid datasets", 2026-10-31, on the owner's ask of 00:55 UTC to remove the
datasets on the grid that neither the gold tier 3 and 4 CT shape work nor the next project, level detection on
fluoroscopy, uses; his choice of 01:01 UTC on the thread's decision card ("List A only"). Issue #511. The sizes are the
measured bytes in spine-datasets' storage feed (the snapshot of 2026-10-25, docs/textbook/figures/22/storage-plan.json);
the volume stood at 17.9 of 22.0 TB at 00:36 UTC.

## The rule

Kept: every set the gold tier uses (ENHANCE.PET, VerSe, TotalSegmentator and every collection of members.json's
census.gold4, which folds all SPINEPS-masked IDC collections into one row and so keeps each of them); every set the
fluoroscopy work uses (C-ArmLSpine, DeepFluoro, LUMOS, VinDr-SpineXR, NHANES II, BUU, the X-ray chain's sets, PolyPose,
the DRR banks); and every CT with the spine in view that TotalSegmentator could add to the gold tier. Removed: CT sets
whose record says the spine is not in view, or that are chest-only and so can never pass the C2-to-sacrum field test,
and that no job, flow, census, split or recipe reads. Each was found in the code only as a fetch row of
grid/run-platform-fetch.sh.

## Retired (2.32 TB)

rsna_rspect 980.2 GB, idc_ldct_and_projection_data 862.7 GB, aws_stoic2021 264.3 GB, zenodo_unitochest 84.1 GB,
zenodo_ts_task_liver_lesions 39.0 GB, zenodo_medpelvis3d 31.4 GB, idc_nsclc_radiomics 27.0 GB,
zenodo_ts_task_hip_implant 9.1 GB, zenodo_ts_task_pleural_effusion 9.0 GB, idc_midrc_ricord_1b 8.7 GB. The planner puts
the lab volume at 15.23 TB after them. The retirement deletes the images and keeps each set's record, freeze and
recipe, so any of them can be fetched again; it runs through spine-datasets' storage request (its pull request #377,
which the owner merges, then grid/storage.sh apply, report and retire there). Their fetch rows are gone from
grid/run-platform-fetch.sh in #511 so no chain fetches them again.

CADICA (3.1 GB) was on the owner's list and was kept: its record (data/sources/coronary_angiography.json) names it real
fluoroscopy video with the thoracic spine in the background, the only large real thoracic fluoroscopy without a data use
agreement, which the fluoroscopy work may need.

## Left for the owner

Seven sets were offered and kept by his choice: zenodo_vsd_fullbody, idc_nsclc_radiogenomics, idc_cptac_luad and
idc_cptac_lscc (CTs with the spine in view and no masks, which may join gold 4 once TotalSegmentator segments them), and
cathaction, aariz_cephalograms and scidb_mtddh (X-ray sets that are not of the spine). The feed counts 9.9 TB of the volume
as files outside the datasets (banks, renders, raw archives beside their unpacked copies, run outputs); none of it is
named for deletion before a fresh read-only survey (grid/storage.sh survey in spine-datasets) lists it by folder.

## Round 2: the folders the planner does not track (about 4.2 TB)

On "continue pruning" (01:14 UTC) the thread read spine-datasets' survey of the volume (storage/survey.json on its
branch storage-report, 2026-10-25), which splits the 17.56 TB into datasets 6.98 TB, untracked data 7.24 TB, other
2.08 TB, runs and outputs 0.78 TB, masks 0.43 TB and jobs and logs 0.05 TB, and proposed four raw folders; the owner
chose them at 01:33 UTC (issue #515). By the gate's status of 01:35 UTC no fetch was running.

| set | size | why |
| --- | ---: | --- |
| idc_nlst | 3,169 GB | the full NLST, partly landed: chest low-dose CT, no full spine, not paired; nlst_pilot stays |
| hf_abdomenatlas2_0_mini | 331 GB | partly landed; AbdomenAtlas 3.0 Mini, a gold 4 collection, aggregates the same public sets |
| zenodo_unitochest | 162 GB | a second copy on the data root of a set retired in round 1 |
| hf_rexgradient_160k | 156 GB | chest radiographs with no level truth |

None of them is a set the planner can retire (it answers "not on the grid" or "not frozen"), so the gate word
`prune round2` (grid/prune/round2.txt, tools/prune.py) plans them in one job, prints the plan, and deletes in a second
job only the folders that still hold exactly what the plan recorded. The u251 folders (RNA-seq and methylation, about
1.9 TB) are not this project's and were left to the owner; the old nnU-Net results (Dataset813, 279 GB) and
results/ablate (202 GB) stay as records of the reported stack.
