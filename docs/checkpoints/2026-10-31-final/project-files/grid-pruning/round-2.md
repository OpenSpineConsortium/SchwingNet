# Grid pruning, round 2: the files outside the datasets

Source: thread "Prune unused grid datasets", 2026-10-31, greg's "continue pruning" of 01:14 UTC. Sizes come from
spine-datasets' read-only survey of the volume (storage/survey.json on the branch storage-report, read 2026-10-25 01:50 UTC),
so they are six days old. The survey splits the 17.56 TB volume into datasets 6.98 TB, untracked data 7.24 TB, other
2.08 TB, runs and outputs 0.78 TB, masks 0.43 TB and jobs and logs 0.05 TB. Nothing here is deleted yet.

## C. Proposed (about 4.2 TB)

| folder | size | what it is | why it goes |
| --- | ---: | --- | --- |
| go2432/data/idc_nlst/raw | 3,168.7 GB | the full NLST, partly landed (the record still says todo) | chest low-dose CT, no full spine, not paired; the 500-person nlst_pilot stays |
| go2432/data/hf_abdomenatlas2_0_mini/raw | 330.9 GB | AbdomenAtlas 2.0 Mini, partly landed | AbdomenAtlas 3.0 Mini (gold 4) aggregates the same public sets |
| go2432/data/zenodo_unitochest/raw | 161.4 GB | a second copy of UniToChest | the set is retired in round 1 |
| go2432/data/hf_rexgradient_160k/raw | 155.6 GB | ReXGradient chest radiographs | chest films, no level truth; not in the X-ray chain's spine sets |

Only the planner's tracked sets can go through the storage request, and none of these four is tracked (the planner answers
"not on the grid" or "not frozen"), so they need a narrow grid step of their own: one job, the four folders named exactly.
If the NLST fetch is still running, it is stopped first.

## D. Yours to judge, not spine work (about 1.9 TB)

The u251_* folders (u251_multiomics, u251_host, u251_science, u251_meth): RNA-seq and methylation work, with Nextflow work/
caches of 346, 304, 196 and 160 GB that a finished pipeline does not need. They are not this project's, so nothing is
proposed without your word.

## Kept

idc/raw (474 GB) and idc/nifti (232 GB) are the IDC collections behind gold 4; or_ready (868 GB), multisource_banks
(342 GB), versefusion (336 GB), fluorocap (219 GB), external/fluoro_video (263 GB), polypose, deepfluoro_vendor and
spine_detector_corpus are the fluoroscopy work's banks and sources; hf_cads_unique (90 GB) is whole-body CT; the masks and
ctsp_april are the gold tier's. The old nnU-Net results (Dataset813, 279 GB) and results/ablate (202 GB) are records of
the reported stack and stay until you say otherwise.
