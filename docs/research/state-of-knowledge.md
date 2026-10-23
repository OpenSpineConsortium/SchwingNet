# What the research knows: a synthesis of SchwingNet's notes

Source: the thread "Spine knowledge synthesis", 2026-10-23, on the owner's ask of 02:03 UTC to pick up "big picture stuff like knowledge synthesis" and to start planning the annotation of the paired CT and X-ray data. Read on 2026-10-23 at main caa5641: every note under docs/research/ that is about the spine (retraining-plan.md, demo-plan.md, data-catalog.md, ct-priors-for-2d-detection.md, xr-annotation-format.md, xr-from-3d/README.md, lumbosacral-to-cervical-extrapolation.md, benchmarks-to-beat.md, data-manifest/README.md, v1-demo/README.md, evaluation/README.md, latency-and-sweep/README.md, artifact-textbook/README.md), with the registry records data/sources/totalsegmentator.json and the sample index's MANIFEST.md where a count needed checking. No paper, grid job or fetch was read for it: it sets the notes beside each other and says where they agree, where they disagree and what nobody has measured. Confidential with the rest of this repository (docs/project.md): it names methods, so nothing of it leaves before the provisional is filed.

The Artifact Textbook (artifact-textbook/, issue #120) synthesises the owner's claude.ai artifacts; this note synthesises the research notes, and its contradictions are the notes', not the artifacts'. The dataset census and roadmap are spine-datasets' (its track #175 and the census of #178); this note plans nothing and names the existing issue for every next step.

## 1. The finding in one paragraph

Every measured number about SchwingNet on real fluoroscopy comes from the reported stack (spine-program 01_carm_level_detection), not from the new workflow: lateral naming on a C-arm it never saw is 96.4 %, AP naming 43.7 %, and detection recall at 0.74 is 80.5 %. Three lessons hold across every note that read that record. Renders carry naming but not detection: a renders-only detector finds 0.3 % of bodies. The largest error, AP, is a whole-column shift by one level, so it is a counting error and not an appearance error. And the only real persons with an L6 are the three frozen test persons, so every rare class the model learns before the talk comes from CT. The programme's levers follow from those three lessons, in the order the notes rank them: a counting prior from CT at decode (A, #57), rare-class renders (B, #58), pose-targeted renders with anchors (C, #59), and real frames labelled through a registered CT (D, #60, and the gold masks of O, #127). The new workflow itself is built and tested, but it has been run only on a synthetic bank, so it has no number about the spine yet. None of the levers has been measured on a real frame.

## 2. The ledger of claims

Grades as xr-from-3d/README.md section 3 defines them: Measured is a number of this project's own record, Published is shown elsewhere in the source named, Inferred is reasoned and not shown.

| # | Claim | Grade | Where it rests |
| --- | --- | --- | --- |
| 1 | Lateral naming on held-out C-ArmLSpine, zero-shot: 595/617 = 96.4 % [92.3, 98.4]; fine-tuned 97.4 %; paired difference +1.0 [-1.9, 4.0] | Measured (reported stack) | demo-plan.md section 0 item 3, and section 3, from spine-program 01/STATUS.md A2.1, A3.1, A3.7 |
| 2 | AP naming, zero-shot: 276/631 = 43.7 %, a one-level cranial shift | Measured (reported stack) | demo-plan.md section 0 item 3; ct-priors-for-2d-detection.md 1 |
| 3 | Detection recall at 0.74: 231/287 = 80.5 % [74.1, 86.8]; 93.9 % on the repaired denominator; no held-out cell meets the 97 % detection target | Measured (reported stack) | demo-plan.md section 0 item 3 |
| 4 | Renders alone do not detect: 0.3 % at 0.74, 31.7 % at 0.25; no frame of the device 7.0 %; 24 frames of the device 84.0 %, with 95 % of the plateau by 10 to 12 frames | Measured (reported stack) | demo-plan.md section 0 item 4, and section 3 |
| 5 | The stop signal caught 5 of 6 erring frames | Measured (reported stack) | demo-plan.md section 5 |
| 6 | Encoder CPU path: 3,350 ms a frame | Measured (reported stack) | retraining-plan.md 1 |
| 7 | The v1 workflow ingests, catalogues, split-checks, trains, evaluates and draws witness frames end to end; its two recorded runs score 1.000 and 0.998 on synthetic persons | Measured (the workflow only) | v1-demo/README.md; evaluation/README.md |
| 8 | Witness frames show what a curve hides: in run cd37124c487d the validation witness frames went 85/93 at epoch 1, 38/93 at epoch 2 while the training loss fell from 0.2775 to 0.0217, 41/93 at epoch 3 and 93/93 at epoch 4 | Measured (synthetic bank) | evaluation/README.md |
| 9 | The level stage's ONNX export matches PyTorch within 1.9e-6, and the frame path without a detector (the crops, the level stage and the tracker) runs at p95 15.1 ms on 4 CPU threads against PyTorch's 31.3 ms | Measured (synthetic model, container CPU) | latency-and-sweep/README.md |
| 10 | The catalog takes 20,000 frames in seconds: ingest of 18,000 of them 10.6 s, build of all 20,000 5.5 s, a query 0.5 s, 20 readers at once 3.2 s | Measured (synthetic frames) | data-catalog.md |
| 11 | Physics renders with strong randomisation reach parity with real training on pelvic landmarks | Published (SyntheX) | lumbosacral-to-cervical-extrapolation.md 2 |
| 12 | On vertebrae a gap stays after translation: about three times the registration error, about 0.07 Dice in segmentation | Published (Jaganathan 2023, Spine-DART, Jecklin 2024) | lumbosacral-to-cervical-extrapolation.md 2 |
| 13 | Render-trained labelling reached 88.3 % on real Long-Film cadaver images, regions not stated | Published (Huang 2022, abstract only) | lumbosacral-to-cervical-extrapolation.md 3 and 8.1 |
| 14 | FluoroSAM names single levels badly: 0.04 Dice for similar levels in the text, 0.16 to 0.25 for L3 to L5 by name in its table, against 0.78 for the vertebrae as one class | Published (arXiv 2412.08020) | benchmarks-to-beat.md 1 |
| 15 | FluoroSAM's bridge from render to real is intensity randomisation alone, which is table stakes | Published (its code) and Inferred (the reading) | benchmarks-to-beat.md 3 |
| 16 | Registration to the patient's CT names levels at 99.3 to 100 %, at 7 to 26 s a frame | Published (LevelCheck) | benchmarks-to-beat.md 2 |
| 17 | No paper trains a level namer on one region of the spine and tests it on another, and none reports a per-angle naming curve | Inferred from the literature read | lumbosacral-to-cervical-extrapolation.md 4; benchmarks-to-beat.md 2 |
| 18 | A counting prior decoded with the level posteriors fixes the AP shift | Inferred (a CRF prior is Published in CT only) | ct-priors-for-2d-detection.md 3, item 1 |
| 19 | A render-to-real correction learned on the lumbosacral pairs carries up to the thoracic and cervical spine | Inferred, untested | lumbosacral-to-cervical-extrapolation.md 1 |
| 20 | Naming on a mid-thoracic or mid-cervical spot frame with no anchor in view is possible | Inferred and doubtful | lumbosacral-to-cervical-extrapolation.md 1 |

What is missing from the ledger says as much as what is in it. No row is a SchwingNet version 1 number on a real frame. No row is a number on a transitional spine read by two readers. No row is a latency on the H200 or on any machine of an operating room.

## 3. Where the notes disagree

Each line names both sides and which one this pull request corrects. A line marked "the owner's" stays as it is until he says which side holds.

1. The bound on version 1's training. ct-priors-for-2d-detection.md (item 3) and xr-annotation-format.md (section 6) speak of "the v1 run's 6 GPU-hour bound" and "the v1 run's scale, at most 6 GPU-hours on one H200", xr-from-3d/README.md carries the same 6 GPU-hours in rows C and I, and benchmarks-to-beat.md (4.2, rung 1) cites retraining-plan.md for it. retraining-plan.md says no such thing: its schedule gives 8 h for the detector, 14 h for the encoder and 10 h for the head. v1-demo/README.md gives a third answer, one job of at most 24 GPU-hours, or at most 5 in flow.py's Slurm mode. The figure is the owner's to set when he gives the word and the number. Until then, a cost estimate that builds on "6 GPU-hours" builds on nothing written. Left as it is: the owner's.
2. What version 1 is. retraining-plan.md (1, item 2) makes version 1 "one detector, one encoder, one head". v1-demo/README.md builds the level stage alone, crops cut from truth boxes, and every result row says "over truth boxes". So version 1's naming number is not comparable to the reported stack's naming, which runs behind its own detector, nor to LevelCheck's end-to-end rate. The comparator row in benchmarks-to-beat.md section 2 that sets version 1 beside the reported stack needs that caveat in the row itself, which pull request #145 adds. What version 1 is stays the owner's.
3. The rule for grid jobs. ct-priors-for-2d-detection.md section 5 says "grid jobs need no number (the owner, 2026-10-21 13:14 UTC)". CLAUDE.md ("every grid job and every training waits for the owner's word and the number of jobs") and docs/project.md (Scope, out of scope) say the opposite, and the owner's project instructions as sessions received them on 2026-10-23 add fetches: no fetch, grid job or training without his word and the count. Corrected here: the line now says that rule was superseded.
4. The IPCAI 2025 X-ray and CT set. ct-priors-for-2d-detection.md section 2 still lists it as registered and not fetched, with its labels to confirm. benchmarks-to-beat.md section 1 records it fetched (6.2 GB, still zipped), found to be the distal femur, and taken out of the registry on 2026-10-23. Corrected here, in the table of section 2 and in item 4 of the ranked plan, which had it labelling vertebrae on real frames.
5. How many paired sets. benchmarks-to-beat.md section 5 counts "nine ... a tenth" and lists ten, then says "two synthetic pairs stand beside the nine". Corrected here to ten.
6. The FluoroSAM weights. benchmarks-to-beat.md disagrees with itself: 2.5 GB on Google Drive in sections 1 and 4.1 and in the first paragraph of section 6, "about 1 GB" two lines later, and 1,002,351,026 bytes for the one file the fetch word brings, fluorosam_model_weights.pth, at the end of section 6. These can all hold if the Drive folder holds more than the one file, but no note says that it does. The fetch will settle it. Left as it is: the next read of the folder settles it.
7. TotalSegmentator's counts. The registry record says 1,228 v2 scans and 1,935 v3 scans, and that "the manifest counts v3 at 1,939". The sample index counts 1,631 v2.0.1 scans and 1,936 v3.0.0 scans, and it lists both folders as "unmapped", which means no registry record names their path on the grid. So v2 stands at 1,228 against 1,631, and v3 at 1,935, 1,936 and 1,939; what the registry's counts were taken from has not been read. The paths are a gap of their own, since ct-priors-for-2d-detection.md section 2 says the first CT job has to find the segmentations before anything is rendered. Left as it is: the census (spine-datasets #178) or the CT prior job (A, #57) settles it.
8. The schedule against the record. retraining-plan.md section 9 puts the registry, the first real shards and the first run of the person-key chain on the real corpus on Fri 23 Oct. As of this note, data-catalog.md and v1-demo/README.md record no ingest of a real frame, and both name the first grid ingest as waiting on the owner's word. This is a slip against a target, not a contradiction, but every date after it in that table moves with it. Left as it is: the owner's.

## 4. The paired CT and X-ray sets: what is known before annotation is planned

The owner asked on 2026-10-23 to start planning the annotation of the paired data. The plan is workstream O (#127) and its steps are in benchmarks-to-beat.md section 5. What the notes, read together, establish before any hour of reading is spent:

- Six sets pair a real spine X-ray with a CT of the same subject: C-ArmLSpine, COBRA, DeepFluoro, Ljubljana, LUMOS and the digital twin's cadaver. Five of them stop at L1 or below. The cadaver reaches T2 and is one specimen. No cervical pair exists anywhere the notes searched (lumbosacral-to-cervical-extrapolation.md 4).
- Four of the six are on the grid and carry a pose. C-ArmLSpine has 149 cases, and its poses are the project's own registrations, whose accuracy has not been measured. COBRA has 692 cases with the geometry stored. DeepFluoro has 6 specimens, with registrations shipped for its H5 frames. Ljubljana's 18 frames of one cadaver carry a gold pose but a read-only licence. LUMOS (280 CTs among 803 patients) and the cadaver are not fetched, and the cadaver's fetch waits on the owner's word (spine-datasets#170).
- The list of ten leaves out the paired sets that are requested, which spine-datasets' records hold (its docs/research/datasets-by-question.md, section 4): the LevelCheck cohort at Johns Hopkins (178 patients, 398 intraoperative radiographs with the preoperative CT, cervical to lumbar, waiting on Ali Uneri's answer), Huashan Fudan (140 lumbar patients, preoperative CT with intraoperative AP and lateral films) and NIT Warangal NIMS (9 patients, 51 Ziehm C-arm sets, level-named CT centroids public). The LevelCheck cohort would be the first pair above the lumbar spine with more than one subject, and the largest paired set of intraoperative radiographs. LUMOS, open to download, waits on one decision, whether the project takes its non-commercial licence, when COBRA (CC BY-NC) and DeepFluoro (CC BY-NC-SA) are already held under such terms.
- No set is known to ship masks of the vertebral bodies by level; whether the digital twin's cadaver ships its TotalSegmentator masks is to confirm on unzip, and LUMOS's labels are to confirm on its record. C-ArmLSpine has level names from two automatic labellers on 814 of 910 bodies, agreed levels only, with the thoracolumbar junction filtered out. DeepFluoro ships the vertebrae as one class. Of the held sets, no other ships any. So the automatic first pass (TotalSegmentator on every paired CT, step 1 of O) is the step every other step waits on. Its output is also the first measure of how much correcting the readers will face.
- TotalSegmentator is not safe on exactly the cases that matter most. The owner's own audit (CTSpinoPelvic1K, cited in lumbosacral-to-cervical-extrapolation.md 3) found that it has no L6 and shifts every label by one on a lumbarised spine, and that the Dice at the junction drops by 29 points. So the reader's correction is not uniform work. It concentrates where the column is transitional or the junction is filtered, and a correction protocol that reads the column call first, as xr-annotation-format.md section 4 records it, catches the shift before any body is redrawn.
- The cost of a useful gold set is known roughly: 30 verified cases give a 95 % interval near plus or minus 10 points on a per-body rate at 90 % (benchmarks-to-beat.md 5). C-ArmLSpine's 149 cases are the natural first set, since its frames are the test device. The owner's answer on the count was "maybe none maybe all of them", so the first pass's masks decide it.
- The gold answers some questions and not others. On the lumbosacral spine it gives per-pixel truth on real frames, the anchors for C, and the targets for E's shape head. It cannot test any level above L1 except on the one cadaver. And COBRA's projections come from radiotherapy linacs, not C-arms, so a correction fitted on them is fitted on another device class (lumbosacral-to-cervical-extrapolation.md 6, arm B).
- The other four paired sets have no spine: the Flepp femur, the pig lower limb, Veriserum's knee implants and the Geneva hip phantom. They are for the registration code: tune it where the pose ships, then run it where it does not. The Geneva phantom stays the unseen-device test and is never used to tune.

## 5. What is not known, and the cheapest measurement that settles each

Ranked by how many later steps wait on the answer. Every row waits on the owner's word and the count before any job runs, and each names the issue that already holds it.

| Question | Why it matters | The cheapest measurement | Issue |
| --- | --- | --- | --- |
| Does the counting prior fix the AP shift? | The largest error in the record; A costs no training | decode the reported stack's dumped AP posteriors with src/schwingnet/chain.py; CPU minutes once the CT statistics job has run | #57 |
| How good is FluoroSAM at naming on our frames, not on its cadaver? | Every comparator claim is on different test sets until one method runs on the other's frames | rung 0: its released weights on the held C-ArmLSpine test persons, its masks turned into boxes by the mask-to-box step #132 adds to tools/evaluate.py (not built) and scored as naming accuracy; about an hour of GPU, after the weights fetch | #132 |
| What does version 1 score on real frames? | Every later row is a delta against it | the v1 driver on C-ArmLSpine, once ingested; the bound is item 1 of section 3 | #11, #12 |
| How much do the automatic CT masks need correcting? | Sets the readers' hours and the gold count | TotalSegmentator over every paired CT as one array job, then a person's look at a sample | #127 |
| Is the anchor in the frame the problem above L1? | Decides whether "any position" is a model problem or a field-of-view problem | arm A: lumbosacral gold plus whole-spine renders, scored on AASCE and on CSXA re-keyed, at spot field and full field | #135 |
| How accurate are C-ArmLSpine's poses? | Its projected labels and residuals are only as good as its poses | reprojection distance on held-out landmarks for a sample of cases | #127 |
| Do the levers add up? | Rungs measured apart can overlap | the ablation ladder; which direction is the owner's (#131) | #131 |

Three things are named in the notes as unmeasured with no task of their own: whether --init in the record's trainers restores the optimizer or only the weights (retraining-plan.md 3.4), whether a training loader over CephFS files is fast enough against a packed shard (data-catalog.md), and whether GitHub Pages restricts a private repository's site on this plan (retraining-plan.md 4). Each is answered the first time its step runs, and the note that runs it says so.

## 6. What the talk may and may not claim

Taken from the notes as they stand, for the slides of 2 November, results only:

- May, once measured: a per-level naming rate on single real C-arm frames by a model with its own detector, with no CT and no prompt, set against FluoroSAM scored on the same frames (#132), not against the 0.04 Dice of another cadaver; the per-angle curve on the sweeps, since no published method reports one; the latency against the 97 ms budget; and the transitional cases named or abstained, as a case series with its intervals.
- May not: "first to learn level naming from renders" (Huang 2022) or "first to try it on C-arm frames" (FluoroSAM); any synthetic-to-real ratio, since none was swept; any number on a cervical or thoracic C-arm frame, since none exists, so a number on films says films; and anything of the method before the provisional is filed.

## 7. Where each piece lives

| Topic | Note | Tasks |
| --- | --- | --- |
| The goal, the workflow and the schedule | retraining-plan.md | #9 to #13 |
| The talk's demo and the reported stack's numbers | demo-plan.md | #4 |
| The data flow: registry, shards, catalog, leaks | data-catalog.md, dataset-organisation-at-scale.md | #10, #33, #9 |
| What is held, by file | data-manifest/README.md | |
| Every source, its licence and its reach | datasets-inventory.md, datasets-reproduce.md, data-access-requirements.md, xray-datasets-missing.md, xray-dataset-requests.md | spine-datasets |
| The workflow's runs and the evaluation page | v1-demo/README.md, evaluation/README.md | #11, #12 |
| Latency, ONNX and the sweep | latency-and-sweep/README.md | #13 |
| What 3D gives 2D | xr-from-3d/README.md, ct-priors-for-2d-detection.md | #56 to #70 |
| The X-ray annotation format, the screener and the pseudo-labeller | xr-annotation-format.md | #63, #64, #65 |
| From the lumbosacral spine to C2 | lumbosacral-to-cervical-extrapolation.md | #135 |
| Benchmarks, comparators and the paired sets | benchmarks-to-beat.md | #127, #130, #131, #132 |
| The artifacts as one book | artifact-textbook/README.md | #120 (the contradictions step is #136) |
