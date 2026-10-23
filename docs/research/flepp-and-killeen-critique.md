# Flepp's and Killeen's approaches to level naming: where they break, and where SchwingNet is better and worse

Source: issue #140, worked by the thread "SchwingNet textbook and Flepp critiques" on 2026-10-23. It answers the owner's ask of 2026-10-22: "the fundamental flaws in these two researchers' approaches to this problem and how I'm approaching it better and worse". The two researchers are Roman Flepp (github.com/rflepp: arXiv 2506.13292, multi-view X-ray/CT registration by bone substructure contours, IPCAI 2025 and IJCARS) and Benjamin D. Killeen (github.com/benjamindkilleen: arXiv 2403.08059, FluoroSAM and FluoroSeg, and arXiv 2412.08020, the language-promptable digital twin).

Read for this note on 2026-10-23:
- arXiv 2506.13292v2 in HTML, its Sections 3 to 5 and Appendices A, C and F;
- arXiv 2403.08059v3 as PDF, its Methods and Evaluation;
- arXiv 2412.08020v1 in HTML, its Sections 3 to 5 and Tables 1 and 2;
- each researcher's GitHub profile, the README of github.com/rflepp/MultiviewXrayCT-Registration and the README of github.com/arcadelab/fluorosam;
- this repository's records named in each row. It builds on docs/research/benchmarks-to-beat.md, which holds each paper in numbers, and the checkpoints of 2026-10-22 23:50 and 2026-10-23 01:55 UTC on #130.

Confidential with the rest of this repository: it names patent-pending method and what the product does better, so none of it goes to symphony-template, spine-datasets, a slide or any public place before the provisional is filed.

Grades are those of docs/research/xr-from-3d/README.md section 3:
- Measured: this project's own record.
- Published: shown in the source named.
- Inferred: reasoned here and not shown. A claim with no source is marked Inferred, never stated as fact.

"The reported SchwingNet" is spine-program's 01_carm_level_detection, the stack docs/project.md names and version 1 replaces. Its numbers are cited through docs/research/demo-plan.md, which quotes them with their STATUS.md rows.

## 1. The answer in short

- **Neither group set out to name levels, so the critique is of what their approaches would need in order to.** Flepp's method registers a distal femur for navigation (Published, arXiv 2506.13292v2 Sections 4.1 and 5). FluoroSAM is a promptable segmenter of 128 anatomical classes and tools (Published, arXiv 2403.08059v3 Methods). The digital twin points a robotic C-arm by voice (Published, arXiv 2412.08020 Section 3). The twin paper names no wrong-level problem (Published, by its absence from the paper as read).
- **Flepp's route to a level is registration to the patient's CT, which is LevelCheck's route.** It needs four things in the operating room:
  - the patient's own CT;
  - a per-patient fine-tune on about 800 DRRs;
  - a fiducial of 16 metal spheres on a K-wire attached to the bone;
  - two views at least 45 degrees apart.

  It was shown on five cadaveric femurs and one C-arm (Published). On a spine, the bone the wire would hold is the one whose level is in question, and a chain of look-alike bodies is where a contour match can settle one level off. LevelCheck's own failures are whole-level shifts (Inferred, with the LevelCheck row as Published support). Where a CT exists and the registration holds, it is the accuracy ceiling (LevelCheck 100 % at 25.7 s, Published). SchwingNet competes with it on having no CT, no wire, one view and latency, never on accuracy.
- **Killeen's route to a level is a text prompt, and the papers show that text alone does not name levels.**
  - On the digital twin's cadaver, Section 4.1 of arXiv 2412.08020 reports 0.04 Dice for "similar vertebrae levels" from one image. Table 1 gives 0.16 to 0.25 Dice for L3, L4 and L5 by name, with centroid errors of 49 to 54 mm (Published).
  - The authors write that FluoroSAM "is severely limited" without point prompts (Section 5, Published).
  - A point on L4 placed by a person is the level already known, so the prompt that rescues the segmenter is the answer the surgeon lacks (Inferred).
  - Its level labels are TotalSegmentator's, on post-mortem CTs (arXiv 2403.08059v3 Methods, Published). TotalSegmentator has no L6 and shifts by one level on lumbarisation (Published, Schwing et al. 2026, as docs/research/lumbosacral-to-cervical-extrapolation.md section 3 records). So FluoroSAM's notion of a level inherits the count error that matters most for wrong-level surgery (Inferred).
- **SchwingNet's real advantages are confirmed in the record.**
  - It names the level, with no prompt, from one frame, as its output (Measured as built).
  - It measures naming per level on person-keyed splits with intervals (Measured as built).
  - It has already measured the renders-only regime against real data on a held-out real device: detection 0.3 % with renders only against 80.5 % with other devices' real frames (Measured by the reported SchwingNet).
  - Its zero-shot lateral naming is 96.4 % on C-ArmLSpine's 296-frame test set, from a device it never saw, against FluoroSAM's one cadaver (Measured by the reported SchwingNet).
- **Its weaknesses are also confirmed, and two of the issue's starting points turn out to be weaker than stated.**
  - No CT at inference is not a lead over FluoroSAM, which needs none either.
  - The latency is measured only on a synthetic dry-run model. No number yet says anything about SchwingNet on fluoroscopy (docs/research/latency-and-sweep/README.md).
  - Version 1 has no real result yet, and its test part is five frozen persons, three of them L6 (data/splits/test-persons.json).
  - AP naming is 43.7 %.
  - There is no real gold above L1, and SchwingNet estimates no pose.
- **What settles the comparison is one measurement on the same frames:** FluoroSAM's released weights through #132 (rung 0 of #131), scored as naming accuracy with this repository's evaluator, beside version 1 (rung 1). The rest is section 6.

## 2. Flepp: multi-view X-ray/CT registration by bone substructure contours

### 2.1 What it assumes, and what holds in an operating room naming levels

| Assumption | What the paper says (grade; where) | In the room, naming a spinal level (grade) |
| --- | --- | --- |
| The patient's own CT | "In the fine-tuning step, we use specimen-specific CT data, which is typically acquired preoperatively in clinical practice." (Published; Section 3.1) | Often there, but not always (Inferred): the case SchwingNet is for is the one where only the fluoroscope is. Where it is there, it was taken supine and the spine is operated prone, so the CT's alignment of one body to the next is not the room's (Inferred). |
| A network fine-tuned per patient | nnU-Net pretrained on DRRs of 15 knee CTs, then fine-tuned on about 800 DRRs per specimen, from -90 to +90 degrees, for 300 epochs. Inference uses about 18 GB of GPU memory. No time is reported for the fine-tune or the registration. (Published; Section 3.1, Appendix F) | A training run per patient before the case, of unknown length (Inferred). |
| A calibrating fiducial on the bone | A radiolucent 3D-printed marker with 16 metal spheres, "mounted on a K-wire attached to the femur", found by a PnP search (Published; Appendix A) | Invasive, and on the spine the bone it would hold is the body whose level is in question (Inferred). A navigation reference on the pelvis, as the twin uses a patient array, would then need a registration per vertebra, which the paper does not do (Inferred). |
| Two views far apart | "two views with a perspective change of at least 45 degrees"; single-view registration "is significantly less reliable" and none of its single-view runs was under 1 mm (Published; Section 4.3, Appendix C.2) | Two exposures and a C-arm turn of at least 45 degrees per check (Inferred). |
| A rigid bone cut into substructures | The femur divided into diaphysis and two condyles, matched within a substructure only, which the authors call "an ad hoc solution tailored to the femur" (Published; Sections 3 and 5) | A spine is a chain of near-identical substructures. A contour match within "a vertebra" has no feature that tells L3 from L4, and the only cue is the count from an end in view (Inferred). LevelCheck, the registration that does name levels, fails by whole-level shifts (Published; Lo 2015, docs/research/lumbosacral-to-cervical-extrapolation.md section 3). |
| One device, five specimens | "the testing of our method was conducted using data from a single C-arm device"; five cadaveric distal femurs, ten views each; a humerus tried on synthetic data only (Published; Sections 4.1 and 5) | Device and population spread untested (Published). |

### 2.2 What it does that SchwingNet cannot

- Sub-millimetre pose of a bone from two real X-rays (Published; Section 4.3):
  - mean reprojection distance 0.67 mm, against 5.35 mm for the commercial method and 4.03 mm for Zhang's;
  - 96.1 % of runs at 1 mm or under;
  - 92 % from random starts within plus or minus 50 mm and 180 degrees, and 100 % with the restart (Appendix C.3).
- SchwingNet estimates no pose at all (Measured: the level stage outputs a level per box; docs/research/latency-and-sweep/README.md).
- A pose projects the CT's labels onto every pixel of the frame. That is the supervised 3D-to-2D prior of #127 step 5. So the method is a tool SchwingNet could use, not a competitor at naming (Inferred).
- Its use here is limited. The code is "available for non-commercial research purposes upon reasonable request", under a pending patent EP25168706.7 (Published; the repository's README). Its data are a femur set (Zenodo 15753063, benchmarks-to-beat.md section 1). #127 therefore takes DiffDRR first.

### 2.3 The fundamental flaw, for this problem

The method answers "where is this bone, given its CT". SchwingNet's question is "which bone is this, given only the frame". Turning the first into the second needs four things the room does not reliably give:

- the CT;
- a wire in a bone of known level;
- two views;
- a time budget the paper never reports.

It also needs a match that cannot slip a level, which the paper does not test. Where all of that is present and holds, CT registration is the accuracy ceiling (LevelCheck 100 % at 25.7 s and 99.3 % at 7.1 s, Published). SchwingNet should claim no accuracy above it. Its claim is the same answer without the CT, the wire or the second view, in one frame interval (Inferred, until measured as section 6 says).

## 3. Killeen: FluoroSAM and the language-promptable digital twin

### 3.1 What they assume, and what holds in an operating room naming levels

| Assumption | What the papers say (grade; where) | In the room, naming a spinal level (grade) |
| --- | --- | --- |
| Renders alone carry the anatomy to real frames | FluoroSeg is about 2.95 million renders of 1,621 CTs "from the New Mexico Decedent Image Database". The gap is handled by "strong domain randomization" (coarse dropout, inversion, blurring, Gaussian contrast, random windowing, CLAHE), with no fine-tuning on real images (Published; arXiv 2403.08059v3 Methods; build_aug.py in benchmarks-to-beat.md section 3) | Post-mortem CTs lack the living patient's motion and contrast, and the randomisation is the cheap layer 2 of workstream E (Inferred). This repository's own record shows renders alone fail at detection on a real C-arm, 0.3 % at confidence 0.74 (Measured by the reported SchwingNet; demo-plan.md 0.4, A6.12). FluoroSAM's papers never train on real frames to compare (Published, by its absence). |
| The level is a class TotalSegmentator gives | 128 organ classes from TotalSegmentator, plus 38 merged groups "such as the 'left ribs' or 'cervical vertebrae', which are separate classes in the base TotalSegmentator" (Published; v3 Methods). The twin's real truth is the same TotalSegmentator labels projected from stitched CBCT (Published; arXiv 2412.08020 Section 4) | The groups are added beside the single vertebrae, not in place of them: Table 1 of arXiv 2412.08020 scores L3, L4 and L5 by name (Published). This corrects the issue's starting point. The level each label means is TotalSegmentator's count, which has no L6 and shifts by one on lumbarisation (Published; Schwing et al. 2026), and the cadaver's own count was checked by nobody the papers name (Inferred). A level a segmenter learned from that count is wrong on exactly the spines where counting is the clinical problem (Inferred). |
| A prompt says what to find | Text, point or mask prompts; text alone gives 0.60 Dice over 1,741 masks, two points 0.69, eight points 0.77 (Published; v3 Evaluation). The twin uses text alone, and the authors write that FluoroSAM "is severely limited" without point prompts (Published; arXiv 2412.08020 Section 5) | For a level, a person's point on "L4" is the level already found (Inferred). The VQ bottleneck "theoretically limits the generalizability of our framework to new segmentation classes", so a class outside the trained vocabulary, such as L6 or T13, has no prompt that reaches it (Published for the bottleneck; Inferred for L6 and T13). |
| One image shows enough | "a single image may not provide enough visual context to distinguish between similar vertebrae levels (0.04 DICE)"; FluoroSAM "fails to localize small, repeating structures and small organs" (Published; arXiv 2412.08020 Section 4.1) | The authors' own statement of the failure (Published). Centroid errors of 49 to 54 mm for L3, L4 and L5 by name (Table 1) are larger than one lumbar body with its disc (Inferred, an anatomical expectation not measured here). |
| Several tracked views make a 3D twin | n "is typically between 2 and 5", at "a minimum acute angle of 30 degrees", every image "acquired with navigation relative to a fixed patient array", on a robotic Loop-X whose moves "are typically on the order of 10 or more seconds" (Published; Sections 3, 3.1 and 4) | Navigation hardware and several exposures per question (Inferred). The 3D centroid errors are 35 to 64 mm for the vertebral groups, and none is given per level (Published; Table 2). |
| One specimen tells the field | FluoroSAM's real test and the twin's are one cadaver, a torso from mid-femur to T2 on one Loop-X: 1,741 masks in v3, and 80 images from 46 viewpoints in the twin (Published) | One person and one device. Neither paper flags it as a limit (Published, by its absence). |
| Run time | Not reported for FluoroSAM. The twin's language model takes "less than 1 second", and its evaluation ignores acquisition time (Published; arXiv 2412.08020 Sections 3 and 4.2) | No per-frame latency to set beside a 97 ms budget (Published, by its absence). |

### 3.2 What they do that SchwingNet cannot

- **Open vocabulary.** Masks for 128 anatomical classes and 464 tool models from text, points or a box. The vertebrae as one class score 0.78 Dice from text alone on the twin's cadaver (Published; v3 Methods, arXiv 2412.08020 Table 1). SchwingNet segments nothing and names only levels (Measured as built).
- **Scale.** About 2.95 million renders of 1,621 CTs, from volumetric and mesh-based rendering built on DeepDRR (Published; v3 Methods, benchmarks-to-beat.md section 3).
- **3D localisation and control.** A sparse twin from 2 to 5 views, and voice control of collimation and viewfinding: 83.54 % end-to-end success over 158 prompts (Published; benchmarks-to-beat.md section 1). SchwingNet localises in no third dimension and drives no device (Measured as built).
- **Released code, weights and data.** FluoroSeg under CC BY-NC-SA 4.0, the weights at 2.5 GB, and the twin's cadaver archive (Published; benchmarks-to-beat.md sections 1 and 6).

### 3.3 The fundamental flaw, for this problem

FluoroSAM's design treats a level as a segmentation class to be found by its appearance. The papers' own numbers show that appearance does not tell one level from the next in one frame (0.04 Dice, Section 4.1). A level is a position in a count from an end. The count needs an anchor in view or context outside the frame, and its truth breaks on transitional anatomy. FluoroSAM has no count, no anchor, and a label source that breaks there (Inferred from the Published figures above). Prompts patch the gap only by importing the answer from a person.

## 4. Where SchwingNet is better, confirmed from this repository's records

| Claim | Status here (grade; record) | Against Flepp | Against Killeen |
| --- | --- | --- | --- |
| The output is the level name, scored as naming accuracy per level, per source and per stratum, correct/n with Wilson intervals on person-keyed n | Measured as built: tools/evaluate.py and docs/research/evaluation/README.md, written by tools/eval_page.py. The reported SchwingNet names lateral levels zero-shot at 595/617 = 96.4 % [92.3, 98.4], and counts from the detected sacrum at 97.0 % (Measured by the reported SchwingNet; demo-plan.md 0.3, A2.1 and A4.7) | It has no level output (Published) | Dice per class, not naming accuracy; 0.04 on levels (Published) |
| One frame, no prompt, no CT, no fiducial, no tracking at inference | Measured by design: the evaluator reads one frame (benchmarks-to-beat.md section 2, the comparator row "SchwingNet version 1") | Needs all four (Published) | No CT either, so not a lead over FluoroSAM. The twin needs navigation (Published) |
| Training on real frames, and the renders-only regime measured against them on a held-out real device | Measured by the reported SchwingNet (demo-plan.md 0.4 and 3, A6.9 to A6.12, A8.2). Its detectors trained on real COBRA Elekta and DeepFluoro frames plus styled renders. Renders alone reach 0.3 % detection at confidence 0.74. Other devices' real frames plus renders reach 80.5 %. Adding 24 frames of the device reaches 84.0 %. The device is absent from training frames, render poses and style terms. Caveat: the zero-shot level encoder's C-arm appearance came from renders alone, beside real plain films (demo-plan.md 8.3) | Trained on renders of the test specimen itself (Published) | Renders only. No comparison with real training, and no held-out-device design (Published, by its absence) |
| A real test at more than one person | Measured by the reported SchwingNet: zero-shot over C-ArmLSpine's 296-frame test set, 617 lateral bodies, from one mobile C-arm never seen in training (data/sources/carmlspine.json; demo-plan.md 0.3 and 8.3) | Five femurs (Published) | One cadaver (Published) |
| Splits keyed to the person, extended without moving anyone, with leak checks before training | Measured as built: data/splits/rule.json and data/splits/test-persons.json. The catalog and ingest refuse a frozen test person in a training shard. Leak checks CHK-6 and CHK-7 run as the ingest step (docs/research/data-catalog.md; tools/catalog.py, tools/ingest.py, tools/leaks.py) | Not applicable: the method fine-tunes on the test specimen (Published) | Split by base CT for renders; the real test is one cadaver (Published; v3 Methods) |
| The same real witness frames drawn from the untrained network at epoch 0 onward | Measured for the workflow only: both recorded runs read the synthetic bank (docs/research/evaluation/README.md) | None (Published) | None (Published) |
| A latency budget and its instrument | Measured for the workflow only. The budget is 97 ms p95, one frame of C-ArmLSpine's sweeps. Parity with PyTorch is checked first. On the synthetic dry-run model, ONNX Runtime on four CPU threads gave p95 15.1 ms (docs/research/latency-and-sweep/README.md; src/schwingnet/latency.py) | No time reported (Published) | No per-frame time reported (Published) |
| Transitional anatomy as its own row, and a counting prior from CT | Unproven: the evaluation page's transitional row is "not measured", and the prior is workstream A (#57) | None (Published) | Inherits TotalSegmentator's count (Published; Inferred for its effect) |

## 5. Where SchwingNet is worse or unproven

| Weakness | Record (grade) |
| --- | --- |
| Version 1 has no real result | The page's two runs are dry runs on the synthetic bank and "measure the workflow, not SchwingNet" (Measured; docs/research/evaluation/README.md). Every SchwingNet number above is the reported SchwingNet's. |
| Version 1's test part is small and skewed | Five frozen persons, three of them real L6 cases and two the demo sweeps. Everyone else goes to training or validation by the hash rule (Measured; data/splits/test-persons.json, data/splits/rule.json). Its all-levels row will rest on five persons of one device. |
| Any angle is not shown | AP naming zero-shot is 276/631 = 43.7 %, a one-level cranial shift, against 96.4 % lateral. tools/evaluate.py has no per-view stratum yet (Measured by the reported SchwingNet; demo-plan.md 0.3; the #130 checkpoint of 2026-10-23 01:55 UTC). |
| Detection misses bodies | Recall at confidence 0.74 is 231/287 = 80.5 % [74.1, 86.8], and the pre-stated 97 % detection target is met by no held-out cell (Measured by the reported SchwingNet; demo-plan.md 0.3, A6.13). |
| No real gold above L1 | The real CT-and-X-ray spine pairs are lumbar or lumbosacral. The exception is the twin's cadaver to T2, which is one specimen, not yet fetched (Measured; benchmarks-to-beat.md section 5). |
| A collimated mid-thoracic or mid-cervical frame shows no anchor | Naming there is Inferred and doubtful. The count needs an end in view or context outside the frame (docs/research/lumbosacral-to-cervical-extrapolation.md sections 1 and 6, arm A). |
| Few real pairs against millions of renders | C-ArmLSpine's 149 cases from one mobile C-arm, plus COBRA's radiotherapy projections and DeepFluoro's six specimens, against FluoroSeg's about 2.95 million renders (Measured; data/sources/carmlspine.json, benchmarks-to-beat.md section 5; Published for FluoroSeg). |
| One device for the real C-arm test | C-ArmLSpine is one mobile C-arm. Leave-one-device-out on real frames is planned (workstream E) and not run (Measured). This is FluoroSAM's weakness too. |
| No pose and no 3D | Names only. It cannot drive navigation or a robot, which Flepp's pose and the twin can (Measured as built). |
| Latency not measured on a model that names fluoroscopy | The dry run's numbers are a synthetic model on a container CPU. The reported SchwingNet's encoder took 3.35 s per frame on a CPU, and its old "17 ms" is banned for having no record (Measured; docs/research/latency-and-sweep/README.md, demo-plan.md 1, retraining-plan.md 5). |
| Licences of the training data | COBRA is CC BY-NC and FluoroSeg CC BY-NC-SA. Whether a product may train on or compare against them is the lawyer's question (Measured as recorded; benchmarks-to-beat.md section 6, #132). |

## 6. What a measurement settles, mapped to #131 and #132

| Question | The measurement, on the evaluation page | Rung (#131 build-up 4.2; leave-one-out 4.1) | Waits on |
| --- | --- | --- | --- |
| Can FluoroSAM name levels on our frames? | FluoroSAM's released weights prompted "L4 vertebra" and so on. Its masks are read as boxes by tools/evaluate.py and scored as naming accuracy per level with Wilson intervals per person, on the C-ArmLSpine test persons and the twin's 80 frames | #132; rung 0; row 7 | the weights' fetch word, the owner's word and count; spine-datasets#170 and #127 for the cadaver's truth |
| Is the prompt doing the work? | The same, text only against two points against a box per vertebra. If only points name levels, the point is the answer (section 3.1) | #132's three arms | as above |
| Does the transitional count break FluoroSAM? | FluoroSAM on case42, case121 and case136, the real L6 persons, prompted "L5 vertebra": a one-level shift there is TotalSegmentator's count showing through. Beside it is version 1's transitional row | #132 with the transitional stratum; rung 1, then rung 2 (the counting prior, A, #57) | as above; version 1's run |
| Does version 1 name better on the same frames? | Version 1's per-level rows on the same test persons and frames | rung 1; row 5 | version 1's run, the owner's word |
| Renders only against real data | Renders only (FluoroSAM's regime) against real data only, the detection half already measured by the reported SchwingNet (section 4) | rows 4 and 6 of 4.1; row 6 has no build-up twin | the full system |
| Any angle | The per-angle curve on the case134 sweep and COBRA's held-out cases, and a per-view stratum that tools/evaluate.py does not yet tally | rungs 3 and 5; every rung's per-angle column | the per-view follow-up named on #130; D (#60) for COBRA's labels |
| A device not seen | Leave-one-device-out on real frames | rung 4 (E layers 1 and 2, #61) | the run |
| Above L1 | The twin cadaver's thoracic frames | #135's row; rung 6 for gold priors | spine-datasets#170, #127's verified masks |
| Latency | p95 per rung against 97 ms on the H200 and on a CPU | every rung, task #13 | version 1's run |
| The registration ceiling | Not on the ladder. A CT-registered arm on C-ArmLSpine, whose cases each carry a CBCT, would put LevelCheck's kind of number on the same frames (Inferred proposal) | none yet | the owner's word: a new rung or not |

Flepp's set is a femur and serves only #127's registration check, so no rung compares SchwingNet with Flepp's method directly (benchmarks-to-beat.md section 4.2). The comparison with it is the LevelCheck comparator row and, if the owner adds it, the registration-ceiling arm above.

## 7. What this means for the talk

- What it can claim once measured: level naming on single real C-arm frames, with no CT, no prompt and no fiducial, per level with intervals and latency. That claim is set against FluoroSAM scored on the same frames (#132), not against a Dice from another cadaver (Inferred, the claim's shape).
- What it cannot claim:
  - more accuracy than CT registration (LevelCheck, Published);
  - being first to learn naming from renders (Huang 2022, Published);
  - any angle, before the per-angle curve;
  - real time, before version 1's p95 is under 97 ms.
- The 0.04 is a Dice, not an accuracy, and is quoted as Section 4.1's text. It is not a row of Table 1 (benchmarks-to-beat.md section 1).
- Nothing of this note goes on a slide before the provisional is filed (docs/project.md).

## 8. Sources

- Flepp et al., "Automatic Multi-View X-Ray/CT Registration Using Bone Substructure Contours", arXiv 2506.13292v2 (IPCAI 2025; IJCARS, doi 10.1007/s11548-025-03391-4): Sections 3.1, 4.1, 4.3 and 5, and Appendices A, C.2, C.3 and F. Also github.com/rflepp/MultiviewXrayCT-Registration's README (code on request, non-commercial, patent pending EP25168706.7) and Zenodo 15753063 as benchmarks-to-beat.md section 1 records it.
- Killeen et al., FluoroSAM, arXiv 2403.08059v3 (MICCAI 2025): Methods (FluoroSeg Dataset; the model, its VQ bottleneck and its randomisation) and Evaluation (the Loop-X cadaver, 1,741 masks). Also github.com/arcadelab/fluorosam's README (weights 2.5 GB, no prompt or speed stated), and src/fluoroseg/alb/build_aug.py as benchmarks-to-beat.md section 3 read it.
- Killeen et al., the language-promptable digital twin, arXiv 2412.08020v1: Sections 3, 3.1, 4, 4.1, 4.2 and 5, and Tables 1 and 2.
- Lo et al., LevelCheck, Spine 40(8):E476, 2015, and Schwing et al., NeurIPS 2026 poster, as docs/research/lumbosacral-to-cervical-extrapolation.md section 3 records them; Huang et al. 2022 as that note and benchmarks-to-beat.md section 2 record it.
- This repository:
  - docs/research/benchmarks-to-beat.md, sections 1 to 6;
  - docs/research/lumbosacral-to-cervical-extrapolation.md, sections 1, 3 and 6;
  - docs/research/demo-plan.md, sections 0, 1, 3 and 8;
  - docs/research/evaluation/README.md;
  - docs/research/latency-and-sweep/README.md;
  - docs/research/retraining-plan.md, sections 4 and 5;
  - docs/research/data-catalog.md;
  - docs/research/xr-from-3d/README.md, section 3;
  - data/sources/carmlspine.json, data/splits/rule.json and data/splits/test-persons.json;
  - the issues #127, #131, #132 and #135, and the checkpoints on #130.

No grid job, training or model run was started for this note.
