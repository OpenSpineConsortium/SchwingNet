# Research directions from the data holding

Oct 8, 2026 · @greg

## Lead

The evidence supports one order of work: measurement first, human reads second, models third. On ordinary spines the 2-D system is at ceiling on plain film and near ceiling on the one real C-arm: it names 97.4 % of bodies on a whole lateral frame and 74.8 % with one body in view. On transitional spines no number exists on a real frame with a human read. The one fact that constrains every project is that the verified real-frame transitional test count is zero today. The best rendered L6 recall is 56.1 to 72.4 % on ten held-out persons. Human readers reach 32 % sensitivity for Castellvi type on radiographs against 76 % on CT.

The parity idea is sound, but its 3-D target is not yet in the form the goal needs. The published 0.990 for T12 against L1 divides five of its eleven features by the patient's median over three or more levels, so it is not a single-vertebra classifier, and its dominant feature is the transverse-process span, which is coronal and invisible on a lateral. No lumbosacral 3-D classifier exists at all.

So the first two projects are an hour on the laptop and a day on the grid: define the single-vertebra 3-D target, then measure which 3-D features survive projection, per view, on exact-pose renders of the 802 labelled CTs. In the same week the reader work that creates power starts: a one-hour coverage render on COBRA2026, a reader queue of 63 volumes, the seven CTSpinoPelvic1K re-reads, the VerSe mask count and the whole-cohort Castellvi read. Models wait for a frozen truth file and a clean encoder. The first clean model is expected to fail its validation screen, and that failure is itself a result the standing determination asks to be stated plainly.

The full document, with every number's file, is HANDOFF/RESEARCH\_DIRECTIONS.md in the private spinesurg-ct-nnunet repository. It was written from six reader notes and three independent proposals, verified by three reviewers against 711 opened claims, and corrected. Nothing ran on the grid. Before a student copy is made, the sentences naming the technology-transfer office and the proposal judging are to be cut; the rest is written to be student-safe.

## An anomaly-aware fluoroscopy classifier

The standing determination of 2026-09-23 is narrower and stronger than "anomaly-aware": name the level correctly on a transitional spine (L6, T13, sacralised L5, four lumbar) from C-arm exposures, at parity with an ordinary spine, and report "not at parity" plainly if that is the result. Castellvi type I is a coronal transverse-process height of 19 mm or more, 68 % of all LSTV, and unrecoverable from a lateral film by construction. The target is therefore the count-changing types II to IV, 9 to 11 % of CTs.

**What has been tried.** Every mechanism that reads morphology alone has measured below the ordinary-spine accuracy. Every mechanism that counts has been measured only on ordinary spines or on renders. The two have never been coupled on a real transitional frame with a verified read.

| Mechanism | What it returned | Status |
| --- | --- | --- |
| Rule counting decoder on CT truth | 6 of 6 L6 found; 2 of 3 sacralisations over-counted | measured, CT only |
| L6 as a voxel class, 18 cases duplicated twelvefold | Dice 0.000 every epoch | measured |
| Anchored decode with T13 and L6 columns | 39.8 % of L6 bodies called L6 on 376 held-out renders, against 63.0 % single-crop | measured |
| Rare-class render banks (physics\_rare: 1,482 annotations of 81 transitional subjects) | random-window naming 45.1 % against 93.9 % on ordinary renders | measured |
| All 144 anomalous BUU films held to validation | anomalous interior 49.9 % against ordinary 89.9 % | measured |
| Star Temporal Classification | 22 to 24 % against 39.8 % | refuted |
| Alphabet coupling of count and morphology | 98.2 % against the count's 97.0 %; the gain is 3 cases (P .25), carried by L6 calls on five-lumbar frames; the three real L6 patients 0 of 5 and 1 of 5 | measured |
| Alphabet loss in the head | L6 recall 56 to 61 % at lambda 0, 67 to 72 % at lambda 1.0; false L6 rises from 0.14 to 0.41 % | measured, a trade-off |
| Binary LSTV and TLTV whole-frame flag | renders 0.58 to 0.73; real BUU films no signal | measured |
| Selective prediction, conformal sets | 99 % at 35.7 % coverage on renders | leaked bank; re-run needed |
| Render-to-fluoro translation (SDXL, CUT, CycleGAN, ADDA) | no gain in any arm | refuted |
| Size in millimetres as a scalar feature | no gain, three times | refuted |

**The design the evidence supports.**

- Task: per-vertebra naming from detected boxes in a limited field, with the count from the detected sacrum as the second mechanism and disagreement as the stop signal. The endpoint is exact level on a transitional spine, person-clustered, with the strict all-sacrum-frames denominator printed beside any anchored number.
- Classes: the 27-level alphabet with the variant alphabets (ordinary, L6, T13, both, four lumbar). T13 on a lumbar frame is a count from the thoracolumbar junction, not a morphology. Seven T13 persons exist in all sources and none in any 2-D validation split.
- Keep both mechanisms and measure their agreement on anomalous spines, which has never been done. On rendered L6 spines the dominant failure is a whole-run shift one level cranial on 26 to 28 % of films, exactly the error a count catches.
- Banks: the G3 person-disjoint split (ordinary 80/10/10, transitional 50/10/40, every real transitional subject in test). The encoder starts from ImageNet on G3 training persons only, because 92 of 97 transitional validation and test persons sit in the v8 and v9 training splits. Renders stay in training as the only labelled L6 and T13; variants in 25 to 35 % of rendered CTs by which CTs are rendered, never by duplication; no decoder pseudolabels; FluoroCap in no training list.
- Schedule: mixed training by default, since pretrain-then-fine-tune lost 25.6 anomalous points. The 45-cell synthetic-to-real ratio array (real share 0.1 to 0.9, N 25 and N all, three seeds) is the experiment nobody has published and runs after the clean encoder exists.
- Devices: each C-arm is its own domain. Pooled is never quoted without the device-held-out arm beside it, and six devices are needed for any two-sided P at or under 0.05.

**The data.**

| Source | Persons and frames | Transitional content | Truth quality | Restriction and leakage |
| --- | --- | --- | --- | --- |
| C-ArmLSpine (Surgio-B51) | at most 149 cases; 299 spot frames; 149 CBCTs | 3 L6 by one automatic labeller; no T13; lumbar-only CBCT, so no count | two automatic labellers, no human read | CC BY 4.0; the v9 zero-shot numbers are clean |
| COBRA2026 (Elekta XVI, Varian) | 692 public cases; 3,480 Elekta frames from 145 cases; 225 Varian cases never exported | planning-CT screen 91 calls (L6 38, T13 45, four lumbar 8); 57 supported by their own field; 7 with an exported frame | automatic only; whether L5 and the sacral ala are in the field is unverified | CC BY-NC; every call on the test side |
| DeepFluoro | 6 cadaver pelves; 366 frames with exact pose | none | exact pose; vertebrae one merged class | detector training only |
| BUU-LSPINE | 3,600 cases; 7,200 films | 144 by the flag table; 9 of 15 L6 reads are children | levels counting-inferred by row order | EULA, never redistribute; 3,603 laterals sit in v8 and v9 and the licence reading is open |
| CSXA | 4,963 lateral cervical films | none | expert corner keypoints | in the v9 lineage |
| NHANES II | 364 persons landmarked; 17,073 films on disk | none read; the detector boxes a sacrum on 1.8 % of lumbar films | expert landmarks on 543 | 16,531 films in no trained bank; entered the older banks twice under two names |
| VinDr-SpineXR | 5,000 studies; 10,466 images | none | lesion boxes only | PhysioNet DUA; 0 in v9 |
| Render banks | ctsp\_drr 802; physics\_drr 7,045 annotations; physics\_rare 1,482 of 81 transitional subjects; ts\_drr 2,905; verse\_drr 387 | physics\_rare is the only labelled L6 and T13 at scale | exact pose by construction | inside the v9 lineage |

**The gates and today's n.**

| Gate | Pre-stated n | Today | Power today |
| --- | --- | --- | --- |
| Exact level on transitional real frames, Wilson lower bound 90 % | 35 persons with no error | 0 verified; 7 unverified (best-case bound 64.6 %) | 0 |
| Variant sensitivity lower bound 85 % | 22 carriers with no miss | 0 real; about 29 render-scoreable of the 43 G3 test L6 persons; 49 of 54 sit inside the current encoder's training | at a true recall of 72.4 %, P(22 of 22) is 0.0008 |
| Paper 2 H1, superiority over 82.2 % | 19 at-risk persons | 7 unverified | ineligible |
| Paper 2 H2, superiority over 97.6 % | 152 with no error; 708 for 80 % power | 0 | unreachable |
| T13 | 22 carriers, about 55 people in total | 7 persons in all sources, 0 real | 0 |

The one powered transitional statement available is the film difference: 49.9 % on 128 anomalous films against 89.9 % on 453, needing 74 per arm at a design effect of 4, with the truth tier stated as a radiograph count under an EULA.

**Measured against.** Kwak 2025 is the only 2-D LSTV model: accuracy 76.4 %, AUC 0.84 on 313 films at a 62 % positive rate, never to be benchmarked on a balanced set. Hanhivaara 2024 is the human ceiling: sensitivity 32 % and kappa 0.22 on radiographs against 76 % and 0.66 on CT. Manbachi 2018 is the human naming number on hard intraoperative films, 69.6 % unassisted and 97.6 % assisted. Farshad 2013 is the one lateral rule, sensitivity 94 % and specificity 74 %, fused types only. A single-lateral flag that beats all three on an unenriched set has found something or has leaked.

**The first experiment, same week, neither a model.**

1. The truth. A one-hour job projects the Dataset803 sacrum and L5 labels of ten COBRA planning CTs through their RTK geometry onto their own Elekta projections and renders the result, which answers by eye whether COBRA is spine data for the sacrum anchor. Then the reading protocol is frozen and the 63-volume queue is read on the CT through the two-stage review tree: the 57 field-supported COBRA calls, 3 re-read candidates and the 3 C-ArmLSpine CBCTs. The yield is recorded in two columns, confirmed on CT and scorable on a real frame, because only 7 of the 91 calls have an exported frame today.
2. The clean encoder (FLU-2). A ResNet-18 two-channel encoder from ImageNet on G3 training persons only, renders and real films mixed in every batch, no pseudolabels, three seeds, heads at lambda 0 and 1.0. Scored on the 7 render-scoreable of the 11 G3 validation L6 persons, with the single T13 person, the false-L6 rate and the film pattern table beside it. It is an evaluation arm, not the flagship training. Submit, estimate the wall time, write the job ids and ETA to the resume file, stop. No test person is scored until paper 2's ledger carries an "H1 seen" entry. Then the coupling script runs on the same frames to tabulate how often the count catches the whole-run shift.

**The stop rule.** Zero or one miss of the 7 proceeds to three seeds and two heads. Two or more misses stops the fluoroscopy arm and the manuscript says "not at parity" with the number. At a true recall of 72.4 % this screen passes 38 % of the time, at 85 % 72 %. If the read confirms fewer than 22 carriers with an exported frame, no fluoroscopy transitional sensitivity can be claimed and the render number is reported alone; the data requests are the only route to 22.

**What is missing and the exact step.**

| Missing | The step |
| --- | --- |
| Verified real-frame transitional persons, 0 of 22 or 35 | the 63-volume queue; expected about 5 L6 at the labeller's precision of 10 of 24, at most 8 four lumbar, near zero T13; about 13 verifiable on CT, at most 19; 22 cannot be reached from COBRA alone |
| Real paired sets outside the holding | send the drafted letters this week (SX-Stitch, Balgrist, the fourteen cine letters, none recorded as sent); draft LevelCheck (178 patients, 398 radiographs) and Huashan (140); fetch the free TCIA CMB XA frames and the NIT Warangal centroid files |
| The BUU licence reading | Greg decides whether BUU-derived weights may leave |
| The whole-cohort Castellvi read on CT | project CT-3, the largest increase in read positives on data already held |
| Two-labeller verification of every census flag | the review tree; a segmenter call is never promoted without a read |
| The open "use all" items | 16,531 NHANES films into detector self-training; the 3,600 BUU AP films into a bank or a written exclusion; all 10,466 VinDr images under a determination; the COBRA Varian export; FluoroCap as a 200-panel test set or written off |
| A chest-CT route to T13 | the CT-RATE form, the INSPECT DUA and NLST beyond the pilot, expected T13 95, 86 and 109 at the low prior; two labellers blind to each other, because the NLST pilot's 9.3 % fell to 1.5 % once a rib on the body was required |

## 3-D to 2-D parity on the paired sets

**The idea, stated precisely.** Use paired CT and fluoroscopy to see how the 3-D features that name a vertebra are represented in a 2-D projection, engineer those features into the 2-D model where it confuses levels, and reach parity between 3-D single-level classification from local morphology and 2-D. Three facts in the record bend that statement before it can be measured.

1. The 3-D number is a within-patient number. The published 0.990 for T12 against L1 uses five measures each divided by the case's own median across its measured levels, plus six between-measure ratios. A vertebra alone in a field has no case median. The six ratios are size-free and would be the single-vertebra feature set; their AUC without the case median is not on disk.
2. The 3-D discrimination at the thoracolumbar junction is coronal. Transverse-process span carries three of the top five standardised weights (minus 1.851 on the 2026-10-08 rerun). On a lateral the process is superimposed on the body. Every 2-D naming number in the programme was built on lateral frames or renders, and AP naming is 43.7 % zero-shot.
3. At the lumbosacral junction the 3-D target is undefined without the count. The article attempts no shape classifier there; L5 and L6 are one bone under two counts, and no CT L6 identification rate from the programme's own model exists.

So the question splits. At the thoracolumbar junction parity is measurable now and the obstacle is the view. At the lumbosacral junction parity needs a 3-D number first, and that number may not exist from local shape; the record routes the extra body to the count from the sacral anchor. The fused L5 is a third case where the pelvis carries the signal (sacral slope AUC 0.73). Only one real paired set carries level truth on a living spine, C-ArmLSpine, and its truth is automatic with the thoracolumbar junction removed. The exact pairs with full level truth are the programme's own renders of its labelled CTs. That is where the question is asked first, with the real sets as the check.

**The 3-D feature inventory.** Visibility columns are hypotheses the experiment measures, not results.

| Feature | 3-D discriminating power | Lateral | AP | 2-D analogue and published reliability | Defect carried into 2-D |
| --- | --- | --- | --- | --- | --- |
| Transverse-process span | the dominant T12 against L1 feature | not readable | readable | tip-to-tip span on the AP; reliability not on disk | 169 process heights overstated by speckle before correction |
| Transverse-process height, lowest lumbar | Castellvi I at 19 mm; the II and III screen | not readable | readable, the Castellvi definition | radiograph kappa 0.22 against CT 0.66 (Hanhivaara 2024) | the screen keys on an unfused process |
| Process to ilium gap | Castellvi II and III | not readable | readable where ala and process overlap | Ferguson view, named only in an unverified sweep | three sacrum-side cues at chance |
| Anterior body height | monotone T11 to L5; weight minus 1.012 | readable | partly | lateral morphometry ICC above 0.95 (unverified, web) | the cohort sits about 6 mm above Panjabi |
| Posterior body height | a plateau; the encoder ignores it | readable | poorly | as anterior | ostk 1b7005c inflates it 10 to 17 mm on 1 in 7; use the release column |
| Wedge ratio | monotone; the best interpolated feature (Q² 0.78) | readable | partly | Farshad 2013, a wedge-type lateral rule, sensitivity 94 %, specificity 74 % | none recorded |
| End-plate width | rises caudally; weight minus 0.643 | not readable | readable | not on disk | L5 withheld: SD 1.58 times the widest published |
| Canal width, interpedicular | rises caudally; weight minus 0.768 | not readable | readable between the pedicle ovals | AP film is the standard projection; agreement with CT not on disk | within 0.2 to 2.9 mm of Panjabi |
| Canal depth, midsagittal | flat; the encoder ignores it | partly | not readable | not on disk | rewritten after the floor defect |
| Pedicle width | widens into the lower lumbar (Zindrick 1987) | not readable as width | readable as the pedicle oval | cervical radiograph against CT r² 0.665 (unverified, web) | L5 reads 20.7 against a published 16.2 |
| Rib presence, 12th rib length, lumbar rib | the thoracolumbar junction; Kwak's attention sits here | partly | readable | no published 2-D stump-rib detector; Möller CT F1 0.84 | ribs at or under 50 mm: 152 twelfth against 10 lumbar |
| Superior facet joint angle | thoracic 72 to 83 against upper lumbar 21 to 47 degrees on three spines | not readable as an angle | partly | Schinz 2026 criterion, CT only | not built; n 3 |
| S1 plate angle, sacral slope | the lumbosacral junction; v11 only | readable | not readable | the 2-D port reproduces the 3-D angles on identical geometry | id 29 retired; everything sacral from v11 |
| Bony fusion L5 to ala (Castellvi III) | count-changing; 9 of 9 count-style sacralisations are IIIb | partly | readable | Farshad 2013, fused types only | a 12-case direction, not a validation |
| Iliac crest level against L4 and L5 | the last lumbar vertebra | readable | readable | crest tangent sign on MRI, sensitivity 81 % | none recorded |
| Iliolumbar ligament origin | last lumbar in 95 % of controls | not readable | not readable | needs axial imaging | dropped |

No bank projects pedicle width, canal width or depth, process span or height, rib facets or the S1 plate as a 2-D landmark today. That gap is the first thing the experiment closes. Names go through `labels_for`, never a fixed map; identifier 29 is retired; zero-pad before any join; the token is not the record id.

**The paired data.** C-ArmLSpine: one CBCT per case with same-session AP and lateral frames, at most 149 cases, automatic truth agreeing on 814 of 910 vertebrae, T12 named on 10 % and T11 on 0 %, poses by edge registration. DeepFluoro: 6 cadaver pelves with exact pose and one merged vertebra class. COBRA2026: 692 planning CTs with exact RTK geometry, spine coverage unverified. Ljubljana: one cadaveric L1 to L5 with gold pose, no derivatives allowed. The programme's renders: 802 CTSpinoPelvic1K, 374 VerSe and 1,170 TotalSegmentator CTs plus 81 transitional series, exact by construction, boxes and end-plate corners only. Not held: LevelCheck (178 patients), Huashan (140), VerSeg-Net (50), Charters (527), Petragallo (429); no request recorded as sent.

**The visibility experiment, three stages.**

1. Stage 1, an hour on the laptop: the single-vertebra 3-D target. Drop the five case-median features from the separability script, keep the six ratios, run T12 against L1 grouped five-fold by case. Fit the seven-level shape model T11 to L5 on the 643 ordinary records and apply it to every body of the 18 six-lumbar spines. Then L6 against ordinary L5 on the ostk rows with the reduced ratio set (the process span is not in that table), 13 positives against 757 L5 rows after the disputed record 0033 is removed, leave-one-case-out with a permutation p-value and a case-grouped bootstrap. Render five L6 masks before any L6 row is believed. Gate: AUC at or above 0.95 means a single-vertebra target exists; 0.90 to 0.95 means one body plus a neighbour; below 0.90 the parity target is a window of three or more bodies and the 2-D one-body 74.8 % is never compared to 0.990. Outside check: the sign of every weight against Panjabi 1991 Table 3, and Schinz 2026's 100 % on 1,242 CTs.
2. Stage 2, a day on the grid: projected morphometry at exact pose on the 802 v11 label volumes. Rebuild the lateral and AP projected-landmark bank from the v11 tree, never the v10 Hugging Face mirror. Project every label and every SPINEPS subregion separately (body, processes, facets, ribs, sacrum, hips) at lateral 90, AP 0, and an arc at 10-degree steps with tilt. Measure the 2-D analogues on the projected silhouettes, never on the grey image. Compare 2-D against 3-D per level and per view: bias, SD, ICC with case-clustered intervals, Bland-Altman limits, and the share of records where a silhouette is not separable from a neighbour. Rerun the separability test unchanged on the 2-D readings, lateral only, AP only, both, and the best arc pose. At the lumbosacral junction report descriptively only. Render twenty records per view with every chord drawn before any number is believed. Gates: a feature is represented in a view at ICC 0.75 or above with the clustered lower bound above 0.60 and its SD inside the widest published living SD; partly represented at 0.50 to 0.75; not readable below 0.50. The junction verdict per view is the T12 against L1 AUC on the represented features: 0.970 or above is parity at the geometry step, 0.90 to 0.97 partial, below 0.90 failure for that view. Smallest first run: fifty records, lateral and AP, T12 to L4, two hours, a smoke test of the code with the gates scored on the 802. L2 to L4 are in because L3 carries the largest one-body error count on the real C-arm.
3. Stage 3, real frames on C-ArmLSpine and COBRA2026, after stage 2's definitions and after the pose verdict (does naming accuracy track registered pose quality; no file has answered it). Compute the 3-D morphometrics on each CBCT, re-fit the poses at the true 0.150 mm pitch, reject frames with poor edge agreement or box disagreement above 0.25 body, project the per-vertebra landmarks onto each frame and render overlays. Regress each 3-D measure from the frozen encoder embedding of the body's crop and again from the projected landmarks measured on the frame: the two separate "the encoder does not encode it" from "the projection does not carry it". Report the three one-labeller L6 cases as agreement, never correctness. The real check already on disk: R² 0.65 for anterior height, 0.63 for process span, 0.75 for wedge, and negative for posterior height on L2 to L5 centroids.

**The variants the experiment would feed.** None starts until stage 2 has said which features a view carries, and each is a published method with its number, decided by Greg before it is built.

| Variant | Published analogue | First arm | Gate |
| --- | --- | --- | --- |
| V0, the measured 2-D feature arm | Farshad 2013, the one lateral rule | reproduce Farshad on lateral renders of the 21 graded III and IV records and 643 ordinary records; then the ALPHABET\_LOSS protocol with the feature vector appended | sensitivity 0.75 or above transfers the rule; below 0.60 the lateral is empty for the fused class |
| V1, feature-supervised auxiliary heads | multi-task regression beside the class head; Payer 2020's landmark network is the closest lineage | the ALPHABET\_LOSS protocol exactly, three seeds, paired case-cluster bootstrap against lambda 0, targets as size-free ratios | the pre-stated rule on L6 recall, film held, false-L6 cost; T12 against L1 one-body accuracy on the real C-arm beside 41.2 % |
| V2, projection-consistent training | multi-view consistency; must not become a sequence loss, which re-injects the counting prior | renders only; the case134 302-frame spin as the n 1 real check | the per-angle naming curve against 82.1 % at trained angles and 52.8 % elsewhere |
| V3, DRR curricula and the ratio sweep | SyntheX parity; the own two-stage arm lost 25.6 anomalous points | the 45-cell array, three seeds, L6 scored separately | a cell that raises held-out L6 recall without lowering ordinary film by more than the seed spread (1.0 point) |
| V4, pose-conditioned features | no spine paper on disk; the device cards carry nine terms worth +4.3 | renders with the pose against the same renders without it, per angle bin | a gain in the 16 untrained bins that survives on the real spin |

Excluded by the record: Star Temporal Classification, CycleGAN, ADDA, CUT and SDXL restyling, decoder-named pseudolabels, size in millimetres as a scalar, and a learned refiner as the 2-D reference.

**The parity metric.** Two single-level accuracies side by side, on the same persons and one label set, T11 to L5, with the junction pair as a second row where the 2-D posterior is restricted to T12 and L1 so chance is equal. The 3-D side is the stage 1 ratio-only shape model refit on G3 training persons, with no case median, no position, no rib and no segmenter name, scored on the held-out bodies of the 73 CTSpinoPelvic1K persons in G3 validation. The 2-D side is the one-body-in-field accuracy of the clean 2-D classifier on renders of the same bodies at the view under test, then on real frames where they exist; it waits on the clean encoder, because 801 of 802 persons sit in the v9 lineage. Parity is a pre-stated non-inferiority claim with a 5-point margin. An interval that merely includes zero is not parity. The published 0.990 is reported beside the two accuracies as the ceiling, never as the 3-D side.

**Gates and the stop rule.** A feature not readable in every view at exact pose with no noise leaves the inventory, and if every feature separating a pair is in that state the pair is routed to the count and the parity claim for it withdrawn. If lateral and AP readings together do not reach T12 against L1 AUC 0.90 on exact-pose renders, no 2-D model on real frames will, and the claim is withdrawn before any network is trained. A feature that survives renders and dies on real frames is a formation or truth fact until tested on a second device. An AP-only feature is a true result and a workflow constraint, stated, not forced into a lateral model. Nothing is claimed at the lumbosacral junction until a 3-D single-body number exists on the same persons. No held-out render number for a v9-lineage model is quoted except through the unseen-cases list.

**n and power.** Stages 1 and 2: 1,486 T12 and L1 vertebrae from 798 cases, AUC interval about plus or minus 0.006, so a 0.02 difference is decidable. Per-feature ICC on 663 to 802 records per measure and level. L6: 13 positives, so stage 1 separates no signal from some signal and nothing finer. The parity comparison: 73 persons, about 146 junction bodies, a paired interval of about plus or minus 7.5 points, so the minimum detectable deficit is about 8 points and the 5-point margin is decidable only once the 93 test persons are added after "H1 seen". Stage 3: L1 in 76 lateral frames, L2 to L5 in 123 to 142 each, one device, so device against anatomy cannot be separated on this set alone.

**Outside checks.** The spread test that caught both defects in the dataset article, the render, Panjabi for the sign of every weight, Schinz for the 3-D side, Hou 2020 for the rule that a 2-D feature agreeing with a 2-D read is not validated, Hanhivaara's radiograph kappa 0.22 as the bound on what an AP process feature can add, Rohlfing 2012 on overlap not being evidence of a correct mapping, and Kwak's T12-rib attention as the warning that a feature study can reproduce the counting prior it means to replace.

## CT-based projects

Ranked by how little stands between the holding and a result, and by what each unlocks. Every project names its outside check, because the recurring failure in this programme is a number that is wrong but plausible.

| Project | Question | First experiment | Gate | n or power | Outside check |
| --- | --- | --- | --- | --- | --- |
| CT-1, the ostk canal-closing fix | does restoring the per-section hole rule bring posterior body height and end-plate depth back within 1 mm of the release rows | per-section hole area at least 18 mm², wall taken only from sections whose hole reaches the canal's median area; run on record 0097 and twenty records; render ten body cuts; then guard the retired `"S1": 29` so a by-name call raises | 0097 within 1 mm; share under the 11.07 mm living floor at or below 5.2 % (twice the published 2.62 %); the number to move is 15.8 % of reader E's instances under that floor | 802 records by five levels | the published floors and prevalence; "the numbers moved toward the mean" is not a pass |
| CT-2, the anterior pelvic plane over 802 | what is the anterior-pelvic-plane sacral slope beside the scanner-axis one, and does the gap to Veilleux exist on v11 at all | step 1 recomputes the v11 means and medians beside Veilleux to confirm the gap is 0.1 degrees, not the 3.4 the stale estimator note argues from; then one script fits the plane from the hip labels on 802 | the plane-referenced slope inside the published supine band (+5.1 Uemura; +8.6 to +12.2 Jenkinson); Suzuki 2020 ICC 0.856 | 802; 756 pass the plate gate | a manual spinopelvic read on a sample, which does not exist yet |
| CT-3, the whole-cohort Castellvi read, the re-reads and the VerSe mask count | how many Castellvi II to IV spines does the cohort hold, and does the rib anomaly co-segregate with the lumbosacral one | one script counts ids 25 and 28 per raw VerSe mask against the Loeffler table; a third reader blind to the first two reads the nine disputed records; then two readers grade all 802 in the review tree with a senior adjudicator | the II to IV rate inside 9 to 18 % and type I near 68 % of calls, or the read is suspect; second-reader kappa at or above 0.63 | 802 at 3 to 5 minutes a case, about 40 to 67 reader-hours; 33 graded today against 71 to 142 expected | Hanhivaara 2020 prevalence; Nagata 2025 co-segregation; the VerSe odds ratio 3.61 |
| CT-4, the 3-D single-body classifier and the LS-L6 certification | can one rib-free body be called thoracic or lumbar from its own facet angle, process position and shape, with no case median; can a segmentation classifier pseudo-adjudicate LS-L6 at a precision lower bound of 0.90 | the stage 1 ratio-only run; a 20-CT timing task across three segmenters; logistic regression on the facet and process features, grouped five-fold, five seeds; then the LS-L6 pool | precision lower bound 0.90 on LS-L6, at most 3 errors on 88; segmenter invariance as a hard demotion | 1,486 for the junction pair; 88 for LS-L6; every other phenotype short by 7 to 33 reads | Schinz 2026 100 % on 1,242 CTs; VERIDAH 97.22 %; HealthOST 91.49 % |
| CT-5, the level atlas revision | does measuring each vertebra in its own frame, with the end-plate from a corpus label, restore L5 and bring every per-level SD inside the published range | rerun end-plate width at L1, L4 and L5 from the SPINEPS corpus label on the same records; score with the three spread columns | no rule ships unless it beats the shipped rule on all three columns; the last three attempts each won one and lost another | 802, paired | render twenty retained L5 masks before any number; Bonczar 2024 and Griffith 2022 SDs |
| CT-6, the L6 learnability curve | at how many distinct six-lumbar cases does L6 Dice leave zero, and does the rib-free counting decoder beat it at every n | preprocess Dataset815 (1,176 cases, 62 L6), repair the flags, one fold at 18, 36 and 62 distinct L6 | the endpoint is the rib-free count by status, not Dice | three points, read against the 28 L6 training scans that sufficed in VerSe'20 | the counting decoder on the same folds; the 25-presacral share 5.5 to 8.2 % |
| CT-7, the anchor-ordinal design | do two dense ordinal fields, from the sacrum and from the lowest rib-bearing body, plus a per-body type, flag the variant as a consistency violation | arms 1 and 2 as a matched pair on the same folds | an ROC on count disagreement separating the 26 transitional-labelled records at counts 4 and 6 from the 757 normal-labelled at counts 4 and 5; the 7 transitional at count 5 and 9 normal at count 6 are the cells a count alone cannot separate | 802 | patch geometry measured on the corpus |
| CT-8, the rib phenotype by the vertebra | does the costal facet separate a hypoplastic twelfth rib from a lumbar rib where length cannot | calibrate the pre-registered rule on the VerSe masks against the Löffler stump column; then the facet signal on named T12 and L1 bodies | Möller's reference distributions reproduced before the rule is used | 30 read positives | prevalence windows: thirteen rib-bearing 0.37 to 0.88 %, lumbar rib 1.6 % |
| CT-9, the super-detector adjudication | how many of the 1,052 positively flagged and 1,285 disagreement-flagged tier-1 CTs are transitional | finish the pre-registration calibration list, fill the freeze line, run the flag over tier 1, open the review queue with paired cases first | specificity maximised at sensitivity at or above 0.95 on read-tier positives, computed before the sweep | 1,052 cases is 50 to 90 reader-hours per stage | per-collection call rate against the prevalence windows; the 33-CT census discrepancy resolved |
| CT-10, the competitor benchmark in one scoring space | on the same 802 records, what count and name does each public system give, and where does each fail on the 33 graded | run the benchmark collector and print the offset histogram and whole-spine shift count per phenotype | every mask passes the monotonic check; truth scores Dice 1.000 through the same path | 802; 33 graded; 18 L6; 9 four-lumbar | a system's number on its private cohort and its number here are two numbers |
| CT-11, segmental mobility from the 351 prone and supine pairs | per-segment angular change between postures | pseudolabel the second acquisition of 20 pairs out of fold; require pelvic incidence to agree within its repeatability before any angle is read | pelvic-incidence invariance across the pair | 351 pairs | Panjabi segmental ranges as the envelope; recorded as a later paper |

Two housekeeping items gate publication rather than research: the dataset article resubmission (seven items needing Greg; REPRODUCE.md corrected to v11 and to the solved 128-record failure) and paper 1's eight rigor fixes, held for the technology-transfer answer.

## Datasets by project

"After migration" is a target path, not a state. Any direction that reads from the Ceph volume must first check the batch STATUS file on the grid. The fluoroscopy sources are tabled in the classifier section above and the paired sets in the parity section; this section adds the CT sources, the holdings no model uses, and the missing sets with the step that gets each.

**CT sources.**

| Source | Holds | Labels | Transitional content | Restrictions and traps |
| --- | --- | --- | --- | --- |
| CTSpinoPelvic1K v11 | 802 records, one per patient; 422 supine, 377 prone | radiologist-sourced vertebrae; sacrum and hips expert where fused; ribs student-corrected; Castellvi consensus on 33 | L6 18 by label and 16 by the readers; four-lumbar 9; no field reaches T1 | labels CC BY-NC-SA; the public mirror is v10 with id 29; 801 of 802 are in the v9 lineage through renders |
| CTSpine1K | 1,005 volumes | expert VerSe-convention masks | the authors list 24 lumbarisation and 13 sacralisation | 782 COLONOG volumes are CTSpinoPelvic1K persons |
| VerSe and VerSeFusion | 374 scans of 355 subjects | expert masks C1 to L6, T13; the Loeffler table by two neuroradiologists | L6 85 scans, T13 6, sacralised 13, Castellvi II 27, lumbar rib 12 | `has_T13` is wrong (18 against 6); 39 of 85 L6 masks lack id 25; never vf\_813 for whole-spine work |
| TotalSegmentator v2 and v3 | 1,228 and 1,935 scans | model output refined; no L6, T13 or lumbar-rib class; `sacrum` excludes S1 | two-labeller L6 14; outside reads on 70 CTs found 12 to 17 of 28 | 1,118 v3 CTs are byte-identical to v2; `s####` is not stable across releases |
| The acquisition tiers | 21,622 CTs; tier 1 5,094 | two pseudo-labellers; no radiologist read on any acquired CT | flags L6 303, T13 82, review 1,168; expected L6 322 and T13 38 to 119 over the 18 screened collections | 127 exact folds merged; 1,186 near-duplicates unmerged |
| Dataset813 and Dataset815 | 802; 1,176 cases | nnU-Net raw | 18 L6; 62 L6 and 4 T13 by manifest | 815 never preprocessed; 813 flags stale; links resolve only inside the container |
| RibFrac, RibSeg v2, Möller masks | 660 chest CTs | expert ribs; stump masks | T13 4, single labeller | 648 of 743 analysed, 95 unexplained |
| RSNA 2022 cervical | 2,019 studies | per-level fracture labels | none | zip never unpacked; used by nothing |

**Holdings no model uses.**

| Item | n | Why unused | What would change it |
| --- | --- | --- | --- |
| NHANES II unannotated films | 16,531 | never offered to the detector | detector self-training |
| BUU-LSPINE AP films | 3,600 | in no bank; no written criterion | a bank or a one-sentence written exclusion |
| VinDr-SpineXR | 10,466 | pseudo levels; test split consumed; DUA | a determination and study-keyed splits |
| AASCE, Spinal-AI, anchor\_drr, Mendeley, lateral\_236 | 457; 8,358; 7,842; 584; 212 | fed only deleted banks; anchor\_drr's own split put 301 of 801 persons on both sides; Mendeley is a BUU redistribution | AASCE and Spinal-AI wholly on one side; Mendeley stays out |
| COBRA cases not exported; Varian | 547 of 692; 225 | the exporter refuses Varian | write the Varian export |
| DeepFluoro vendor frames without a pose | 2,293 of 2,659 | no released pose | pose recovery |
| C-ArmLSpine sweep projections and the case134 spin | 602; 302 frames | only one script reads a sweep | export into the real-frame layout |
| ts\_drr\_v3 | 1,735 renders | never benched | a held-out TotalSegmentator test by CT hash |
| Dataset815 | 1,176 cases, 62 L6 | never preprocessed | the preprocessing job where singularity resolves |
| Tier-1 acquisition CTs | 20,280 | read by no one, in no bank by design | the reader queue |
| FluoroCap | 29,500 panels | dropped by directive; the 200-panel test set does not exist | annotate about 200 or write it off |

**Missing sets and the step to get each.**

| Set | Adds | State | Step |
| --- | --- | --- | --- |
| LevelCheck clinical cohort | 178 patients, 398 intraoperative radiographs; about 16 at-risk persons at 9 % | no request drafted | a letter to the I-STAR group |
| Huashan | 140 patients with CT and intraoperative AP and lateral films; about 13 at-risk | no request drafted | ask for device, headers, frames per patient, DUA terms |
| SX-Stitch | 1,032 overlapping intraoperative frames with masks | drafted 2026-09-23, not sent | send |
| Balgrist ex-vivo | 19 specimens, three C-arms | drafted, not sent | send |
| Fourteen cine letters | real cine with level-named tracks | drafted, not sent | send |
| Charters 2024, UCLA | 527 patients, 2,486 paired kV with registration | not drafted | write |
| Jaganathan and Maier | 55 thoracolumbar CBCT sweeps | never released | ask under a DUA |
| TCIA CMB-MML and CMB-AML XA | 16 patients, one spine procedure | open, not fetched | fetch as a Slurm job |
| NIT Warangal | 9 level-named patients | public | download |
| Merlin (Stanford AIMI) | 1,260 expected transitional people at the low prior, more than all of tier 1 | gated, no form signed | accept the AIMI DUA |
| CT-RATE, INSPECT, NLST beyond the pilot | T13 95, 86 and 109 expected at the low prior | gated or held by the stopping rule | the gate form; the DUA; finish the tier-1 screen |
| Griffith 2022 per-level SDs | the matched comparator for the atlas | paywalled | interlibrary request |
| Li 2016, Li 2017, ABLSpineLevelCheck 2024 | the naming-novelty risk | IEEE Xplore blocked | a library request before any submission |

## The ranked project list

| Rank | Project | First step | Gate | n today against n needed | The decision it returns | Depends on |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | PAR-1, the single-vertebra 3-D target | the ratio-only variant of the separability script, T12 against L1, one hour on the laptop | AUC at or above 0.95, 0.90 to 0.95, or below 0.90 | 1,486 against 1,486; L6 13 positives against 757, nothing finer than "some signal" | what parity is measured against: one body, one body plus a neighbour, or a window | nothing |
| 2 | PAR-2, projected morphometry at exact pose on the 802 v11 volumes | fifty records, lateral and AP, T12 to L4, a two-hour smoke test on reqp, job ids and ETA written to the resume file; then all 802 and the arc | per-feature ICC tiers 0.75 and 0.50; junction AUC tiers 0.97 and 0.90 | 1,486 against 1,486 | the per-feature, per-view visibility table and the view each confusion pair needs | PAR-1's feature list; the v11 tree on the grid |
| 3 | FLU-1, the real-frame transitional truth file | the one-hour COBRA coverage render; the 63-volume reader queue under a frozen protocol; the Elekta export of every confirmed case | 22 carriers for 85 %; 35 at-risk persons for 90 %; 19 for paper 2 | 0 verified against 22 or 35; expected 5 to 13 verifiable on CT, at most 19; scorable on a real frame only where a frame exists, 7 of 91 calls today | whether any anomaly-aware claim on real frames can ever be powered from the holding; the requests are the only route to 22 | a reader; the protocol freeze; the Varian exporter or a written exclusion |
| 4 | CT-3, the re-reads, the VerSe mask count and the whole-cohort Castellvi read | the VerSe raw-mask count script, under an hour; the nine re-reads with a third reader | II to IV rate inside 9 to 18 %; second-reader kappa at or above 0.63 | 33 graded against 71 to 142 expected | the lumbosacral truth pools and the rib co-occurrence test at power 0.98 | two readers and an adjudicator |
| 5 | CT-1 and CT-2, the ostk fix and the anterior pelvic plane | record 0097 alone, under an hour; fifty records with ten renders, two hours | 0097 within 1 mm; the plane angle inside the supine band; the v11 gap to Veilleux confirmed at 0.1 before the fit | 802 | safe 3-D columns for every twin; the plane-referenced sacral slope beside the scanner-axis one | nothing |
| 6 | DAT-1, send the drafted requests, draft two, fetch two | the letters out this week; "sent" recorded in the manifest card | a reply naming a DUA route for at least one set of 100 or more living patients | 0 sets against 19, 35 or 60 persons | whether real transitional n can come from outside the holding | Greg's signature |
| 7 | PAR-3, Farshad 2013 on lateral renders | the 21 graded III and IV records and 100 ordinary renders, half a day | sensitivity at or above 0.75 transfers; below 0.60 the lateral is empty for the fused class | 21 positives, 643 negatives | the one literature-grounded lateral feature, or its absence | the v11 end-plate corners from PAR-2 |
| 8 | PAR-4, pose quality against naming on C-ArmLSpine, and the sacra called L6 | the exactness-by-quartile table, two hours; render the 24 sacrum crops and the four off-bone laterals | odds of an error per 0.25 body of disagreement with an interval excluding 1 | 617 lateral and 631 AP bodies; 24 sacra | go or no-go for the real paired probe; a crop rule or a class problem for the sacrum | the per-frame registration scores on the grid |
| 9 | FLU-2, the clean-lineage encoder, validation side | one seed, lambda 0; scored on the 7 render-scoreable of the 11 validation L6 persons; then three seeds, two heads, and the coupling script on the same frames | zero or one miss of 7 proceeds, two or more stops; the count catches at least 80 % of run-shifted films | 7 render-scoreable validation persons; about 29 of 43 test persons after "H1 seen" | the first quotable held-out render number, or the "not at parity" sentence | FLU-1's protocol; the audit-only persons segmented; the paper 2 ledger entry; the BUU licence decision before any weight leaves |
| 10 | CT-4, the 3-D single-body classifier and the LS-L6 certification | timing on 20 CTs; the facet-angle model on unambiguous bodies | precision lower bound 0.90 on LS-L6, at most 3 errors on 88 | 88 against 88; other phenotypes short by 7 to 33 reads | the 3-D side of parity at both junctions | CT-1; CT-3's re-reads; Greg's fourteen decisions |
| 11 | PAR-5, the real paired probe on C-ArmLSpine | morphometry on the CBCTs; the pose re-fit at 0.150 mm; the embedding regression per feature per view | Q² above 0.5 on the lateral for any feature beyond height and wedge, or the parity work moves to AP | L1 in 76 lateral frames; L2 to L5 in 123 to 142 | which 3-D features a real frame carries, per view, on living spines | PAR-2's definitions; PAR-4's verdict; CT-1 |
| 12 | PAR-6, the measured 2-D feature arm and variants V1 to V4 | V0 under the ALPHABET\_LOSS protocol; each variant only after Greg's decision | HELPS, TRADE-OFF, HURTS or NOT SHOWN by the pre-stated rule | 10 held-out L6 evidence persons and 0 T13 | whether explicit 2-D morphometry moves the junction pairs, with a number | PAR-2, PAR-3, PAR-5, FLU-2 |
| 13 | CT-6, the L6 learnability curve on Dataset815 | preprocess 815; repair the flags | Dice leaves zero at 36 or stays zero at 62 | 62 distinct L6 with a read | whether L6 is learnable as a voxel class from this corpus | GPU time; CT-3's flags |
| 14 | CT-5, CT-7, CT-8, CT-9, CT-10 | as in the CT section | as in the CT section | as in the CT section | atlas revision; the anchor-ordinal premise; the rib phenotype; the census adjudication; the benchmark | CT-1; the pre-registration freeze; readers |
| 15 | PUB-1, the dataset article resubmission and paper 1's rigor fixes | the seven items to Greg as a list; the reprint build; the eight fixes | ten published pages; the eval gate held out on every quoted row | none by policy | a citable dataset article; a submittable paper 1 | Greg; the technology-transfer answer |
| 16 | CT-11, prone and supine mobility | twenty pairs pseudolabelled out of fold | pelvic-incidence invariance | 351 pairs | a later paper | recorded as not a now-thing |

**The time order.** Week one has no model in it. PAR-1 runs on the laptop in an hour and tells everyone what parity is measured against. The COBRA coverage render and the VerSe mask count run as single one-hour jobs. PAR-2's fifty-record pilot and CT-1's 0097 test run the same day. The drafted letters go out and two new drafts are written, because they cost nothing and set the clock on the only route to real transitional persons outside the holding. The reader queues open: the seven re-reads plus two more first, then the 63 field-supported volumes, then the 802 for Castellvi grade. If a reader is free on Monday, the 11 field-supported COBRA L6 calls are the single most decisive afternoon in the holding, because they can retire the real-frame transitional claim before any model is built.

Weeks two to six: PAR-2 on all 802 and the arc; CT-2 closes the anterior pelvic plane; PAR-3 reproduces the one lateral rule; PAR-4 decides whether the registered poses are good enough for a real paired probe; FLU-2 trains the clean encoder and is read on the validation side only; CT-3's Castellvi read proceeds. After CT-1 and the re-reads: CT-4, CT-6 when a container partition is free, and PAR-5 once PAR-2 has frozen its definitions and PAR-4 has passed. After FLU-1's read: if 19 or more at-risk persons are verified with an exported frame, paper 2's power is recomputed under the replacement detector and the gate unblinded under the frozen protocol; if fewer, paper 2 is restated as awaiting verified cases and the requests decide its future. Only then is any G3 test transitional person scored, and only after the "H1 seen" entry. Last and conditional: PAR-6 and the variants, each an arm Greg has decided on.

Three rules run through the whole order. If the re-reads move a record, the G3 split changes and the leak audit is re-run before FLU-2 scores anyone. No weight trained with BUU laterals leaves until Greg has read the licence. Nothing trains on the flagship recipe before gates G0 to G3 close, and which gates are formally closed is not written in one place on the laptop; the pipeline-state tool on the grid is the authority.

## What is not known and where to look

**Where the three proposals disagreed.** They agreed on the facts and disagreed on the axis of ranking. Proposal A ranked by how soon a number comes back that changes a decision, using only data in the holding, and put the hour-long ratio-only 3-D run first and the clean encoder ninth. Proposal B made the parity idea the spine, wrote the richest feature inventory and the model variants with their published analogues, and placed the human reads second. Proposal C ranked by whether a pre-stated claim can be decided at the n on disk in a paper that already has a home, and put paper 1's close-out and the Castellvi read first. This page takes B as the programme, because the three asks are its structure and its feature-level specification is what a student can act on; it grafts A's "smallest experiment that changes a decision" for every project and A's ordering of the ratio-only run before the full projection study, and C's venue and power discipline and its list of claims unreachable at any n. The one open contest is the 85 % bound on the 43 test L6 persons: A and C allowed two misses, B's calculation allows one (42 of 43 gives 87.9 %, 41 of 43 gives 84.5 %), and the page uses one.

**The unknowns that decide a project.**

| Unknown | Where it was looked for | Why it matters |
| --- | --- | --- |
| The ratio-only single-vertebra T12 against L1 AUC, with no case median | the separability script, the anchor-ordinal design, the article | the 3-D side of parity; PAR-1 answers it in an hour |
| Any per-feature, per-level, per-view measurement of what survives projection | every research sweep, the literature folders, the CTSpinoPelvic1K docs | none exists; PAR-2 is the first |
| Any CT L6 or lumbosacral naming rate from the programme's own model | the NeurIPS paper gives voxel results only | parity cannot be claimed against an unmeasured number |
| A human level read on any real fluoroscopic frame | the results files and the C-ArmLSpine card | every real 2-D number is against automatic truth |
| Whether COBRA2026 projections cover L5 and the sacral ala | marked unverified in the paired-data sweep | decides whether COBRA is spine data for the sacrum anchor |
| How many of the 57 field-supported COBRA calls and the 303 L6 and 82 T13 acquisition flags are transitional | no read exists | the whole yield of FLU-1 and CT-9 |
| Whether C-ArmLSpine's 149 cases are 149 living people, under what ethics approval, and how its pose was obtained | the fourth research pass; the literature state | the person unit of every real-frame interval |
| Whether naming accuracy on C-ArmLSpine tracks registered pose quality | the card says not measured | PAR-4 and PAR-5 depend on it |
| Whether any drafted data request was sent or answered | the three request cards say "Sent: not recorded" | DAT-1's whole premise |
| What Li 2016, Li 2017 and ABLSpineLevelCheck 2024 report | IEEE Xplore blocked | could overturn paper 1's naming-novelty sentence; Li 2017 is the one title near the parity question |
| The true person-level transitional naming accuracy of any arm on real frames | the power tables | every planning value assumed 95 to 99 % |
| Which gates G0 to G7 are formally closed, and whether any migration batch is finalized | the flagship plan; no batch STATUS file on the laptop | every "run this on the grid" step |
| Which licence reading holds for CTPelvic1K, VerSe, DeepFluoro, Geneva and Ljubljana, and the BUU EULA terms for derived labels | the manifest's licence row | which banks may back released weights |
| The VerSe L6 count: 85, 47, 50 or 87 | three files disagree; no count from the raw masks exists | CT-3 does the count |
| A manual spinopelvic read on any CTSpinoPelvic1K record | the estimator docs and the toolkit | the only outside check on PI, SS and PT; CT-2 adds it |
| The spinopelvic numbers the estimator note argues from (SS 33.1) against the v11 release table (36.6) | the estimator note predates the 2026-09-11 plate fix | its 3.4-degree gap is 0.1 on v11; the section needs a rewrite |
| Whether the 2026-09-17 refutation of pretrain-then-fine-tune was ever re-run on a clean bank | the remedies note | the training-schedule default rests on a leaked-bank arm |
| The person counts behind AASCE's index groups, CSXA's one-image-one-patient assumption and VinDr studies per patient | the identity spec | every leak check is only as good as these keys |
| A validated reject rule or variance decomposition for any 3-D measure | the morphometry docs | the yardstick for how much 2-D error is method |

Two numbers quoted in the working notes have no on-disk source and are not used as checks: an "about 0.7 AUC from 2-D angles" paper and a TotalSegmentator Dice of 0.943.
