# Grid pruning: the folders outside the tracked datasets

Source: thread "Prune unused grid datasets", 2026-10-31. Sizes come from the read-only survey of the lab volume,
grid job 40902375, read at 02:15 UTC (spine-datasets branch storage-report, storage/survey.json). The volume held
17.88 TB: 6.98 TB of tracked datasets, 7.52 TB of untracked data, 0.78 TB of runs and outputs, 0.45 TB of masks and
2.1 TB of other folders. Each row below is marked by greg's rule of 02:11 UTC: keep fluoroscopy, gold tier 3 and 4,
paired CT and X-ray, and plain film; everything else goes. Nothing in this file has been deleted.

## Already going (round 2, the prune word)

| folder | GB |
| --- | ---: |
| data/idc_nlst/raw | 3,168.7 |
| data/hf_abdomenatlas2_0_mini/raw | 330.9 |
| data/zenodo_unitochest/raw | 161.4 |
| data/hf_rexgradient_160k/raw | 155.6 |

## Delete by the rule (about 1.6 TB)

| folder | GB | what it is |
| --- | ---: | --- |
| results/nnunet_results/Dataset813_SpineSurgLSTVFullRibs | 278.8 | an old nnU-Net run's outputs |
| results/ablate | 201.6 | old ablation run outputs |
| data/versefusion/derived | 226.3 | VerSe fusion renders, rebuildable from VerSe |
| data/versefusion/raw | 109.5 | VerSe fusion inputs, rebuildable |
| data/hf_cads_unique/raw | 89.6 | CADS CT, not in the gold census |
| data/ctsp_april/ct | 85.0 | an April copy of CTSpinoPelvic1K, which round 3 removes |
| data/spine_detector_corpus/derived | 60.0 | an older detector corpus |
| data/deepfluoro_vendor/unpacked | 72.7 | a second unpacked copy of DeepFluoro beside the tracked set |
| results (folded rest) | 35.8 | small run outputs |
| data/rsna_rspect_pe (left after round 1) | 0.0 | goes with round 1 |

## Your call (about 3.0 TB)

| folder | GB | for keeping | for removing |
| --- | ---: | --- | --- |
| u251_* (multiomics, host, science, meth) | about 1,650 | your U251 project's work, refs and results | not spine at all |
| data/or_ready/indomain | 516.6 | the in-domain bank the C-arm work reads | rebuildable from its sources |
| data/or_ready/film_ncurve | 252.0 | film-derived bank (plain film) | rebuildable |
| data/multisource_banks/derived | 342.3 | DRR and film banks | rebuildable, may be stale |
| data/anomaly_harvest | 325.8 | the anomaly pack's masks (gold work) | large |
| data/idc/raw and data/idc/nifti | 706.1 | the IDC images the SPINEPS census read (gold 4) | nifti may duplicate raw |

## Keep by the rule

data/external/fluoro_video (262.8), data/fluorocap (218.9), data/aws_enhance_pet_ct (197.3) and its labels (11.3),
data/polypose (87.8), data/or_ready/auto_reference (78.4), data/hf_flux2_klein_9b (52.9, the FluXray model),
data/totalsegmentator_v300 and v201 (95.0), data/spineps (8.8), the gold3 and VerSe masks, the jobs and logs (50.6).
