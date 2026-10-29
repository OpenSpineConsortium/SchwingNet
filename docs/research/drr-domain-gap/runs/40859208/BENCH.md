# bench flexray_drr_gap: job 40859208 on alh3, commit 6e908e6, 2026-10-29 00:30:16 UTC
- code: commit <hex withheld> copied to /rs/rs_grp_oschome/go2432/bench/flexray_drr_gap/code-6e908e6, which every step runs; no step holds the checkout
- PREREG.md: as frozen, sha256 3ca1b6b7aea60f00
- GPU: NVIDIA L40S, 46068 MiB, 550.163.01
- FluXray: read from /rs/rs_grp_oschome/go2432/data/hf_flexray_data/raw
- masks: spineps in /rs/rs_grp_oschome/go2432/data/spineps; moose in /rs/rs_grp_oschome/go2432/data/moose; a render group whose segmenter's masks are not read, or too few CTs have, is skipped with tha
- environment: flexray[train]==1.0.2 nanodrr==0.1.5 scikit-learn==1.9.1 umap-learn==0.5.12 numpy==2.4.6; index: /rs/rs_grp_oschome/go2432/data/_samples/<date withheld>-225857-J6Ax/samples.sqlite; weig
- prepared: analysis/PREPARED.json written, so the shards claim its units
- exit 0 at 2026-10-29 00:47:15 UTC
- shard 0: job 40859209_0 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:10 UTC
- shard 1: job 40859209_1 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:10 UTC
- shard 2: job 40859209_2 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:10 UTC
- shard 3: job 40859209_3 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:00:06 UTC
- shard 4: job 40859209_4 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:25 UTC
- shard 5: job 40859209_5 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:24 UTC
- shard 6: job 40859209_6 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:25 UTC
- shard 7: job 40859209_7 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 00:59:42 UTC
- shard 8: job 40859209_8 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:00:02 UTC
- shard 9: job 40859209_9 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:00:19 UTC
- shard 10: job 40859209_10 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:00:20 UTC
- shard 11: job 40859209_11 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:00:42 UTC
- shard 12: job 40859209_12 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:00:42 UTC
- shard 13: job 40859209_13 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:01:01 UTC
- shard 14: job 40859209_14 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:01:01 UTC
- shard 15: job 40859209_15 on alh3, GPU NVIDIA L40S, exit 0 at 2026-10-29 01:01:23 UTC
- merge: job 40859211 on alh3
- results: /rs/rs_grp_oschome/go2432/bench/flexray_drr_gap
  record: study drr-domain-gap; commit 6e908e6; tree clean; seed 0; plan 95a4-ba7b-ebfa-cac9; groups.json 92a1-640b-70f1-b6c6; PREREG 3ca1-b6b7-aea6-0f00; code e2ac-c706-01bb-c897
  record: jobs prepare 40859208, array 40859209 (16 tasks), merge 40859211; GPUs NVIDIA L40S x17
  record: units 768 of 768 done, 0 failed; mmd backend torch-cuda
  record: seconds render 336, plan 86, images 154, features 262, heads 8, analysis 354 (wall), units 17668 (summed), figures 19
  record: environment flexray[train] 1.0.2 nanodrr 0.1.5 scikit-learn 1.9.1 umap-learn 0.5.12 numpy 2.4.6 over the train-gpu torch
  drr gap: 10127 images, 21 groups, W&B not pushed (ServicePollForTokenError)
  replication flexray_replica vs flexray_reference in flexray (invariant): not replicated (persons 26/26 n 104/104; mmd q 0.046, 0.043 without nulls)
  replication fluxray_raw vs fluxray_raw_reference in flexray (invariant): replicated (persons 26/26 n 103/103; mmd q 0.910, 0.910 without nulls)
  render totalsegmentator_v201: 27 CTs chosen of 27 with every mask of 1228 CTs (moose 27, spineps 27); 26 kept by every group
  group flexray_drr synthetic found 104 chosen 104 decoded 104 persons 26
  groups counted as flexray_drr: flexray_drr_ct flexray_replica flexray_reference flexray_spineps
  group fluxray_raw synthetic found 104 chosen 104 decoded 103 persons 26 undecoded 1
  groups counted as fluxray_raw: fluxray_raw_reference
  group fluxray synthetic found 138063 chosen 1000 decoded 1000 persons 1000
  group ts_drr_project synthetic found 1316 chosen 76 decoded 74 persons 19 undecoded 2
  group devcorpus synthetic found 39506 chosen 568 decoded 568 persons 142
  group fluorogen synthetic found 2725 chosen 1000 decoded 1000 persons 1000 persons by file
  group carmlspine_spots fluoroscopy found 299 chosen 288 decoded 288 persons 144
  group deepfluoro fluoroscopy found 2659 chosen 1000 decoded 1000 persons 14
  group geneva_hip fluoroscopy found 116 chosen 100 decoded 100 persons 1
  group vindr_spinexr film skipped, 20932 index rows, none kept: format 10466, modality 10466
  group buu_lspine film found 7204 chosen 1000 decoded 1000 persons 1000
  group aasce film found 294 chosen 294 decoded 294 persons 294 persons by file
  group nhanes2 film found 17073 chosen 1000 decoded 1000 persons 1000 persons by file
  group csxa film found 4959 chosen 1000 decoded 1000 persons 1000 persons by file
  group kub_stonex film found 5188 chosen 1000 decoded 1000 persons 1000 persons by file
  group ieee_lateral film found 236 chosen 236 decoded 236 persons 236 persons by file
  group lumos film skipped, no folder lumos/bank under the data root
  group aariz film found 841 chosen 841 decoded 841 persons 841 persons by file
  space flexray dim 1024 rows 10127 spread 0.145 pca64 0.91
   calibration split-half auc median 0.49 range 0.44 to 0.52 over 11, mmd flagged 0, auc interval above half 0, nulls in the mmd q family
   replication flexray_replica vs flexray_reference persons 26/26 n 104/104 auc 0.50 [0.50, 0.50] p 0.455 knn 0.50 mmd p 0.043 q 0.046 fd64 0.0 kid64 -903.775 prdc 1.00 1.00 1.09 1.00 not replicated
   replication fluxray_raw vs fluxray_raw_reference persons 26/26 n 103/103 auc 0.50 [0.50, 0.50] p 1.000 knn 0.50 mmd p 0.910 q 0.910 fd64 0.0 kid64 -2033.462 prdc 1.00 1.00 1.01 1.00 replicated
   flexray_drr vs fluoroscopy auc 0.94 [0.89, 0.98] p 0.010 knn 0.95 fd64 1073.0 ratio 1.32 mmd p 0.001 prdc 0.60 0.73 0.15 0.02 closer than two real corpora
   flexray_drr vs film auc 0.96 [0.94, 0.98] p 0.010 knn 0.95 fd64 1225.0 ratio 1.65 mmd p 0.001 prdc 0.12 0.72 0.04 0.01 closer than two real corpora
   flexray_drr_ct vs fluoroscopy auc 0.89 [0.83, 0.94] p 0.010 knn 0.90 fd64 663.5 ratio 0.81 mmd p 0.001 prdc 0.42 0.94 0.14 0.05 closer than two real corpora
   flexray_drr_ct vs film auc 0.93 [0.90, 0.96] p 0.010 knn 0.88 fd64 704.2 ratio 0.95 mmd p 0.001 prdc 0.14 0.90 0.03 0.01 closer than two real corpora
   flexray_spineps vs fluoroscopy auc 0.96 [0.93, 0.98] p 0.010 knn 0.96 fd64 1008.3 ratio 1.24 mmd p 0.001 prdc 0.57 0.75 0.16 0.03 closer than two real corpora
   flexray_spineps vs film auc 0.97 [0.96, 0.98] p 0.010 knn 0.91 fd64 1140.2 ratio 1.53 mmd p 0.001 prdc 0.16 0.71 0.07 0.02 closer than two real corpora
   fluxray vs fluoroscopy auc 1.00 [0.99, 1.00] p 0.010 knn 0.99 fd64 575.9 ratio 0.71 mmd p 0.001 prdc 0.25 0.48 0.06 0.10 closer than two real corpora
   fluxray vs film auc 0.95 [0.94, 0.96] p 0.010 knn 0.98 fd64 348.8 ratio 0.47 mmd p 0.001 prdc 0.34 0.60 0.14 0.15 closer than two real corpora
   ts_drr_project vs fluoroscopy auc 0.98 [0.96, 0.99] p 0.010 knn 0.94 fd64 660.6 ratio 0.81 mmd p 0.001 prdc 0.38 0.64 0.14 0.04 closer than two real corpora
   ts_drr_project vs film auc 0.95 [0.93, 0.98] p 0.010 knn 0.94 fd64 551.7 ratio 0.74 mmd p 0.001 prdc 0.41 0.65 0.15 0.02 closer than two real corpora
   devcorpus vs fluoroscopy auc 0.95 [0.89, 0.98] p 0.010 knn 0.97 fd64 633.6 ratio 0.78 mmd p 0.001 prdc 0.56 0.45 0.20 0.12 closer than two real corpora
   devcorpus vs film auc 0.99 [0.99, 1.00] p 0.010 knn 1.00 fd64 551.8 ratio 0.74 mmd p 0.001 prdc 0.26 0.47 0.08 0.03 closer than two real corpora
   fluorogen vs fluoroscopy auc 0.95 [0.92, 0.97] p 0.010 knn 0.97 fd64 550.5 ratio 0.67 mmd p 0.001 prdc 0.35 0.61 0.14 0.27 closer than two real corpora
   fluorogen vs film auc 0.94 [0.93, 0.95] p 0.010 knn 0.97 fd64 332.5 ratio 0.45 mmd p 0.001 prdc 0.52 0.56 0.24 0.17 closer than two real corpora
   replication flexray_drr_ct vs flexray_drr persons 26/26 n 104/104 auc 0.67 [0.60, 0.74] p 0.010 knn 0.68 mmd p 0.001 q 0.001 fd64 276.6 kid64 3152.925 prdc 0.90 0.90 0.85 0.95
   replication flexray_drr vs flexray_replica persons 26/26 n 104/104 auc 0.57 [0.53, 0.60] p 0.010 knn 0.54 mmd p 0.001 q 0.001 fd64 33.0 kid64 -817.460 prdc 1.00 1.00 1.10 1.00
   replication flexray_spineps vs flexray_replica persons 26/26 n 104/104 auc 0.53 [0.47, 0.59] p 0.208 knn 0.55 mmd p 0.136 q 0.143 fd64 157.4 kid64 -259.517 prdc 0.92 0.85 1.09 0.97
   replication fluxray_raw_reference vs fluxray persons 26/1000 n 103/1000 auc 0.88 [0.84, 0.92] p 0.010 knn 0.85 mmd p 0.001 q 0.001 fd64 922.3 kid64 22610.470 prdc 0.36 0.83 0.21 0.09
   real-real auc median 1.00 min 0.97 max 1.00 over 36 pairs
   fluoroscopy vs film auc 0.97 [0.96, 0.98]
   silhouette -0.01
  space imagenet dim 512 rows 10127 spread 0.565 pca64 0.78
   calibration split-half auc median 0.48 range 0.43 to 0.52 over 11, mmd flagged 0, auc interval above half 0, nulls in the mmd q family
   flexray_drr vs fluoroscopy auc 0.99 [0.97, 1.00] p 0.010 knn 0.98 fd64 472.9 ratio 0.81 mmd p 0.001 prdc 0.33 0.05 0.14 0.02 closer than two real corpora
   flexray_drr vs film auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 492.5 ratio 0.91 mmd p 0.001 prdc 0.16 0.05 0.05 0.00 closer than two real corpora
   flexray_drr_ct vs fluoroscopy auc 1.00 [0.99, 1.00] p 0.010 knn 0.98 fd64 418.9 ratio 0.72 mmd p 0.001 prdc 0.27 0.09 0.09 0.02 closer than two real corpora
   flexray_drr_ct vs film auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 419.2 ratio 0.78 mmd p 0.001 prdc 0.30 0.04 0.09 0.01 closer than two real corpora
   flexray_spineps vs fluoroscopy auc 0.99 [0.98, 1.00] p 0.010 knn 0.97 fd64 433.2 ratio 0.74 mmd p 0.001 prdc 0.21 0.16 0.08 0.01 closer than two real corpora
   flexray_spineps vs film auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 441.1 ratio 0.82 mmd p 0.001 prdc 0.16 0.09 0.05 0.00 closer than two real corpora
   fluxray vs fluoroscopy auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 382.8 ratio 0.66 mmd p 0.001 prdc 0.00 0.01 0.00 0.00 closer than two real corpora
   fluxray vs film auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 273.7 ratio 0.51 mmd p 0.001 prdc 0.06 0.07 0.02 0.02 closer than two real corpora
   ts_drr_project vs fluoroscopy auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 560.4 ratio 0.96 mmd p 0.001 prdc 0.24 0.35 0.08 0.01 separable
   ts_drr_project vs film auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 661.2 ratio 1.23 mmd p 0.001 prdc 0.04 0.31 0.01 0.00 closer than two real corpora
   devcorpus vs fluoroscopy auc 1.00 [0.99, 1.00] p 0.010 knn 0.99 fd64 560.6 ratio 0.96 mmd p 0.001 prdc 0.39 0.00 0.15 0.02 closer than two real corpora
   devcorpus vs film auc 1.00 [1.00, 1.00] p 0.010 knn 1.00 fd64 671.3 ratio 1.25 mmd p 0.001 prdc 0.49 0.00 0.16 0.01 closer than two real corpora
   fluorogen vs fluoroscopy auc 0.99 [0.98, 1.00] p 0.010 knn 0.98 fd64 415.2 ratio 0.71 mmd p 0.001 prdc 0.05 0.35 0.02 0.02 closer than two real corpora
   fluorogen vs film auc 0.99 [0.99, 0.99] p 0.010 knn 0.99 fd64 289.4 ratio 0.54 mmd p 0.001 prdc 0.27 0.34 0.12 0.07 closer than two real corpora
- run log, UTC: each step's lines as it wrote them while it ran, with the units' quarter marks
  2026-10-29 00:30:24 prepare: started as job 40859208 on alh3
  2026-10-29 00:31:17 prepare: computes on NVIDIA L40S
  2026-10-29 00:31:17 prepare: stage render started
  2026-10-29 00:36:53 prepare: stage render done after 336 s
  2026-10-29 00:36:53 prepare: stage plan started
  2026-10-29 00:38:19 prepare: stage plan done after 86 s
  2026-10-29 00:38:19 prepare: stage images started
  2026-10-29 00:40:53 prepare: stage images done after 154 s
  2026-10-29 00:40:54 prepare: stage features started
  2026-10-29 00:45:16 prepare: stage features done after 262 s
  2026-10-29 00:45:17 prepare: stage heads started
  2026-10-29 00:45:25 prepare: stage heads done after 8 s
  2026-10-29 00:46:58 prepare: 768 units listed over 4 readings (0 not read), so the array's tasks claim them
  2026-10-29 00:52:41 tasks: 16 started from 00:52:41 to 01:01:21 on 1 node, NVIDIA L40S x16
  2026-10-29 00:55:35 units: 1 of 768 done, the first
  2026-10-29 00:57:06 units: 192 of 768 done (25%)
  2026-10-29 00:57:28 units: 384 of 768 done (50%)
  2026-10-29 00:57:56 units: 576 of 768 done (75%)
  2026-10-29 00:59:06 units: 768 of 768 done (100%)
  2026-10-29 01:01:22 tasks: 16 finished with nothing left to claim from 00:59:07 to 01:01:22, 768 units done and 0 failed among them
  2026-10-29 01:01:40 merge: started as job 40859211 on alh3
  2026-10-29 01:01:41 merge: every one of the 768 units read back as done, from 16 tasks; the jobs ran on NVIDIA L40S x17, prepare's among them
  2026-10-29 01:01:41 merge: stage analysis done after 354 s
  2026-10-29 01:02:07 merge: stage figures done after 19 s
  2026-10-29 01:03:43 merge: results.json, the figures and summary.txt written
- exit 0 at 2026-10-29 01:04:00 UTC
