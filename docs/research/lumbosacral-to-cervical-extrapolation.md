# From the lumbosacral gold to C2: prior art and feasibility

Source: the thread "Census, Any-View table and report fix", 2026-10-22, on the owner's ask of 23:08
UTC: "with cobra it should work in any position, because i dont think the rest of the spine is that
different from the lumbar spine, or at least i think you can learn how to extrapolate this ability
from the lumbosacral all the way to c2 using a combination of drr+physics noise; denoising; and
generative ai, please push creating this workflow to a task along with doijng deep research into its
prior art and feasaiblity". The task is issue #135, workstream P of docs/research/xr-from-3d/README.md.
The research is two literature searches run from the thread on 2026-10-22, one on training X-ray
models from renders of CT and the gap to real images, one on naming levels across the whole spine;
the nine papers that carry the argument were read a second time against their primary sources, and
the note was then reviewed adversarially against the repository's records and the two searches
(section 8 says what each changed). Confidential with the rest of this repository (docs/project.md):
it describes methods.

## 1. The answer in short

- **The ingredients are published and work, on the pelvis and the thoracolumbar spine.** Renders of
  segmented CT with physics, several renderers and heavy appearance randomisation reach parity with
  real training on pelvic bone landmarks and segmentation (SyntheX). On vertebrae a gap stays even
  after translation: about three times the error of real training for thoracolumbar 2D/3D
  registration (Jaganathan 2023), about 0.07 Dice from renders to real C-arm frames for T1 to L5
  segmentation (Spine-DART), and translation only matching fine-tuning on the lumbar spine (Jecklin
  2024). A detector trained only on images synthesised from 297 CTs labelled vertebrae at 88.3 % on
  real intraoperative Long-Film images (an extended-field tomographic mode) of 13 cadavers (Huang
  2022). So render-trained work on thoracic and lumbar C-arm images is Published; on the cervical
  spine it is not.
- **The extrapolation itself has never been shown.** No paper trains a level namer on one region of
  the spine on radiographs or fluoroscopy and tests it on another. Every whole-spine method, in CT,
  MRI or film, names levels the same way: it finds the chain, keeps the order, and counts from an end
  it can see (C2, S1, the last rib). The thoracic spine, farthest from both ends, is the weakest
  region in most per-region tables, cervical naming fell to 69 % at one external site (Netherton
  2025), and a shift by one whole level is the dominant error everywhere.
- **The anatomy does not have to be extrapolated.** The segmented CTs cover C1 to S1 (VerSe,
  TotalSegmentator and CTSpine1K, whose level truth the registry calls partial; RSNA 2022 cervical
  gives only C1, C2 and C7 anchors and is still zipped), so renders give cervical and thoracic truth
  as good as the CTs' level labels, which are least reliable in the thoracic count (section 3). A
  level count on every CT, ribs included, comes before the renders.
- **What would travel upward is the correction from render to real frame,** the device's noise,
  blur, scatter, processing and the translation model, learned on the lumbosacral pairs, the only
  place a real frame and a render of the same pose exist. That it travels is the hypothesis P tests,
  Inferred and untested: no cited study varies the anatomy under a fixed device, and Jecklin's
  comparison of Siemens and Ziehm C-arms on lumbar specimens, which found no clear difference, says
  nothing about anatomy. Parts of the image chain depend on the anatomy and no lumbosacral pair
  contains them: automatic exposure control and dynamic range at the shoulders and over the lungs,
  the scatter fraction through the chest, the mandible over C2. These are the reasons it may fail.
- **The hard part is the field of view, not the shape.** A C-arm spot frame of T7 shows neither C2
  nor S1, so a single frame cannot be counted from an end. Naming on a mid-thoracic or mid-cervical
  spot frame needs a cue inside the frame (the ribs, the shoulders at C7-T1, the mandible and the dens
  at C2, the sacrum and the crests at L5-S1) or context outside it (a sweep, the previous frames, the
  counting prior of workstream A). This is where "any position" is decided, and it is measured per
  region and per field of view, not assumed.
- **Feasibility grade:** the render, noise and translation pipeline is Published for the pelvis and
  the thoracolumbar spine; the transfer of a correction learned on lumbosacral pairs to cervical and
  thoracic frames is Inferred and untested; naming on a single collimated mid-thoracic or
  mid-cervical frame with no anchor in view is Inferred and doubtful. A cheap first arm answers the
  anchor question; the correction's arm costs most of row P's budget (section 6).

## 2. The gap from render to real, as measured

| Setting | Paper | Renders, tested on real | Real, tested on real | Renders, tested on renders | Reading |
| --- | --- | --- | --- | --- | --- |
| Pelvis landmarks, plain DRR | Unberath 2019, IJCARS 14(9):1517 | 78.2 mm | n/a | 6.70 mm | a plain render fails |
| Pelvis landmarks, full physics (poly-energetic, materials, scatter, noise) | Unberath 2019 | 24.7 mm | n/a | 6.35 mm | physics alone leaves a gap of four times |
| Pelvis landmarks, physics and strong randomisation, 500 renders each of 20 CTs | Gao 2023 (SyntheX), Nat Mach Intell 5:294, the published numbers | 5.95 mm, Dice 0.86 | 6.46 mm, Dice 0.79 | n/a | parity or better, on 366 real frames of 6 cadavers |
| Pelvis landmarks, one renderer; then four renderers with nine randomised stages | Grimm 2021, IEEE TMI | 11.7 mm, 98 to 100 % missed; then 6.4 mm, about 20 % missed | n/a | 5.9 to 6.2 mm | renderer diversity and randomisation together close the error; recall is the sensitive number |
| Pelvis landmarks, renders of the specimen's own CT versus 2D diffusion conditioned on projected masks | Rapuri 2026, arXiv 2606.21414 | renders 7.83 mm, diffusion 4.40 mm, on predictions whose heatmap matches the truth well (NCC above 0.6, a filter at evaluation) | 4.89 mm | n/a | at NCC above 0.2 the order flips: diffusion 25.40, renders 17.92, real 18.94, renders at 500 views 9.73 (the paper's Table 1, second reading) |
| Thoracic and lumbar vertebrae, 2D/3D registration on clinical cone-beam CT | Jaganathan 2023, WACV, arXiv 2210.07611 | 3.78 mm, 10 % success plain; 2.97 mm, 66 % randomised; 1.83 mm, 90 % with translation (CUT) and feature alignment | 0.65 mm, 99.4 % (a comparison method retrained on paired real X-rays) | n/a | a gap of about three times stays |
| Lumbar vertebrae, 3D reconstruction from real fluoroscopy of ex-vivo specimens | Jecklin 2024, arXiv 2401.16027 | almost no sample above surface score 0.6 from bone-only renders; 0.62, F1 0.84 with Pix2Pix translation (estimated origin) | 0.63, F1 0.84 after fine-tuning on real | 0.69, F1 0.86 | translation equals fine-tuning |
| T1 to L5 vertebra segmentation | Inigo 2025 (Spine-DART), arXiv 2512.05803 | Dice 0.82 on 35 real Loop-X frames of one cadaver | n/a | Dice 0.89 | about 0.07 Dice lost from renders to real |
| Structures by text prompt, about 3 million renders of 1,621 CTs | Killeen (FluoroSAM), arXiv 2403.08059 v3 | Dice 0.60 text only, 0.69 two points, 0.77 eight points, over 1,741 masks of a cadaver from mid-femur to T2 | n/a | 0.59, 0.70, 0.79 | pooled over structures; v2 printed 0.26 overall text only against 0.43 on renders; levels pooled at 0.04 Dice in arXiv 2412.08020 |
| Surgical phase from renders | Killeen 2023 (Pelphix), MICCAI | 67.6 % mean, the view class 51 % | n/a | 93.8 % | the largest losses are on categories the simulation defined by hand |
| Bone and organs on topograms, DRRs translated | Zhang 2018 (TD-GAN), MICCAI | bone Dice 0.401 untranslated, 0.835 translated | 0.871 supervised | n/a | unpaired translation recovers most of the gap |

Two lessons for P. First, recall falls before error does (Grimm), so the per-level naming rate and
the rate of missed bodies are both reported, not the error alone. Second, the largest failures that
remain after physics and translation are label-definition failures (SyntheX's COVID lesions,
Pelphix's view class): the renderer gives the class it was told to give, and a level name is such a
label, so the renders must carry the counting conventions of the real readers, transitional anatomy
included. A vertebra-specific appearance gap, about 0.07 Dice or two to three times in millimetres,
also remains (Jaganathan, Spine-DART, Jecklin).

## 3. Naming levels across the whole spine

| Work | Data | Region numbers | Reading |
| --- | --- | --- | --- |
| LevelCheck, Lo 2015, Spine 40(8):E476 | 20 thoracolumbar surgery patients, preoperative CT and one intraoperative radiograph, 10,000 trials | 100 % at 25.7 s, 99.3 % at 7.1 s; failures are whole-level shifts | registration with the patient's CT is the gold method; cervical not tested |
| De Silva 2016, Spine; Manbachi 2018, Ann Biomed Eng 46(10):1548 | 398 radiographs, cervical to lumbar; 62 difficult cases | median localisation error 30.4 % unassisted, 2.4 % with LevelCheck | most useful where the sacrum or the twelfth rib is absent or hidden |
| Huang 2022, Comput Methods Programs Biomed 227:107222 (Uneri, Siewerdsen) | images synthesised from 297 CTs; tested on 50 AP and 50 lateral real Long-Film images (an extended-field tomographic mode) of 13 cadavers | 88.3 % labelling accuracy on both views, F1 above 96 %, 3.3 mm; the abstract also prints 88.9 % with instrumentation and 91.2 % without, which cannot both partition the same 88.3 %, so they are another measure or subset the closed full text would name | render-trained labelling transfers to real intraoperative images over a long field; the regions are not in the abstract |
| VertXNet, Chen 2024, Sci Rep (arXiv 2207.05476) | 293 cervical and 219 lumbar laterals, trained together | Dice C2 to C6 0.90 to 0.91, C7 0.88, T1 0.52; T11 0.76, L1 to L5 0.85 to 0.87, S1 0.82; tested without retraining on PREVENT and NHANES II at 0.88 to 0.90 | counts from a detected C2 or S1; the bodies at the edge of the field fail; it moves across datasets, never across regions |
| Payer 2020, VISAPP (VerSe 2019, CT) | 80 volumes, three-fold cross-validation | cervical 91.1 % (102 of 112), thoracic 89.0 % (388 of 436), lumbar 90.4 % (284 of 314) | the three Wilson intervals overlap, so no order between regions is read from it |
| Btrfly, Sekuboyina 2020, Radiol Artif Intell (CT reformations) | 302 plus 65 CTs | cervical 89.9 %, thoracic 86.2 %, lumbar 91.4 %; the rib cage in a plain projection costs about 5 points | the closest 3D analogue to a projection |
| VerSe challenge, Sekuboyina 2021, Med Image Anal | 374 CTs, 53 with T13 or L6 | best 94.3 % (2019), 96.6 % (2020) | a one-level shift is the dominant error; the hidden L6 of 2019 was missed by almost every entrant |
| Netherton 2025, Phys Imaging Radiat Oncol 34 (external) | 81 patients at two sites | cervical 69 % and 92 %, thoracic 87 % and 90 %, lumbar 92 % and 97 % | cervical is the weakest and varies most between sites |
| VERIDAH, Moeller 2026, arXiv 2601.14066 | 1,536 CTs (365 in test), 6,291 MRIs | 99.18 % of CT test subjects labelled perfectly, against 77.81 % for the baseline; thoracic count anomalies (T13, T11) found 96.3 % against 11.1 %, lumbar (L6, L4) 97.2 % against 61.1 % | without anomaly labels in training, about a quarter (22 to 26 %) of the thoracic anomalies on CT are found, against 53 to 64 % of the lumbar: the thoracic count is the harder one to learn unlabelled |
| Schwing et al. 2026, NeurIPS poster (CTSpinoPelvic1K) | 1,153 CT records of 802 patients, 33 with a transitional vertebra typed by Castellvi (the registry's 18 L6 spines are the lumbarised among them) | TotalSegmentator has no L6 and shifts labels by one on lumbarisation; junction Dice drops 29 points | the owner's own audit: transitional anatomy breaks the CT side too |
| Lee 2025, J Clin Med 14(21):7671 | 3,116 lateral lumbar films | transitional vertebra or not: accuracy 76.4 % (sensitivity 85.1 %, specificity 61.9 %), AUROC 0.84 | transitional anatomy is hard on film even as a yes or no |

What this says for P:

- Counting from an end works where an end is in view, and the end differs by region: S1 and the
  sacrum for the lumbar spine (COBRA, C-ArmLSpine, DeepFluoro show it), C2 and the dens for the
  cervical spine, the twelfth rib and the first rib for the thoracic spine. A namer learned on
  lumbosacral frames learned the sacral anchor. The thoracic anchors come from renders checked on the
  one real C-arm pair that reaches T2 (the digital twin's cadaver of arXiv 2412.08020); the cervical
  ones from renders checked on fluoroscopic cine with level-named tracks (Bournemouth, Maastricht),
  which carry no CT.
- The junctions are where the projection hides the anchor: the shoulders over C7 and T1 on a lateral
  frame, the heart and the rib cage over the mid-thoracic bodies, the mandible over C2, the iliac
  crests over L5 and S1. The rows for C7-T1, T12-L1 and L5-S1 are the ones to watch.
- Transitional anatomy (L6, T13, eleven or thirteen ribs, cervical ribs) is where every system fails,
  so the renders include it (CTSpinoPelvic1K's 33 transitional spines, VerSe's 53) and the counting
  prior (workstream A) carries its odds into the decoder.

## 4. What has not been shown, and what would be first

- No study trains a vertebra namer on one region of the spine on radiographs or fluoroscopy and tests
  it on another. In P that study is the ablation arm "no renders above L1"; the main design trains
  on whole-spine renders, as Huang did, so it is not itself a cross-region study.
- Naming levels on single real C-arm frames from renders alone, with no CT of the patient, has been
  done, and badly: FluoroSAM through the digital-twin paper scored 0.04 Dice on levels pooled, over a
  hemisphere of angles. What is open is a usable per-level rate on single C-arm spot frames at any
  angle, set against that 0.04, with the latency, and the measured transfer of a correction learned
  on one region to the others.
- No per-region identification rate on real cervical or thoracic C-arm fluoroscopy exists. One public
  set of real C-arm frames reaches above L1 with the specimen's CT: the digital twin's cadaver (80
  Loop-X frames, 46 viewpoints, mid-femur to T2, registered to 4 CTs), whose levels come from its CT
  once segmented; it is one specimen. No cervical C-arm set with a CT is public (the registry's
  record cervical_thoracic_intraop names the gap); cervical fluoroscopy with level-named tracks
  exists on request (Bournemouth, Maastricht).
- No AI paper measures the C7-T1 shoulder overlap, the mandible over C2 or the crests over L5-S1 on a
  fluoroscopic frame; they are documented clinically (swimmer's views, EOS against radiographs).

## 5. What the owner's workflow becomes, given the evidence

Issue #135's six steps map onto these, with the changes marked:

1. **Anatomy from renders of the whole spine (the issue's step 1).** Render every segmented CT at
   C-arm poses and at the field a spot frame has (collimated, a few bodies) as well as at long-film
   field, since the field decides whether an anchor is in view. Count the levels on every CT first,
   ribs included; include the transitional spines.
2. **The appearance correction learned where it can be measured (the issue's steps 2 and 3, the
   physics noise, the denoiser and the generative translation).** Render each CT at the frame's pose
   and set the render beside the real frame: the residual is the measured gap. Start on the poses that
   ship (DeepFluoro's H5 frames, Ljubljana's gold standard) and COBRA's solved geometry; C-ArmLSpine's
   poses are the project's own 2D/3D registrations, whose accuracy is not measured, so its residuals
   enter only above a pose-quality bar, since pose error would otherwise pass for the gap. Fit the
   physics noise first (quantum and electronic noise per device, as Hariharan 2019 fits it, plus blur,
   scatter and the vendor's processing), then the shape-preserving denoiser of workstream E, real to
   render-like, applied the same way to both sides, then the translation model. Which translation
   comes first is open: CUT or Pix2Pix are the measured ones on vertebrae, and Rapuri's comparison of
   diffusion with dense renders was in another regime (renders of each specimen's own CT), so it does
   not rank them for P.
3. **The correction applied upward and checked (the issue's step 3).** Apply it to cervical and
   thoracic renders. A translated render is kept when its geometry still matches the render's
   projected labels (a bone segmentation of the output, or its edges, set against the projected masks
   and corners), not when a detector trained on plain renders reads it the same, since such a
   detector misreads realistic images whatever their labels (section 2); the rejection rate is
   reported beside how realistic the kept images are.
4. **Training by region, with the anchor decided per frame (the issue's step 4, with an addition).**
   Train on lumbosacral real gold plus whole-spine renders. The addition is a head that says whether
   an anchor is in the frame and which, with the naming rate reported apart for frames with an anchor
   and frames without; for frames without, the context route (the sweep's earlier frames, or the
   counting prior) is measured separately. The issue's test list drops VinDr-SpineXR, which has no
   levels, and Spinal-AI2024, whose identities are synthetic (section 6).
5. **The junction rows (the issue's step 6):** C7-T1, T12-L1 and L5-S1, and the transitional spines.
6. **Reverse ablation by region (the issue's step 5),** one ingredient removed at a time: no
   translation, no denoiser, no physics noise, no renders above L1 (the cross-region arm), and, as
   additions, no transitional spines and no anchor head. The literature points to transitional
   anatomy (VERIDAH, on CT); the anchor head is this note's inference; neither has been measured on
   radiographs or fluoroscopy.

## 6. The tests, region by region, and the first measurements

| Region | Real test with level truth | Held? | What limits it |
| --- | --- | --- | --- |
| Cervical, film | CSXA 4,963 laterals with corner JSON, C1 to C7 | held | every person is in the v9 base, so it tests only once re-keyed out of training |
| Cervical and lumbar, film | NHANES II 543 landmarked films, and the VertXNet labels with identity and C2 and S1 | films held, labels not fetched | every person is in the v9 base, so it tests only once re-keyed out of training; the labels are a Zenodo fetch (record vertxnet_nhanes2_labels) |
| Cervical, film | Aariz 1,000 cephalograms, C2 to C4 by maturation stage | held (on the volume at the census of 2026-10-22, CC BY 4.0) | the top of the counter only |
| Cervical, fluoro | Bournemouth 252 flexion and extension sequences, level-named corner tracks C0 to T1 | tracks held, no pixels | the cine is a request, drafted and sent onward on 2026-10-21; no CT |
| Cervical, fluoro | Maastricht 112 lateral recordings, C0 to C7 per frame | no | a request, drafted, never sent; a data transfer agreement expected; no CT |
| Thoracic, film | AASCE 609 AP films, T1 to L5 corners in order | held | AP only, scoliotic spines |
| Thoracic and lumbar, fluoro | the digital twin's cadaver, 80 Loop-X frames registered to 4 CTs, mid-femur to T2 | the fetch word ipcai2025_robotic_xray_drive (#124) | one specimen; levels from its CT once segmented (workstream O) |
| Thoracic, film | MrOS 5,994 men and SOF about 9,700 women, lateral thoracic and lumbar films with grades per named level | no | a data request each, not sent |
| Thoracic, film | TVGH SpineXR, T1 to L5 labels per its description | no | behind a login on IEEE DataPort |
| Any, fluoro | the owner's own cervical and thoracic C-arm captures with the patient's CT | no | the only way to C-arm gold with the patient's CT above L1 beyond one cadaver |
| Not a test | Spinal-AI2024 20,000 films | held | synthetic identities, all on train, so it tests nothing about real frames |
| Not a test | VinDr-SpineXR 10,466 | held | lesion boxes, no levels |

Two arms, cheapest first, none run before the owner's word:

- **Arm A, the anchor question, with no new data and no correction:** train the namer on the
  lumbosacral real gold plus whole-spine renders, and score it on AASCE (thoracic, AP) and CSXA
  re-keyed out of training (cervical, lateral), each frame cropped to a spot field and left at its
  full field, per level with Wilson intervals. It costs the renders and one training. If naming
  holds on full fields and falls on spot fields, the anchor is the problem and step 4 is the work.
  These are films: they test the anatomy and the anchors, not the C-arm correction, and AASCE's
  scoliotic AP spines are their own confound.
- **Arm B, the correction:** steps 1 to 3 first (row P's 20 to 50 GPU-hours of rendering and
  translation, then one training per arm), with and without the correction. Its deciding tests are
  fluoroscopic: the digital twin's cadaver for the thoracic and lumbar C-arm frames, and the
  Bournemouth cine, once it arrives, for the cervical. The lumbar comparator is on the same modality
  (the cadaver's lumbar frames, C-ArmLSpine's held-out cases). A fall on these can still come from the
  device class the correction was fitted on (COBRA's kV projections are from radiotherapy linacs,
  C-ArmLSpine is one mobile C-arm, DeepFluoro a Cios Fusion), so the fit's devices are named beside
  every number.

## 7. What it means for the claims at the talk

- Huang 2022 already labelled vertebrae on real intraoperative Long-Film images from renders alone
  at 88.3 %, and FluoroSAM named levels on single real C-arm frames from renders at 0.04 Dice, so
  neither "first to learn level naming from renders" nor "first to try it on C-arm frames" is open.
  What is open is a usable per-level rate on single C-arm spot frames at any angle, with no CT of the
  patient, with the latency on screen, set against FluoroSAM's 0.04; and the measured transfer of a
  render-to-real correction learned on one region to the others.
- Every cervical or thoracic number shown before a real C-arm test above L1 is scored is a number on
  films, and says so on the slide.

## 8. Sources and how they were checked

The numbers above were read from the papers by two literature searches on 2026-10-22. The nine
that carry the argument (Huang 2022, SyntheX, Jaganathan 2023, Jecklin 2024, VertXNet, Payer 2020,
Spine-DART, Rapuri 2026, VERIDAH) were read a second time from their primary sources by independent
checks (8.1); FluoroSAM's v3 numbers match the reading of the thread "Benchmark and priors issues";
and two adversarial reviewers then read the note against the repository's records and the searches
(8.2).

### 8.1 The second reading

- Huang 2022: every number in the abstract holds (297 CTs, 50 AP and 50 lateral, 13 cadavers,
  88.3 %, F1 above 96 %, 3.3 mm, 88.9 % and 91.2 % with and without instrumentation). The test images
  are Long-Film, an extended-field tomographic mode, not plain radiographs, and the abstract names
  no region; the full text is closed and was not read, so the first search's "whole spine" is dropped.
- SyntheX: the numbers are the published version's (Nature Machine Intelligence, Table 1, 360 px,
  six-fold testing on the 366 real frames); the arXiv preprint prints 6.29 mm and Dice 0.818 against
  8.15 mm and 0.759 for the same comparison. The paper gives the training set as 10,000 renders in
  its results and 18,000 in its methods.
- Jaganathan 2023: confirmed. The 3D data are clinical cone-beam CT of 55 patients, and "supervised
  on real" is a comparison method retrained on paired real X-rays.
- Jecklin 2024: the numbers are the estimated-origin rows (with the true origin 0.73 and 0.88 after
  translation); the real data are ex-vivo specimens; the C-arm comparison was one t-test of Siemens
  against Ziehm on six specimens, which the authors say proves no absence of difference.
- VertXNet: confirmed; the Sci Rep version adds tests on PREVENT and NHANES II without retraining.
- Payer 2020: confirmed, with the counts; CT, three-fold on the 80 training volumes; lumbar includes L6.
- Spine-DART: confirmed; the paper says both "over 150,000" and 161,000 renders.
- Rapuri 2026: confirmed; the render arm renders each specimen's own CT, the NCC threshold is a
  filter applied at evaluation, not a confidence a deployed model has, and at looser thresholds the
  order of the arms flips.
- VERIDAH: corrected; the results are on 365 test scans of the 1,536, the anomaly recalls are pooled
  per region, and "about a quarter without labels" holds for thoracic anomalies only.

### 8.2 The adversarial review

The review against the records corrected the tests table (NHANES II is in the v9 base like CSXA;
Aariz is held), and in the paired-sets table of docs/research/benchmarks-to-beat.md it corrected
the Geneva phantom (CT and gold poses ship), DeepFluoro (the vertebrae ship as one class),
C-ArmLSpine (its poses are registered, its level names automatic) and LUMOS (280 of 803 patients have
a CT). The review of the argument turned the device-not-anatomy claim into the hypothesis P tests,
replaced the label-preservation check by a geometric one, split the first measurement into a cheap
anchor arm and a costed correction arm with fluoroscopic deciding tests, corrected the region
ordering (cervical weakest at one site; Payer's within noise), restated what would be first against
FluoroSAM's 0.04, and mapped section 5 onto the issue's steps.

### 8.3 Papers

- Unberath et al., DeepDRR, MICCAI 2018 (arXiv 1803.08606); Unberath et al., IJCARS 14(9):1517-1528, 2019.
- Bier et al., MICCAI 2018, X-ray-transform invariant landmark detection.
- Gao et al., SyntheX, Nature Machine Intelligence 5:294-308, 2023 (arXiv 2206.06127).
- Grupp et al., IJCARS 2020 (arXiv 1911.07042): the real-trained ceiling on DeepFluoro, vertebrae Dice 0.74, sacrum 0.63.
- Grimm et al., IEEE TMI 2021 (arXiv 2011.07294).
- Zhang et al., TD-GAN, MICCAI 2018 (arXiv 1806.07201).
- Jaganathan et al., WACV 2023 (arXiv 2210.07611).
- Jecklin et al., arXiv 2401.16027, 2024.
- Inigo et al., Spine-DART, arXiv 2512.05803, 2025.
- Killeen et al., Pelphix, MICCAI 2023 (arXiv 2304.09285); FluoroSAM, arXiv 2403.08059; arXiv 2412.08020.
- Rapuri et al., arXiv 2606.21414, 2026.
- Prakash et al., ICCV workshops 2025 (arXiv 2411.18602); Chambon et al., RoentGen (arXiv 2211.12737); Peng et al., XraySyn, AAAI 2021 (arXiv 2012.02407).
- Hariharan et al., IJCARS 14(4):601-610, 2019 (low-dose fluoroscopy noise); Liu et al., arXiv 2208.14022; Jeon et al., arXiv 2411.00830.
- Lo et al., Spine 40(8):E476-E483, 2015; De Silva et al., Spine 2016; Manbachi et al., Ann Biomed Eng 46(10):1548-1557, 2018.
- Huang et al., Comput Methods Programs Biomed 227:107222, 2022.
- Chen et al., VertXNet, Sci Rep 2024 (arXiv 2207.05476).
- Abumoussa et al., Neurosurg Focus 54(6):E16, 2023; Siminski et al., AJNR 44(5):618-622, 2023.
- Payer et al., VISAPP 2020; Sekuboyina et al., Radiol Artif Intell 2020 (arXiv 1902.02205); Sekuboyina et al., Med Image Anal 2021 (arXiv 2001.09193).
- Netherton et al., Med Phys 47(11):5592-5608, 2020, and Phys Imaging Radiat Oncol 34, 2025.
- Deng et al., CTSpine1K (arXiv 2105.14711); Moeller et al., VERIDAH (arXiv 2601.14066); Elton et al. (arXiv 2001.10503).
- Schwing et al., NeurIPS 2026 poster, CT segmenters on transitional vertebrae.
- Lee et al., J Clin Med 14(21):7671, 2025; Noh et al., Bioengineering 11(5):481, 2024.
- Liebrand et al., Eur Spine J 2026 (doi 10.1007/s00586-026-09925-x), systematic review of level localisation.
