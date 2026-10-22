# From the lumbosacral gold to C2: prior art and feasibility

Source: the thread "Census, Any-View table and report fix", 2026-10-22, on the owner's ask of 23:08
UTC: "with cobra it should work in any position, because i dont think the rest of the spine is that
different from the lumbar spine, or at least i think you can learn how to extrapolate this ability
from the lumbosacral all the way to c2 using a combination of drr+physics noise; denoising; and
generative ai, please push creating this workflow to a task along with doijng deep research into its
prior art and feasaiblity". The task is issue #135, workstream P of docs/research/xr-from-3d/README.md.
The research is two literature searches run from the thread on 2026-10-22, one on training X-ray
models from renders of CT and the gap to real images, one on naming levels across the whole spine,
with the load-bearing numbers checked a second time against their papers (section 8 says which).
Confidential with the rest of this repository (docs/project.md): it describes methods.

## 1. The answer in short

- **The ingredients are published and work.** Renders of segmented CT with physics, many renderers and
  heavy appearance randomisation reach parity with real training on bone landmarks and segmentation
  of the pelvis (SyntheX), and unpaired translation or a small real fine-tune closes most of what is
  left on the lumbar spine (Jecklin 2024, Jaganathan 2023). A detector trained only on images
  synthesised from 297 CTs labelled vertebrae at 88.3 % on real intraoperative Long-Film images
  (an extended-field tomographic mode) of 13 cadavers (Huang 2022). So render-trained level
  labelling does transfer to real intraoperative images; which regions that test covered, the
  abstract does not say.
- **The extrapolation itself has never been shown.** No paper trains a level namer on one region of
  the spine on radiographs or fluoroscopy and tests it on another. Every whole-spine method, in CT,
  MRI or film, names levels the same way: it finds the chain, keeps the order, and counts from an
  end it can see (C2, S1, the last rib). The thoracic spine, farthest from both ends, is the weakest
  region in every per-region table, and a shift by one whole level is the dominant error everywhere.
- **What the owner's idea needs is a change of what is extrapolated.** The anatomy does not have to
  be extrapolated: the segmented CTs cover C1 to S1 (CTSpine1K, VerSe, TotalSegmentator, RSNA 2022
  cervical), so renders give exact cervical and thoracic truth. What has to travel upward from the
  lumbosacral pairs is the correction from render to real frame: the device's noise, blur, scatter,
  processing and the translation model. That is what the evidence leans towards (the gap is a
  property of the device and the image chain more than of the anatomy; Jecklin saw no clear
  difference between Siemens and Ziehm C-arms on six specimens, while warning that this does not
  prove there is none), and it is what the lumbosacral pairs can measure, since only there a real
  frame and a render of the same pose exist.
- **The hard part is the field of view, not the shape.** A C-arm spot frame of T7 shows neither C2
  nor S1, so a single frame cannot be counted from an end. Level naming on a mid-thoracic or
  mid-cervical spot frame needs a cue inside the frame (the ribs, the shoulders at C7-T1, the
  mandible and the dens at C2, the sacrum and the crests at L5-S1) or context outside it (a sweep,
  the previous frames, the counting prior of workstream A). This is where the claim "any position"
  is decided, and it has to be measured per region and per field of view, not assumed.
- **Feasibility grade:** the render, noise and translation pipeline is Published; the transfer of the
  appearance correction from lumbosacral pairs to cervical and thoracic frames is Inferred and
  plausible; level naming on a single collimated mid-thoracic frame is Inferred and doubtful without
  an anchor in the frame. The first measurement is cheap and decides the rest (section 6).

## 2. The gap from render to real, as measured

| Setting | Paper | Trained on renders, tested on real | Trained on real | Reading |
| --- | --- | --- | --- | --- |
| Pelvis landmarks, plain DRR | Unberath 2019, IJCARS 14(9):1517 | 78.2 mm | n/a | a plain render fails |
| Pelvis landmarks, full physics (poly-energetic, materials, scatter, noise) | Unberath 2019 | 24.7 mm (6.4 mm on renders) | n/a | physics alone leaves a gap of four times |
| Pelvis landmarks, physics and strong randomisation, 500 renders each of 20 CTs | Gao 2023 (SyntheX), Nat Mach Intell 5:294 (the published numbers; the arXiv preprint prints others) | 5.95 mm, Dice 0.86 | 6.46 mm, Dice 0.79 | parity or better, on 366 real frames of 6 cadavers |
| Pelvis landmarks, one renderer versus four and nine randomised stages | Grimm 2021, IEEE TMI | 11.7 mm, 98 to 100 % missed; then 6.4 mm, about 20 % missed | n/a | renderer diversity matters most; recall is the sensitive number |
| Pelvis landmarks, render of the specimen's own CT versus 2D diffusion conditioned on projected masks | Rapuri 2026, arXiv 2606.21414 | render 7.83 mm, diffusion 4.40 mm, on predictions whose heatmap matches the truth well (NCC above 0.6) | 4.89 mm | diffusion matches real on those; on looser matches the order flips, and renders sampled at 500 views each did best |
| Thoracic and lumbar vertebrae, 2D/3D registration | Jaganathan 2023, WACV, arXiv 2210.07611 | 3.78 mm, 10 % success plain; 2.97 mm, 66 % randomised; 1.83 mm, 90 % with translation (CUT) and feature alignment | 0.65 mm, 99.4 % | on vertebrae a gap of about three times stays |
| Lumbar vertebrae, 3D reconstruction from real fluoroscopy of ex-vivo specimens | Jecklin 2024, arXiv 2401.16027 | almost no sample above surface score 0.6 from bone-only renders; 0.62, F1 0.84 with Pix2Pix translation (estimated origin) | 0.63, F1 0.84 fine-tuned; 0.69, 0.86 on renders | translation equals fine-tuning; Siemens and Ziehm C-arms not clearly different on six specimens |
| T1 to L5 vertebra segmentation | Inigo 2025 (Spine-DART), arXiv 2512.05803 | Dice 0.82 on 35 real frames of one cadaver | Dice 0.89 on renders | about 0.07 Dice lost |
| Organ segmentation by text prompt, 3 million renders of 1,621 CTs | Killeen 2024/25 (FluoroSAM), arXiv 2403.08059 | Dice 0.60 text only, 0.77 with eight points, cadaver from mid-femur to T2 | 0.59 to 0.79 on renders | no per-vertebra number; nothing above T2 |
| Surgical phase from renders | Killeen 2023 (Pelphix), MICCAI | 67.6 % mean, the view class 51 % | 93.8 % on renders | the largest losses are on categories the simulation defined by hand |

Two lessons for P. First, recall falls before error does (Grimm), so the per-level naming rate and
the rate of missed bodies are both reported, not the error alone. Second, the failures that remain
after physics and translation are label-definition failures (SyntheX's COVID lesions, Pelphix's view
class): the renderer gives the class it was told to give. A level name is such a label, so the renders
must carry the counting conventions of the real readers, transitional anatomy included.

## 3. Naming levels across the whole spine

| Work | Data | Region numbers | Reading |
| --- | --- | --- | --- |
| LevelCheck, Lo 2015, Spine 40(8):E476 | 20 thoracolumbar surgery patients, preoperative CT and one intraoperative radiograph, 10,000 trials | 100 % at 25.7 s, 99.3 % at 7.1 s; failures are whole-level shifts | registration with the patient's CT is the gold method; cervical not tested |
| De Silva 2016, Spine; Manbachi 2018, Ann Biomed Eng 46(10):1548 | 398 radiographs, cervical to lumbar; 62 difficult cases | median localisation error 30.4 % unassisted, 2.4 % with LevelCheck | most useful where the sacrum or the twelfth rib is absent or hidden |
| Huang 2022, Comput Methods Programs Biomed 227:107222 (Uneri, Siewerdsen) | images synthesised from 297 CTs; tested on 50 AP and 50 lateral real Long-Film images (an extended-field tomographic mode) of 13 cadavers | 88.3 % labelling accuracy on both views, F1 above 96 %, 3.3 mm; 88.9 % with instrumentation, 91.2 % without | the nearest prior art to P: render-trained labelling transfers to real intraoperative images over a long field; the regions are not in the abstract, the full text is closed |
| VertXNet, Chen 2024, Sci Rep (arXiv 2207.05476) | 293 cervical and 219 lumbar laterals, trained together | Dice C2 to C6 0.90 to 0.91, C7 0.88, T1 0.52; T11 0.76, L1 to L5 0.85 to 0.87, S1 0.82; tested without retraining on PREVENT and NHANES II at 0.88 to 0.90 | counts from a detected C2 or S1; the bodies at the edge of the field fail; it moves across datasets, never across regions |
| Payer 2020, VISAPP (VerSe 2019, CT) | 80 volumes, three-fold cross-validation | cervical 91.1 % (102 of 112), thoracic 89.0 % (388 of 436), lumbar 90.4 % (284 of 314) | thoracic lowest, farthest from both ends |
| Btrfly, Sekuboyina 2020, Radiol Artif Intell (CT reformations) | 302 plus 65 CTs | cervical 89.9 %, thoracic 86.2 %, lumbar 91.4 %; the rib cage in a plain projection costs about 5 points | the closest 3D analogue to a projection |
| VerSe challenge, Sekuboyina 2021, Med Image Anal | 374 CTs, 53 with T13 or L6 | best 94.3 % (2019), 96.6 % (2020) | a one-level shift is the dominant error; the hidden L6 of 2019 was missed by almost every entrant |
| Netherton 2025, Phys Imaging Radiat Oncol 34 (external) | 81 patients at two sites | cervical 69 % and 92 %, thoracic 87 % and 90 %, lumbar 92 % and 97 % | cervical varies most between sites |
| VERIDAH, Moeller 2026, arXiv 2601.14066 | 1,536 CTs (365 in test), 6,291 MRIs | 99.18 % of CT test subjects labelled perfectly, against 77.81 % for the baseline; thoracic count anomalies (T13, T11) found 96.3 % against 11.1 %, lumbar (L6, L4) 97.2 % against 61.1 % | without anomaly labels in training, only 22 to 26 % of the thoracic anomalies on CT are found, against 53 to 64 % of the lumbar: the thoracic count is the harder one to learn unlabelled |
| Schwing et al. 2026, NeurIPS poster (CTSpinoPelvic1K) | 1,153 CTs, 33 transitional | TotalSegmentator has no L6, shifts labels by one on lumbarisation; junction Dice drops 29 points | the owner's own audit: transitional anatomy breaks the CT side too |
| Lee 2025, J Clin Med 14(21):7671 | 3,116 lateral lumbar films | transitional vertebra found at 76.4 %, AUROC 0.84 | transitional anatomy is hard on film even as a yes or no |

What this says for P:

- Counting from an end works where an end is in view, and the end differs by region: S1 and the
  sacrum for the lumbar spine (COBRA, C-ArmLSpine, DeepFluoro show it), C2 and the dens for the
  cervical spine, the twelfth rib and the first rib for the thoracic spine. A namer learned on
  lumbosacral frames learned the sacral anchor; the cervical and thoracic anchors must come from
  renders, since no real gold pair shows them.
- The junctions are where the projection hides the anchor: the shoulders over C7 and T1 on a lateral
  frame, the heart and the rib cage over the mid-thoracic bodies, the mandible over C2, the iliac
  crests over L5 and S1. The plan's rows for C7-T1, T12-L1 and L5-S1 are the ones to watch.
- Transitional anatomy (L6, T13, eleven or thirteen ribs, cervical ribs) is where every system fails,
  so the renders must include it (CTSpinoPelvic1K's 18 L6 spines, VerSe's 53) and the counting prior
  (workstream A) must carry its odds into the decoder.

## 4. What has not been shown

- No train-on-one-region, test-on-another study exists for vertebrae on radiographs or fluoroscopy.
  This would be a first, in either direction of its result, and is worth reporting as such.
- No per-region identification rate on real cervical or thoracic C-arm fluoroscopy exists; no public
  set of real cervical or thoracic C-arm frames with named levels exists either (the registry's
  record cervical_thoracic_intraop names the gap).
- No AI paper measures the C7-T1 shoulder overlap, the mandible over C2 or the crests over L5-S1 on a
  fluoroscopic frame; they are documented clinically (swimmer's views, EOS against radiographs).
- No paper reports a per-vertebra sim-to-real Dice for level naming; FluoroSAM reports organs pooled
  and names levels at 0.04 Dice on its cadaver (docs/research/benchmarks-to-beat.md).

## 5. What the owner's workflow becomes, given the evidence

The order of issue #135 stays, with these changes of emphasis:

1. **Anatomy from renders of the whole spine, not by extrapolation.** Render every segmented CT at
   C-arm poses and at the field of view a spot frame has (collimated, a few bodies), not only at long-
   film field, since the field decides whether an anchor is in view. Include transitional spines.
2. **The appearance correction learned where it can be measured.** On COBRA, C-ArmLSpine and
   DeepFluoro, render the CT at the stored pose and set the render beside the real frame: the residual
   is the measured gap. Fit the physics noise (quantum and electronic noise per device, as Hariharan
   2019 fits it, plus blur, scatter and the vendor's processing) to that residual first, then train the
   translation model (a CUT or Pix2Pix style model first, a mask-conditioned diffusion model second,
   since Rapuri found diffusion no better than dense render sampling on hard cases) and the shape-
   preserving denoiser of workstream E, real to render-like, applied the same way to both sides.
3. **The correction applied upward and checked.** Apply it to cervical and thoracic renders; keep a
   translated render only when the level detector trained on plain renders still reads the same levels
   on it (the label-preservation check), so translation never changes the truth.
4. **The anchor decided per frame.** Train the namer with a head that says whether an anchor is in the
   frame and which, and report the naming rate apart for frames with an anchor and frames without; for
   frames without, add the context route (the sweep's earlier frames, or the counting prior) and
   measure it separately. This is the test of "any position" on the spine above L1.
5. **Reverse ablation by region**, one ingredient removed at a time: no translation, no denoiser, no
   physics noise, no renders above L1, no transitional spines, no anchor head. The last two rows are
   the ones the literature says matter most and have not been measured.

## 6. The tests, region by region, and what limits them

| Region | Real test with level truth | Held? | What limits it |
| --- | --- | --- | --- |
| Cervical, film | CSXA 4,963 laterals with corner JSON, C1 to C7 | held | every person is in the v9 base, so it tests only once re-keyed out of training |
| Cervical, film | NHANES II 543 landmarked films (cervical and lumbar), and the VertXNet labels with identity and C2 and S1 | films held, labels not fetched | the labels are a Zenodo fetch (record vertxnet_nhanes2_labels) |
| Cervical, film | Aariz 1,000 cephalograms, C2 to C4 by maturation stage | not fetched (figshare, CC BY 4.0) | the top of the counter only |
| Cervical, fluoro | Bournemouth 252 flexion and extension sequences, level-named corner tracks C0 to T1 | tracks held, no pixels | the cine is a request, drafted, sent onward on 2026-10-21 |
| Cervical, fluoro | Maastricht 112 lateral recordings, C0 to C7 per frame | no | a request, drafted, never sent; a data transfer agreement expected |
| Thoracic, film | AASCE 608 AP films, T1 to L5 corners in order | held | AP only, scoliotic spines |
| Thoracic, film | MrOS 5,994 men and SOF about 9,700 women, lateral thoracic and lumbar films with grades per named level | no | a data request each, not sent |
| Thoracic, film | TVGH SpineXR, T1 to L5 labels per its description | no | behind a login on IEEE DataPort |
| Any, fluoro | the owner's own cervical and thoracic C-arm captures with the patient's CT | no | the only way to real C-arm gold above L1 |
| Not a test | Spinal-AI2024 20,000 films | held | synthetic identities, so it tests nothing about real frames |
| Not a test | VinDr-SpineXR 10,466 | held | lesion boxes, no levels |

The first measurement that decides the rest needs nothing new: train the level namer on the
lumbosacral real gold plus whole-spine renders (with and without the correction), and score it on
AASCE (thoracic, AP) and on CSXA re-keyed out of training (cervical, lateral), per level with Wilson
intervals, each frame cropped to a spot field and to its full field. If cervical and thoracic naming
holds near the lumbar rate on full fields and falls on spot fields, the anchor is the problem and
step 4 is the work; if it falls on both, the correction does not travel and step 2 is the work. No
job of it runs before the owner's word.

## 7. What it means for the claims at the talk

- Huang 2022 already labelled vertebrae on real intraoperative Long-Film images from renders alone
  at 88.3 %, so a claim of "first to learn level naming from renders" is not open. What stays open is: single spot
  frames from a C-arm at any angle, with no CT of the patient, with the latency on screen, and the
  measured transfer of a render-to-real correction learned on one region to the others.
- Every cervical or thoracic number shown before a real C-arm gold set above L1 exists is a number on
  films, and says so on the slide.

## 8. Sources and how they were checked

The numbers above were read from the papers by two literature searches on 2026-10-22, and the nine
that carry the argument (Huang 2022, SyntheX, Jaganathan 2023, Jecklin 2024, VertXNet, Payer 2020,
Spine-DART, Rapuri 2026, VERIDAH) were read a second time from their primary sources by independent
checks; section 8.1 lists what that second reading changed.

### 8.1 The second reading

- Huang 2022: every number holds (297 CTs, 50 AP and 50 lateral, 13 cadavers, 88.3 %, F1 above
  96 %, 3.3 mm). The test images are Long-Film, an extended-field tomographic mode, not plain
  radiographs, and the abstract names no region; the full text is closed and was not read, so the
  first search's "whole spine" is dropped.
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
- Rapuri 2026: confirmed; the render arm renders each specimen's own CT, and the NCC threshold is a
  filter applied at evaluation, not a confidence a deployed model has.
- VERIDAH: corrected; the results are on 365 test scans of the 1,536, the anomaly recalls are pooled
  per region, and the "quarter to a third without labels" holds for thoracic anomalies only.

### 8.2 Papers

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
