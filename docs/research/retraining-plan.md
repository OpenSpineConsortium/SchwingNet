# The retraining plan: what "better" is measured as, what it spends, and the schedule to 2 November

Source: the thread "SchwingNet video demo plan", 2026-10-20, the owner's definition of "better" given that day. The facts come from OpenSpineConsortium/spine-program (folder 01_carm_level_detection unless another is named; paths there are relative to that folder) and Gregory-Schwing-MD-PhD/spinesurg-ct-nnunet, branch L6_Class (`ssn:`), read on 2026-10-20; the Beethoven design from OpenSpineConsortium/beethoven-research, beethoven-agents and beethoven-qa the same day. Every number names its file; "not recorded" means the record is silent. This file is confidential with the rest of this repository (docs/project.md).

## 1. The owner's definition, and what each part needs

"Better means with the data leakage and code correctness audit of beethoven-research and beethoven-qa building a metaflow with all its build out testing, the increase accuracy and neural network performance across the entire spine, using the COBRA dataset, video frames, etc., and the workflow being visible on wandb.ai, metaflow's website, and any UI sharable browser based representation of the training and evaluation process, maybe even playing the video and letting the local computer infer on the video in real time."

Six parts, each one task of epic #7, in the order they land:

| Task | What it delivers | What stands in its way today |
| --- | --- | --- |
| #8 (this file) | the measure, the baselines, the spend, the schedule | nothing |
| #5, then #9 | the audit under beethoven-qa's gate and beethoven-research's split check | beethoven-qa 6.0.0 is merged (its main at 8e5628a) but not tagged; the fold banks still carry three leaks (section 3) |
| #10 | the whole-spine data: COBRA used whole, the sweeps exported with level names, a cervical anchor | 547 of 692 COBRA cases and 74,142 of the exported cases' projections are unused; case39's level names are not exported; the only voxel-anchored cervical source was never tried |
| #11 | the study as a Metaflow flow over Slurm, tested | Metaflow is Beethoven's decision D3 and is built nowhere (beethoven-agents pixi.toml 9-10; beethoven-research CLAUDE.md 114-115) |
| #12 | wandb.ai, Metaflow cards, a browser page | W&B is used only by the CT segmentation trainer (ssn:slurm/spine_train_fold.sh 58-60); nothing in the SchwingNet line logs anywhere but JSON files and an MLflow SQLite store (ssn:docs/MODEL_REGISTRY.md 4, 23-42) |
| #13 | real-time inference on the recorded sweep | cine_eval.py and cine_latency.py have never been run (DATA.md 330-332); no latency of the reported stack is measured (DATA.md 206-209) |

## 2. The measure

"Better" is measured on the sets the record already holds out, with the same gate (`ssn:tools/eval_gate.py`) and the same intervals, so the new number sits beside the old one in one table. Three measures, pre-registered before the first training job as the directive says (spine-program CLAUDE.md, rule 6): the rule, the success criterion and the hash of this section's text, stamped on every result row.

| Measure | Baseline, the reported stack | Where | Success criterion (default; the owner's to change) |
| --- | --- | --- | --- |
| M1 lateral naming, whole frame, C-ArmLSpine, zero-shot | 595 / 617 (96.4 %), 141 cases, Wilson on effective n [92.3, 98.4] | STATUS.md A2.1 | the new lower bound above the old point estimate (above 96.4 %) |
| M2 AP naming, whole frame, C-ArmLSpine, zero-shot | 276 / 631 (43.7 %), 142 cases [34.9, 51.9] | STATUS.md A2.2 | above 80 %, which the fine-tuned arm reaches (A3.2, 96.4 %) and the zero-shot arm does not |
| M3 vertebra and sacrum detection recall at 0.74, C-ArmLSpine | 231 / 287 (80.5 %) [74.1, 86.8]; 93.9 % on the repaired denominator | STATUS.md A6.1, A6.5 | the pre-stated 97 % that A6.1 says the reported stack is short of |

Two strata are measured with the same rule and never pooled into M1 to M3:

- Transitional (anomalous) spines: the record has three never-seen L6 cases in C-ArmLSpine (case42, case121, case136; STATUS.md A1.5) and the reading of one labeller; the senior second reader is Dr Tech (Corewell), in the owner's words of 2026-10-20 (docs/research/demo-plan.md, section 8). The stratum's n is small, so its number is reported with its interval and no criterion; 80 % power for a 90 % lower bound needs 99 persons at a true 97 % (STATUS.md E.4), which no corpus holds.
- The synthetic anomaly arm, 18 CTSpinoPelvic1K L6 spines by 3 seeds (STATUS.md C3.9, RECORD ONLY today): rerun under the gate so it can be quoted.

Whole spine: the encoder already names 27 classes, C1 to C7, T1 to T13, L1 to L6 and the sacrum (docs/MODEL_CARD.md 28-30), but the only intraoperative test set is lumbar, T11 to the sacrum, and no cervical or thoracic intraoperative frame has ever been scored (MODEL_CARD.md 99-104). The cervical and thoracic film numbers (CSXA 99.8 %, BUU 97.3 %, NHANES 99.1 %) are on the selection split, not held out (07_plain_film_level_id/STATUS.md 113-117), and the render floor is T7 at 55 to 59 % and T13 0 of 9 (same file, 117). So "across the entire spine" means, for 2 November: a held-out film test per region with the gate (M4, no baseline exists, so no criterion), and a C2 anchor shown on a real frame (MODEL_CARD.md 102-104); an intraoperative cervical or thoracic number needs frames the record does not hold (section 4).

## 3. The audit (#5, #9): what is known to leak

Held out means no ancestor of the checkpoint saw the person; unknown is not clean (docs/handoff/LEAKAGE.md, section 1). What the audit must close before any new number is quoted:

- The C-ArmLSpine fold models (A3.x) fine-tune from banks built from allspine_v7, which carries NHANES II twice (48 of 54 validation patients had a twin in training), VinDr keyed per image and 2,100 FluoroCap crops from 950 panels, which directive D1 dropped from training (docs/handoff/DATASET_USAGE.md 25-30, 163-173; LEAKAGE.md 5.1, 7.3; spine-program CLAUDE.md rule 9). The clean v9 base exists (jobs 40415667 to 40415670, DATASET_USAGE.md 75); clean v9-base fold models exist only as the 250 name_fill cells (DATASET_USAGE.md 176-182). The fold banks are rebuilt from the v9 base with those three sources out; that is the first training job of the plan.
- The encoder's old initialisation (allspine_v2_r1, MODEL_CARD.md 155-169) carried both leaks; the un-suffixed fold models are refused by the gate already (DATA.md 72-75).
- CHK-6 and CHK-7 were never run and the content-hash chain never ran on the real corpus (LEAKAGE.md 2, 7.1): both run in #9.
- COBRA duplicates (5,013) and the TotalSegmentator bench inside v9 (483 of 523) are in LEAKAGE.md 5.3's table; the audit re-keys every bank by person (identity cobra:<case>; centres D, F and G stripped, LEAKAGE.md 4).
- code_sha is missing from devcorpus_train.py and the CV scorer (MODEL_CARD.md 42-49): every trainer the flow calls records commit and clean-tree flag, or the flow refuses to start it.

The tool is beethoven-research's splits.py: `Split` (corpus, level, training, evaluation) and `shared_groups` and `disjoint`, contracted and proven, with the level one of patient, study, cadaver or source volume (beethoven-research src/beethoven_research/splits.py 534-629). Each corpus gets one Split record under src/schwingnet/records/ before its first training job, and tests/test_splits.py fails on a shared group. Code correctness is beethoven-qa's gate on this repository's package once #5 lands: the pure parts (the step graph, the record rows, the bank keys) contracted and proven; every function that reads files, runs torch or starts a process listed under [tool.beethoven-qa.unproven] with its reason, as beethoven-agents does for its 25 I/O functions (beethoven-qa CLAUDE.md 317-320). Whether CrossHair runs beside torch is not recorded; the training scripts themselves (ssn:tools/train_level_classifier.py, realxray_train.py, head_mixed_length.py) stay in spinesurg-ct-nnunet and are called, never refactored before the talk, since a refactor voids the parity gate (docs/project.md, Scope).

## 4. The data (#10)

| Source | What it is | On the grid | Licence and limits | Used today | The plan |
| --- | --- | --- | --- | --- | --- |
| COBRA2026 | 692 public pelvic cone-beam CT cases (467 Elekta, 225 Varian), 375,618 projections, each with a registered planning CT; projections, not video | /rs/rs_grp_oschome/go2432/data/cobra2026/, 808.6 GB (DATA.md 124-127) | CC BY-NC 4.0; 175 of 867 cases embargoed to 2032-03-01 (DATA.md 234-241); PatientAge and PatientSex in the CT (docs/DATASHEET.md 118) | 145 Elekta cases at 24 frames, 3,480 frames, in the sacrum detector's bank; no Varian bank; 74,142 of the exported cases' 77,622 projections unused with no reason (DATASET_USAGE.md 40-42, 127-128) | export every non-embargoed case and every projection, Elekta and Varian, keyed by case; it is pelvis and lumbosacral only (the sacrum is defined on 18.2 % of 609 test frames, grants/aidas_2027/RECORD.md 76), so it serves M3, not the whole spine |
| C-ArmLSpine sweeps | case134 and case39, 301 frames each, rotational arcs | CEPH/data/realxray/carmlspine_sweep (case134 only) | CC BY 4.0 | case134 exported detection-only, poses but no level names (VERIDAH misnamed its CBCT, docs/CINE_DEMO_RECON_2026-09-26.md 116, 147); case39 has L2 to L5 and sacrum names and no export | export case39 with its names; the sweeps are the demo's test and never training |
| C-ArmLSpine frames | 296 frames, the held-out test set | the gate's lists | CC BY 4.0 | M1 to M3 | unchanged; never trained on in the zero-shot arm |
| Bournemouth cervical | 252 sequences, 63 people, C0 to T1 corner tracks at 15 fps; no pixels in the public file | CEPH/data/realxray/bournemouth_qf/raw, the .mat only (DATA.md 119-120) | CC BY 4.0 | nothing | a test of the tracker's geometry only; it cannot train or test the encoder |
| DeepFluoro | 6 cadavers, 366 H5 frames plus a 2,659-frame deposit of which 2,293 are unused (DATA.md 128-133) | there | CC BY-NC-SA 4.0 | the sacrum detector | use all, keyed by cadaver (the cadaver split level) |
| Public clips | YouTube, PMC and others, 262.8 GB, never scored (DATA.md 141-143) | CEPH/data/external/fluoro_video/ | one clip CC-licensed of 18 with live fluoroscopy; levels almost never named (docs/FLUORO_VIDEO_YOUTUBE_SCAN_2026-09-26.md 7-20) | nothing | private evaluation of the tracker only; no training, no slide |
| FluoroCap | 29,500 literature panels, 72.8 % reproductions, no patient key | HOME/FluoroCap/, not migrated | out of training by directive D1 | still in the fold banks | out of every bank (section 3) |
| RSNA 2022 cervical CT | the only voxel-anchored C1, C2 and C7 source | archived, unpacked by nothing (DATASET_USAGE.md 247-261) | public challenge data; terms to be read before use | nothing | the C2 anchor's render source, if the owner gives the word; a new corpus and a new identity key |
| allspine v9 bank | CSXA 4,963, BUU 3,603, NHANES 543 films and renders of CTSpinoPelvic1K, VerSe and TotalSegmentator v2 (DATASET_USAGE.md 18-21, 143-157) | there | as each source | the encoder's base | re-keyed by person for M4's held-out film test; the "use all" rebuilds D2 to D6 (DATASET_USAGE.md 225) are the whole-spine lever |

The thing the data cannot give by 2 November: real cervical or thoracic intraoperative frames with level truth. None is on the grid or public (docs/FLUORO_VIDEO_SOURCES_2026-09-26.md 13-50), so the whole-spine claim at the talk is a film and render claim with an intraoperative lumbar number beside it.

## 5. The pipeline (#11) and its visibility (#12)

Beethoven's decision D3 is Metaflow with outerbounds/metaflow-slurm and a plain sbatch adapter underneath first; it is beethoven-agents' to build and nothing of it exists in any of the three repositories (beethoven-agents pixi.toml 9-10; beethoven-research pixi.toml 347-348). The telemetry stack (W&B, CodeCarbon) is planned as a pixi feature of the research pipeline's study image, also not built (beethoven-research pixi.toml 344-347). So this repository builds the first instance, as a pixi feature of its own with a re-lock that says so, and beethoven-agents takes what generalises after the talk:

- The flow runs inside a Slurm job, never on the login node (spine-program CLAUDE.md rule 7; warrior kills python by name). Each step submits one sbatch through the adapter, which writes the job file, submits, polls the status file no faster than every 60 s and records job id, partition, QoS, wall time asked and used, GPU-hours and preemptions beside the step's result (beethoven-agents CLAUDE.md, the compute-spend paragraph). The adapter is tested against a stub sbatch in tests/ and proven for its pure parts.
- Steps: banks (the exports of #10), split check (the Split records, refusing to continue on a shared group), detector, encoder, head, fold models, evaluation through the eval gate, cards. Each step's trainer is the existing script in spinesurg-ct-nnunet, called by path at the commit the record names.
- W&B: each trainer gets the W&B hooks the CT trainer already has (ssn:tools/nnunet_wandb_variant.py as the pattern), project SchwingNet, with offline mode and a later sync where the compute node cannot reach api.wandb.ai, which is not yet measured (a compute node reached GitHub over HTTPS on 2026-10-14). The key is a W&B credential of the owner's, not a Claude credential or an Anthropic key: it lives as the repository secret WANDB_API_KEY, for a job started by grid.yml, and as a mode-0600 file in the owner's grid home, read into the environment by the job and never on a command line, in a job file, a log or sbatch --export (spine-program CLAUDE.md rule 10).
- Metaflow's own view: Metaflow's UI needs a metadata service and a UI backend on a server, which the project has decided against hosting ("no server of ours", the template's decisions); the hosted form is Outerbounds, an account of the owner's. The default here is Metaflow cards, the HTML each step writes, published as a page of this repository's docs site (members only, SYMPHONY_DOCS pages) with the evaluation tables, and a W&B report linked beside it, which anyone with the link can read. Outerbounds is the owner's choice if he wants the flow graph live rather than the cards.

## 6. Real-time inference (#13)

The reported stack is PyTorch: YOLO11m-pose naming detector (42.2 MB), YOLO11m sacrum detector (40.6 MB), ResNet-18 encoder with a two-channel stem (44.8 MB, 11.17 M parameters, 3.62 GMAC per crop), BiGRU head (8.5 MB) (DATA.md 31-62; MODEL_CARD.md 21-25, 493). Measured on 2026-09-13 with older models on a V100: detector 22.9 ms median at 1024 px, encoder 2.3 ms, head 0.68 ms; CPU at 8 threads 331 ms and 18.3 ms (DATA.md 196-201). The sweep plays at about 10.3 fps (docs/research/demo-plan.md, section 1), so a GPU reads every frame with margin and a CPU reads one frame in three. Not measured: the reported stack's latency on any device; runtime_cost.json does not exist; the "17 ms" figure is banned (DATA.md 206-209, 337).

Order: cine_latency.py on an H200 (gmsap) with the reported stack, then the retrained one, which gives the parity gate and the number on screen; cine_eval.py for the causal tracker and the CLEAR-MOT numbers over case134 and case39; ONNX export of the three models with a parity check (old exports exist, dist/detect_v4_1024_fp32.onnx, docs/CINE_DEMO_RECON_2026-09-26.md 21); a local Python player with the overlay and the measured latency on screen, which is the demo; a browser player with onnxruntime-web only if all of that is done. A TensorRT arm needs its own parity run (code/cine_latency.py 77) and is not in the plan.

## 7. What it spends

Partition limits are the #SBATCH lines of each script, not measured times; the one measured training time is 2 h 25 min for a v2 encoder (ssn:docs/MODEL_REGISTRY.md 8), and GPU-hours for this line are not recorded (MODEL_CARD.md 561-566). Each row starts only on the owner's word and number for that row.

| Run | Script | Partition, GPU, memory, wall limit | Jobs in the plan | Wall hours asked |
| --- | --- | --- | --- | --- |
| COBRA and sweep exports (#10) | new slurm/export_cobra.sh, export_sweeps.sh | reqp, CPU | 1 array over cases, 1 | not recorded; the 145-case export's time is not recorded |
| clean fold banks (#9) | ssn:slurm/allspine_v8_clean.sh pattern | reqp, CPU | 1 | not recorded |
| sacrum detector, COBRA whole | ssn:slurm/realxray_train.sh | gvohp or galhp, 1 GPU, 8 CPUs, 48 GB, 8 h; rx_lodo ran at imgsz 1024 | 1 to 3 seeds | 8 each |
| encoder, v9 bank re-keyed | ssn:slurm/allspine_v9_train.sh | gvohp or galhp, 1 GPU, 180 GB, 14 h | 1 | 14 |
| head | in the encoder job, or ssn:slurm/head_mixed.sh | 240 GB, 10 h | 0 to 1 | 10 |
| fold models from the clean v9 base | ssn:slurm/carmlspine_cv_v9init.sh | gmsap, gvohp or galhp, 96 GB, 6 h | 5 folds | 30 |
| evaluation, M1 to M4 and the strata | ssn:tools/eval_gate.py | gmsap, 1 GPU | per model | 1 each |
| cine latency and cine eval (#13) | code/cine_latency.py, cine_eval.py | gmsap, 1 H200 | 2 per stack | 2 each |
| flow dry run, one epoch each | the flow | as above | 1 | about 4 |

GPU-hours in all, if every row runs once: about 80 asked, on H200s the owner says are available; the real figure is recorded by the adapter and goes in the run index. No Claude token runs on the grid (docs/setup/grid.md); the sessions that write the code spend the owner's own plan.

## 8. The schedule

Thirteen days from 2026-10-20 to the talk on Monday 2 November; the provisional is filed by Friday 30 October, and nothing of the method is shown before it. Dates are targets, not measurements.

| By | Lands | Needs from the owner |
| --- | --- | --- |
| Tue 21 Oct | #5 beethoven-qa 6.0.0 vendored; #9's Split records and split tests; #10's datasheets | the tag v6.0.0 (step 1 below); the word on the COBRA and sweep exports |
| Thu 23 Oct | the exports done; the clean fold banks; the adapter and the flow's dry run | the word and number for the export and bank jobs, and the dry run |
| Sat 25 Oct | the reported stack re-measured under the gate (M1 to M3 and the strata), cine_latency on the H200; W&B logging on | the word and number for the evaluation and latency jobs; the W&B secret (step 2) |
| Tue 27 Oct | detector on COBRA whole, encoder re-keyed, fold models from the clean base; M4 film tests; the cards page | the word and number for the training jobs (section 7) |
| Thu 29 Oct | the comparison table, old beside new, with intervals; the recorded sweep with overlay and latency; Dr Tech's transitional reads collected | Dr Tech's reads, through the owner |
| Fri 30 Oct | the provisional filed | the owner's |
| Sat 31 Oct to Sun 1 Nov | the slides' figures from the table and the recording; nothing of the method | the owner's choice of figures |
| Mon 2 Nov | the talk | |

What falls off first if time runs short, in order: the browser player (#13's last step), the RSNA cervical anchor (#10), Outerbounds (#12), the third detector seed (section 7). What does not fall off: the audit, the clean fold banks, M1 to M3 under the gate, the recorded sweep.

## 9. The owner's decisions, each with its default

1. The success criteria of M1 to M3 (section 2): defaults as given.
2. COBRA whole: export every non-embargoed Elekta and Varian case and projection (about 800 GB read, the bank's size not recorded); default yes.
3. RSNA 2022 cervical CT as the C2 anchor's source: a new corpus to read the terms of and key; default no for 2 November, yes after.
4. Weights and Biases: the owner's account and project SchwingNet (free tier holds private projects); the key as the secret and the file in section 5; default yes.
5. Metaflow's view: cards on the docs page (default) or Outerbounds as well.
6. Real time at the talk: a recording with the latency on screen (settled 2026-10-20); the local player on the owner's own computer runs if its CPU or GPU latency, measured in #13, reads the sweep at its frame rate.
7. Dr Tech's reads: the frames go to him through the owner, as crops or whole frames, under the owner's data agreement; the engine never sends them.
