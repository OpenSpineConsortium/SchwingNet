# Benchmarks to beat: FluoroSAM, the language-promptable digital twin and contour registration

Source: the thread "Census, Any-View table and report fix", 2026-10-22, on the owner's asks of 21:25
UTC ("these two papers seem to be the people to beat ... If I cant beat them through gradual reverse
ablation, then im not a computer scientist") and 21:30 UTC ("evaluate fluorosam for how its adjusting
for the noise between synthetics and real fluro ... i just want to know what the benchmarks ill have to
beat are so i can show how much better I am, what new capabilities im giving for the first time,
whether i work better on real fluoro xrays, can i predict from any angle, can i classify?"). Read from
arXiv 2403.08059v2 (FluoroSAM), arXiv 2412.08020 (the digital twin), arXiv 2506.13292v2 (contour
registration), the FluoroSeg and FluoroSAM repositories (arcadelab, cloned 2026-10-22) and the
registration project page. Confidential with the rest of this repository: it names what the product
does better, so nothing of it leaves before the provisional is filed.

Extended on 2026-10-23 by the thread "Benchmarks to beat table" (issue #130, from the checkpoint of
2026-10-22 23:50 UTC on that issue): the comparator rows of section 2 with their grades and the
evaluation-page number each is compared with, the digital twin's per-region Dice from Table 1 of arXiv
2412.08020, the Flepp record and its licence from the Zenodo page, which record the grid's Zenodo token
serves (section 6), what each version of the FluoroSAM paper says of its renderer (section 3), both
directions of the ablation ladder (section 4) and VertebralDiffusion (section 8). Grades are those of
docs/research/xr-from-3d/README.md section 3: Measured is this project's own record, Published is
shown elsewhere in the source named, Inferred is reasoned here and not shown. What was read for the
revision is section 9.

## 1. The three papers in numbers

### FluoroSAM (Killeen et al., MICCAI 2025; arXiv 2403.08059)

A Segment-Anything variant trained from scratch on synthetic X-rays with text, point and box prompts.

- Training data: FluoroSeg, 1,672,969 DRRs in the paper (the released set has 2,953,257 from 1,621
  CTs: 519 head and neck, 573 torso, 529 lower extremity), rendered by a modified DeepDRR from 1,699
  CTs (747 New Mexico Decedent Image Database, 108 TotalSegmentator, 844 internal torso scans), with
  TotalSegmentator V2 masks (117 classes plus 11 appendicular bones, 128 organ masks) and 464 tool
  meshes, up to 15 tools a view; the principal ray sampled on a hemisphere short of 25 degrees from
  the S/I axis; detector 180 to 500 mm and source-to-detector 700 to 1200 mm (a mini C-arm in 10 % of
  views). 448 x 448 pixels.
- Real test: 464 fluoroscopic images of one cadaveric lower torso on a Brainlab Loop-X, angles plus
  or minus 30 degrees cranial-caudal and plus or minus 90 orbital, truth by 2D/3D registration to the
  CBCT and projection of TotalSegmentator's 3D masks; public chest X-rays for the lung.
- Numbers: synthetic test (47,190 images) text only 0.43 +/- 0.26 Dice, text and more prompts 0.85
  +/- 0.11, two points 0.68 (MedSAM 0.60, SAM 0.58); the cadaver, text only, hard tissue 0.39, overall
  0.26; with points, hard tissue 0.90 +/- 0.15 (the abstract says 0.79), soft tissue 0.73 +/- 0.15;
  MedSAM with a box 0.51 +/- 0.21; the whole lung on chest films zero-shot 0.52 text only, 0.90 with
  points. No per-vertebra table.
- Those numbers are arXiv v2's. The v3 of June 2025 reports others, read in full by the thread
  "Benchmark and priors issues" on 2026-10-22 and matching this programme's own second reading
  (docs/research/lumbosacral-to-cervical-extrapolation.md): on the real cadaver, over 1,741 masks,
  Dice 0.60 text only, 0.69 with two points or a box, 0.77 with eight points; on synthetic
  validation 0.59, 0.70, 0.79; FluoroSeg 2,953,257 DRRs from 1,621 CTs. A comparison on the talk
  quotes v3.
- Released: the code, the weights (2.5 GB on Google Drive) and FluoroSeg (2.65 TB on Hugging Face,
  gated, CC BY-NC-SA 4.0; the owner accepted its terms on 2026-10-22). The 464-frame cadaver set of
  v2 is not released under that name; the digital twin's cadaver, below, is.

### The language-promptable digital twin (Killeen et al., arXiv 2412.08020, December 2024)

Voice control of a robotic C-arm (Loop-X) through GPT-4o and Whisper, with FluoroSAM's masks from
several views stacked into a sparse 3D "digital twin" of one cadaveric torso (80 images, 46 unique
viewpoints; truth from four stitched navigated CBCTs segmented by TotalSegmentator).

- End-to-end voice success 83.54 % over 158 prompts (visualisation 82.6 %, collimation 60.7 %,
  viewfinding 83.3 %).
- FluoroSAM on this cadaver, text prompts only (Published; read on 2026-10-23 from arXiv 2412.08020v1):
  Table 1, "FluoroSAM Single-image Performance" in Appendix A, gives Dice and centroid error per
  prompt: vertebrae as one class 0.78 +/- 0.15, lumbar vertebrae 0.72 +/- 0.18, thoracic vertebrae
  0.64 +/- 0.20; the groups upper lumbar 0.42, lower lumbar 0.68, upper thoracic 0.35, lower thoracic
  0.27, sacrum 0.35 and ribs 0.54 (means; the table prints each spread); the single levels it lists,
  L3 0.21, L4 0.16 and L5 0.25; and over all its rows an average of 0.47 +/- 0.25 Dice and 58.87 +/-
  50.29 mm centroid error (41 rows, where the text says the top 40 prompts). The 0.04 Dice for similar
  vertebral levels and 0.02 for individual rib bones are Section 4.1's text, not rows of the table: so
  "ribs 0.02" is one rib told from its neighbours while the ribs as one class score 0.54, and the
  per-level number the capability table quotes is the text's 0.04, beside the table's 0.16 to 0.25 for
  L3 to L5 by name.
- The twin localises 35 structures within 51.68 +/- 30.84 mm from random orientations; collimation
  boxes precision 0.26, recall 0.70.
- Released: the cadaver set, a Google Drive zip linked from the README of
  github.com/benjamindkilleen/IPCAI-language-digital-twin (the repository is MIT; the data's own
  terms are to read on unzip): 80 single-shot X-rays, 46 from unique viewpoints, of a torso from the
  mid-femur to T2, acquired with navigation and registered to 4 CTs included in the archive. The
  fetch word ipcai2025_robotic_xray_drive (#124) brings it to the grid. No baseline compared.
  Correction of 2026-10-22: this line said "Nothing released" until the thread "Benchmark and
  priors issues" found the README.

### Multi-view X-ray/CT registration by bone substructure contours (Flepp et al., arXiv 2506.13292)

Two calibrated X-rays of the distal femur, a fiducial with 16 metal beads for the pose, an nnU-Net
that draws three substructure contours (diaphysis, medial and lateral condyle) trained on
patient-specific DRRs, and a contour ICP that matches within a substructure only.

- Real test: 5 cadaveric specimens, ten views each at about 9 degrees apart, Siemens Fluorospot, CT
  at 0.2 mm slices.
- Numbers: mean reprojection distance 0.67 mm (ImFusion, manual four-point start, 5.35 mm; Zhang's
  silhouette ICP 4.03 mm); sub-millimetre in 96.1 % of 30 runs, 92 % of 50 random starts (plus or
  minus 50 mm, plus or minus 180 degrees), 100 % with the restart; contours at 0.59 mm Chamfer.
- Released: the dataset on Zenodo 15753063 (the record read on 2026-10-23): open access with no login,
  one file, dataset_ipcai.zip, 6.7 GB, md5 cc8bf3e445495d2deb6d50dd058dc977, under the "Research-Only
  Dataset License" (redistribution for academic research only, commercial use by written permission,
  Swiss law; copyright 2025 Roman Flepp, University Children's Hospital Zurich), described there as
  "Paired X-Ray and CT dataset including real calibrated X-ray images and 5 CT scans" with no anatomy
  named, and its DOI line pointing at the paper (10.1007/s11548-025-03391-4). The paper names the
  anatomy: 5 cadaveric distal femur specimens, 10 views each, 50 X-rays (arXiv 2506.13292v2 has
  Sections 1 to 5 and Appendices A to F; the owner's anchor #S7.F8 is Appendix B's Figure 8, the
  point-matching figure, and there is no Section 7). The code is by request from github.com/rflepp
  under a non-commercial licence, with a patent pending, EP25168706.7, as the first reading recorded
  from the project page; the paper's text carries no Zenodo, licence or patent statement. The femur,
  not the spine. On the grid: at /rs/rs_grp_oschome/go2432/data/ipcai2025_xray_ct/raw and still zipped
  (4 files, 6.2 GB, the sample index of 2026-10-22, docs/research/data-manifest/MANIFEST.md); its
  record is data/sources/ipcai2025_xray_ct.json, corrected on 2026-10-23 from "pelvis or spine, to
  confirm" to the femur; its registry entry, its line in grid/fetch-xray.json and its bank recipe were
  removed the same day, since no spine region fits it, it is fetched and it enters no shard.

## 2. What each of them cannot do, which is the opening

| Capability | FluoroSAM / the twin | Contour registration | SchwingNet's claim |
| --- | --- | --- | --- |
| Classify, first sense: name each vertebra's level on a real fluoroscopic frame (vertebral classification, the goal's phrase in docs/project.md) | no: 0.04 Dice on levels, the paper's own number (Section 4.1 of arXiv 2412.08020) | no: it has no levels | yes, the product; measured per level on held-out real frames, the evaluation page's rows |
| Work without a CT of the patient | yes for masks, no for the twin's geometry (CBCT truth) | no: needs the preoperative CT and a fiducial | yes, CT-free at the podium |
| Any angle | trained on a hemisphere; tested at plus or minus 30 and 90 on one device | two views 45 degrees apart or more | the per-angle curve on real sweeps (C-ArmLSpine, COBRA) is the test |
| Classify, second sense: the transitional stratum (T13, L6) and the anomaly calls | no | no | the screener (H, #64) with the counting prior from CT as its prior (F, #62; A); the evaluation page's transitional row, and a per-image call with its interval once H exists |
| Real fluoroscopy | trained on renders only, tested on one cadaver and one device | trained on renders of the same specimen, tested on the specimen | trained on real films and frames plus renders, tested leave-one-device-out |
| Latency | not reported | nnU-Net at 18 GB GPU, ICP to converge; no number | the 97 ms budget, measured |

So the first-time claims the talk can make, each with its measurement: level naming on real frames
with no CT, at any angle, with latency; and anomaly and transitional-anatomy classification from a
single frame. Segmentation of bone as one class is not a claim to make against FluoroSAM, which does
it well (vertebrae as one class 0.78 text only on the digital twin's cadaver; 0.60 to 0.77 over all
structures in v3); the comparison is on levels, where it scores 0.04.

### The comparator rows

Every published method with a number, what it reads at test, where its number comes from with its
grade, and the number of this repository it is compared with: a stratum of the evaluation page
(docs/research/evaluation/README.md, written by tools/eval_page.py from the results.json that
tools/evaluate.py writes: naming accuracy as correct/n with its Wilson interval and the person count,
for all levels, per level, per source and for the transitional stratum) where the data are held, else
the spine-datasets task that brings the data. A row read in the abstract alone says so: its number is
quoted, its regions and conditions are not known. The rows for Huang 2022, LevelCheck, I-STAR, VerSe,
Payer and Btrfly are those of docs/research/lumbosacral-to-cervical-extrapolation.md (section 2 and
its second reading, 8.1); the rest were read for this revision (section 9).

| Row | What it reads at test | Data and test set | Number (grade; source) | The same number here |
| --- | --- | --- | --- | --- |
| FluoroSAM v2 (arXiv 2403.08059v2) | one real frame and a text, point or box prompt; renders alone in training | 464 Loop-X frames of one cadaveric lower torso | hard tissue Dice 0.39 text only, 0.90 +/- 0.15 with points; overall 0.26 text only (Published; v2's results) | #132: its masks' bounding boxes scored as boxes by tools/evaluate.py on the held C-ArmLSpine test persons, as the all-levels and per-level rows; the weights wait on the owner's word (section 6) |
| FluoroSAM v3 (arXiv 2403.08059v3) | the same | the real cadaver, 1,741 masks; synthetic validation | Dice 0.60 text only, 0.69 with two points or a box, 0.77 with eight points; synthetic 0.59, 0.70, 0.79 (Published; v3's results) | the same row of #132; v3 is the version a talk quotes |
| FluoroSAM in the digital twin (arXiv 2412.08020) | one real frame and a text prompt | 80 Loop-X frames of one torso to T2 | vertebrae 0.78 +/- 0.15, lumbar 0.72 +/- 0.18, thoracic 0.64 +/- 0.20; one level 0.04 (Published; Table 1 and Section 4.1) | the same frames: naming accuracy per level on the twin's cadaver as a source row, once OpenSpineConsortium/spine-datasets#170 brings the archive and #127 verifies its masks; its thoracic frames are #135's row |
| Huang 2022, Comput Methods Programs Biomed 227:107222 | one real image, no CT; renders of 297 CTs in training | 50 AP and 50 lateral Long-Film images of 13 cadavers | 88.3 % labelling accuracy on both views, F1 above 96 %, 3.3 mm; 88.9 % with and 91.2 % without instrumentation (Published; the abstract alone, the full text closed, regions not stated) | the all-levels row on held real frames, AP and lateral apart; tools/evaluate.py tallies no view stratum yet, a follow-up for the ladder's first rung (section 4) |
| Ahmad, Ali and Jung 2025, HSI 2025 (doi 10.1109/HSI66212.2025.11142408) | multi-view DRRs of VerSe 2019 | not stated in the abstract | no number in the abstract and no real-image test visible (Published method; the abstract alone) | none until read in full; if it holds a real-image number, the AP-and-lateral pair stratum above |
| LevelCheck, Lo 2015, Spine 40(8):E476 | one radiograph registered to the patient's own CT | 20 thoracolumbar patients, 10,000 trials | 100 % at 25.7 s, 99.3 % at 7.1 s (Published) | the all-levels row on C-ArmLSpine, whose cases carry a CBCT that is never read at inference; its seconds against task #13's p95 under 97 ms |
| I-STAR 398 radiographs (De Silva 2016, Spine; Manbachi 2018, Ann Biomed Eng 46(10):1548) | the surgeon reads the radiograph, with and without LevelCheck | 398 radiographs, cervical to lumbar, 62 difficult | median localisation error 30.4 % unassisted, 2.4 % with LevelCheck (Published) | one minus the all-levels accuracy; the unassisted figure is the reader's row, the one a frame-level method is set beside |
| VerSe (Sekuboyina 2021, Med Image Anal); Payer 2020, VISAPP; Btrfly (Sekuboyina 2020, Radiol Artif Intell) | CT volumes, a 3D labeller | 374 CTs; 80 CTs three-fold; 302 plus 65 CTs | identification 94.3 % (2019) and 96.6 % (2020); Payer cervical 91.1 %, thoracic 89.0 %, lumbar 90.4 %; Btrfly 89.9 %, 86.2 %, 91.4 % (Published; CT, not X-ray) | no row of the evaluation page: the ceiling of the 3D side that the counting prior (A, #57) and the renders' truth stand on; never filed as an X-ray number |
| FCN and CRF, Sekuboyina and others, ISBI 2023 (doi 10.1109/ISBI53787.2023.10230520; arXiv 2108.06554) | CT volumes | three benchmark CT sets, not named in the abstract | identification rate above 97 %, near 100 % with one interaction (Published; CT, the abstract alone) | the same: CT, no page row; its anatomical-prior CRF is the model for A (docs/research/ct-priors-for-2d-detection.md) |
| SchwingNet version 1, the evaluation page (#12) | one real frame, no CT, no prompt | the frozen test persons, read once at the version boundary | the row that moves: the two runs recorded so far are the synthetic-bank dry run (cd37124c487d, test 430/431 = 0.998, 5 synthetic persons) and its predecessor, which measure the workflow and not SchwingNet (Measured; the workflow only) | the page itself; every rung of section 4 is one more row |
| The reported stack, context only (spine-program 01_carm_level_detection, 01/STATUS.md; docs/research/demo-plan.md) | one real frame, no CT | C-ArmLSpine, held out, zero-shot | lateral naming 595/617 = 96.4 % [92.3, 98.4], fine-tuned 97.4 %; AP naming 276/631 = 43.7 %; detection recall at 0.74 231/287 = 80.5 % [74.1, 86.8]; a renders-only detector 0.3 % at 0.74 and 31.7 % at 0.25; no frame of the device 7.0 % (Measured by the reported stack) | context beside version 1, which docs/project.md makes the baseline; the latency budget is task #13's p95 under 97 ms |

Read against the owner's three questions. On real fluoroscopy with no CT, the published level-naming
numbers are Huang's 88.3 % on Long-Film cadaver images and the reported stack's 96.4 % lateral and
43.7 % AP on C-ArmLSpine, on different test sets, so neither beats the other until one method runs on
the other's frames, and Huang's code is closed; FluoroSAM's 0.04 per level is a Dice on one cadaver,
not an accuracy, and meets ours only through #132 on the same frames. Any angle has no published
level-naming number at all: no row above reports a per-angle curve (Inferred from the rows). Classify
in the first sense is version 1's own row; in the second sense no row exists anywhere yet.

## 3. How FluoroSAM handles the gap between renders and real fluoroscopy

Read from fluoroseg/src/fluoroseg/alb/build_aug.py and the paper (the code read again on 2026-10-23,
build_aug_dcm and build_aug_cxr, the list below unchanged). It is intensity-space domain
randomisation and nothing else:

1. Every render is taken through the negative log, inverted, and windowed by a k-means mixture window
   (the window's bounds from the intensity clusters, so the bone band fills the range), as the real
   images are windowed at inference to the 99th percentile.
2. Then, at random, an inversion with probability 0.5, and one of: CLAHE (clip 4 to 6, tiles 8 x 12),
   or two to four of {Gaussian, motion or median blur; sharpen or emboss; contrast scaled by -2 to 2;
   a Gaussian non-uniform contrast (alpha 0.6 to 1.4, sigma 0.1 to 0.5 of the image); fog or
   drizzle; pixel dropout at 5 % or coarse dropout of 8 to 20 holes up to 64 px; channel shuffle}.
3. The renderer, and what is not stated (read on 2026-10-23): v1 of the paper calls it "a modified
   version of the DeepDRR simulator" and describes no modification, v2 the same as this note's first
   reading and the checkpoint on #130 recorded it, and v3 names no renderer, saying the DRRs come
   from "volumetric and mesh-based rendering" built on DeepDRR, SyntheX and Pelphix. No version says
   whether the run kept DeepDRR's noise and scatter models, and neither repository holds a render
   setting (fluorosam's utilities name only DeepDRR's data folder, through an environment variable),
   so whether noise and scatter were simulated is not stated, and nothing says they were turned off.
   There is no detector or image intensifier model, no vendor processing (unsharp masking, edge
   enhancement, LUTs), no grid lines, collimation edges or burnt-in text, no style transfer, and no
   fine-tuning on real images. v2 never quantifies the gap: its synthetic test gives 0.43 text-only
   Dice and the real cadaver 0.39 on hard tissue and 0.26 overall, on one device, the Loop-X. v3 puts
   the two side by side, synthetic validation 0.59, 0.70 and 0.79 against the real cadaver's 0.60,
   0.69 and 0.77, so over all 1,741 masks pooled the gap is within a few points, on that one cadaver
   and one device; per level it is not reported, and the 0.04 on levels in the digital twin says the
   randomisation carries bone as a class and not its count.

What this means for SchwingNet: the randomisation is the same layer 2 that xr-from-3d's workstream E
names (SyntheX's recipe), so it is table stakes, not a differentiator. The differentiators are layers
1, 3 and 4 there: reading each device's own LUTs from the header, a learned per-device intensity
correction, and shape as a target supervised by projected CT labels; and the measurement they lack,
leave-one-device-out accuracy on real frames across several devices (the record holds C-ArmLSpine,
FluoroCap's panels, DeepFluoro's vendor frames and COBRA's projections, each from different hardware).

## 4. The ablation ladder, in both directions

The owner's phrase is "gradual reverse ablation". #131 holds it in two readings, both on the same held
test persons and the same metrics, and keeps both until the owner says which he means: the leave-one-out
from the full system, written first here, and the build-up from the published baseline, one component
added per rung. Recommended (the checkpoint of 2026-10-22 on #130; Inferred): build up before the talk,
since each rung exists as soon as its component does, and leave one out once the full system exists,
since only then is there a whole to take parts from. Each rung is one run id, one commit and one result
file, with naming accuracy per level and per source and Wilson intervals on person-keyed n, detection
recall, the per-angle curve and task #13's latency; a rung that loses stays in the table as a loss;
nothing is tuned on a test person; and no rung runs before the owner's word and number for it.

### 4.1 Leave one out, from the full system

Start from the whole system and take one part away at a time, each run scored on the same held-out
real test persons, so every part's worth is a number on a slide and the comparison with the papers
above is one row of the same table:

1. Full system: real films and frames, renders with projected anchors, the counting prior, the
   device randomisation, the shape head.
2. Minus the shape head (xr-from-3d E layer 4).
3. Minus the per-device correction (E layer 3).
4. Minus the renders (C): real data only.
5. Minus the counting prior (A): the classifier alone.
6. Minus the real data: renders only, which is FluoroSAM's regime; its level Dice of 0.04 is the
   published floor for this row.
7. FluoroSAM itself on the same frames, prompted "L4 vertebra" and so on, scored by the same corner
   boxes (tools/evaluate.py reads a mask's bounding box as a box), with and without a point prompt.

Rows 1 to 6 are runs of tools/flow.py with switches, each with its run id, commit and result file,
and wait for the owner's word and number like every training. Row 7 needs the FluoroSAM weights
(2.5 GB from Google Drive, which the container cannot fetch) on the grid under models/, and a small
evaluator that turns its masks into boxes; no training.

### 4.2 Build up, from the published baseline

The rungs as #131 wrote them, each with the estimate docs/research/xr-from-3d/README.md section 3 gives
its workstream, so the owner can give the word and the number rung by rung.

Before the talk:

0. FluoroSAM's released weights on the test set (#132), scored as the paper scores (IoU, Dice) and as
   this repository scores (the level named, counted from the sacrum). Inference only, about an hour of
   GPU.
1. The level stage alone (version 1, tools/train.py and tools/evaluate.py): the version 1 run itself,
   within its 6 GPU-hour bound (docs/research/retraining-plan.md).
2. Plus the counting prior from CT at decode (A, #57): 1 to 2 CPU-hours, no training.
3. Plus the AP and oblique renders with projected anchors (C, #59): 1 to 3 GPU-hours to render, 6
   GPU-hours to fine-tune.
4. Plus device harmonisation layers 1 and 2 (E, #61): within E's 10 to 20 GPU-hours, the cheap half.

After the talk:

5. Plus the real frames labelled from COBRA's planning CTs (D, #60): 3 to 6 GPU-hours and 50 to 100
   CPU-hours.
6. Plus the gold per-pixel priors on real frames (#127, steps 4 and 5 of section 5): its own estimate
   once the registration route is chosen.
7. Plus the physics renderer (M, #69): 10 to 20 GPU-hours.

Rung 0 is row 7 of 4.1 and rung 1 is its row 5, the classifier on real data alone; the two ladders
meet at the full system, and row 6 of 4.1, renders only, has no build-up twin. The same test sets serve
both (#131): the C-ArmLSpine sweeps case134 and case39 and the held-out frames the record scores
(docs/research/demo-plan.md), the digital twin's cadaver once OpenSpineConsortium/spine-datasets#170
brings it, and COBRA's held-out cases for the per-angle curve; the Flepp femur set carries no spine
and serves only #127's registration check.

### 4.3 The results, as they come

| Rung | Direction | Component | Run id, commit | All levels | Transitional (T13, L6) | Detection recall | Per-angle | Latency p95 | Delta to the rung beside |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| none yet | | | | | | | | | |

A rung's row is filled from its results.json by the thread that ran it, never typed from memory, and
the evaluation page's row for the run is the same number.

## 5. The CT-and-X-ray pairs, their segmentations, and the plan

The owner's ask: find out whether the held CT-X-ray sets come with segmentations, plan ITK-SNAP and
AI-assisted segmentation with Dr Tech's verification into the priors work, and use registration code
for supervised pixel-to-pixel 3D-to-2D priors.

The owner's count on 2026-10-22 23:08 UTC is nine such sets once the pig set is counted, a tenth,
the digital twin's cadaver, was found the same evening, and the
goal restated then is: every paired CT-and-X-ray set is segmented, in ITK-SNAP with AI assistance
where no annotation exists and verified by Dr Tech, so that every real X-ray with a CT carries gold
per-pixel labels; and the annotated X-ray sets without a CT (BUU-LSPINE, NHANES II, CSXA, Aariz,
AASCE, VinDr-SpineXR; Spinal-AI2024 is synthetic and train-side only) then either train an independent
pseudolabeller or test the network, never both for one person. The ten, with what each ships:

| Set | Anatomy | X-rays | CT | Pose | Segmentation shipped | What ITK-SNAP must add |
| --- | --- | --- | --- | --- | --- | --- |
| C-ArmLSpine (held) | lumbar | 149 cases, 299 spot frames, 59,609 DICOM frames, 2 sweeps | CBCT per case | registered by the project (quality not measured) | level names on each CBCT from two automatic labellers (TotalSegmentator and SPINEPS/VERIDAH), agreed levels only, 814 of 910 bodies; the filter drops the thoracolumbar junction; no body masks | masks per body, L1 to S1, read by a person |
| COBRA (held, CC BY-NC) | lumbosacral, pelvis | 692 cases of raw CBCT projections, 375,618 | planning CT and the reconstruction | stored (geometry solved) | none for vertebrae | masks on the planning CT, L3 to S1 and the pelvis |
| DeepFluoro (held, CC BY-NC-SA) | pelvis, hip, low lumbar | 366 H5 frames, 2,659 vendor frames | 19 CT of 6 specimens | registered for the H5 frames | 7-class 3D and per-frame 2D labels, the vertebrae as one class and the upper sacrum | split the vertebrae class into named lumbar bodies |
| Ljubljana 2D/3D gold standard (held, ND) | L1 to L5 | 18 frames of one cadaver | CT | stored | the registration's gold standard; no body masks | five bodies, read-only licence: masks live beside, never redistributed |
| LUMOS (Zenodo 18173664, not fetched, 46.4 GB, CC BY-NC 4.0) | lumbar, diagnostic radiographs | 1,620 AP or lateral films of 803 patients, 280 of them with a CT | 280 non-contrast lumbar CTs | none: registration needed | to confirm on the record | masks on the 280 CTs, then registration to the films |
| Digital-twin cadaver (arXiv 2412.08020; a Drive zip, the fetch word ipcai2025_robotic_xray_drive since #124) | torso from mid-femur to T2: sacrum, lumbar and thoracic | 80 single-shot Loop-X frames, 46 unique viewpoints | 4 CTs covering the specimen, in the archive | registered by navigation to a fixed patient array | TotalSegmentator masks in the paper; whether they ship, to confirm on unzip | verify the lumbar and thoracic bodies; the one real C-arm pair above L1 |
| IPCAI 2025 paired set (Zenodo 15753063, research-only licence; fetched, still zipped, 6.2 GB on the volume) | femur | 50 calibrated X-rays | 5 CTs | stored | contour masks and bone models | nothing for the spine; a registration benchmark |
| Pig lower limb (IEEE DataPort 10.21227/gxpd-d998, 205 MB) | pig lower limb, no spine | 7 C-arm projections, with and without soft tissue | CT and two CBCT | matrices shipped | none | nothing for the spine; a registration benchmark (not the LevelCheck pig study the record named) |
| Veriserum (ETH, not fetched) | knee implant phantoms | about 110,000 dual-plane fluoroscopic frames | implant models, 200 frames manually registered | registered | implant poses | nothing for the spine; real flat-panel noise and metal at scale |
| Geneva hip phantom (held; D'Isidoro, Med Phys 2021) | pelvis | 116 frames of one phantom on an unseen device | phantom CT | gold-standard rigid transforms and projection matrix | two-labeller boxes through the pose | nothing; it stays the unseen-device test, never used to tune |

Real spine X-rays with a CT of the same subject are the first six. Five are lumbar or lumbosacral;
the digital twin's cadaver reaches T2, so it is the one real C-arm pair above L1 (one specimen, so a
test for issue #135's thoracic rows, never a training set). No cervical pair exists among them. Three of the last four pair
real frames with a CT or a model of something else (the femur, the pig limb, the knee implants),
and their use is the registration code; the Geneva phantom stays the unseen-device test: a
2D/3D registration tuned on the femur, the pig limb and the knee, where the truth pose is shipped,
is then run on LUMOS and the FluoroCap panels, where it is not. Two synthetic pairs stand beside the
nine: PENGWIN task 2 (50,000 renders of 100 pelvic CTs at real C-arm poses) and FluoroSeg
(2.65 TB of DRRs); FluoroSAM's 464-frame cadaver of v2 is not released under that name.

The plan, as workstream O of the xr-from-3d programme (issue #127 under #56); reaching the cervical and thoracic spine from this lumbosacral gold is workstream P (issue #135), whose prior art and feasibility is docs/research/lumbosacral-to-cervical-extrapolation.md:

1. Automatic first pass: TotalSegmentator (vertebrae and sacrum) on every planning CT and CBCT of
   C-ArmLSpine, COBRA, DeepFluoro, Ljubljana, LUMOS and the digital twin's cadaver, on the grid, as
   one array job; its masks
   are the AI assistance, and every set is done, not only the three held longest.
2. Correction by the owner in ITK-SNAP, case by case, with the level names from the C-ArmLSpine
   labels and the counting prior as the check; each corrected mask is a file under the case with the
   editor's name and the date in its sidecar, never in the mask.
3. Verification by Dr Tech: a second reader marks each case verified or returned, in a review sheet
   the repository tracks (tools/docx_review.py's pattern, or a CSV in the case folder); a body counts
   as gold only when verified. The two-reader agreement is the number reported, as C-ArmLSpine's
   814 of 910 is.
4. Projection: for C-ArmLSpine and COBRA the pose is stored, so the verified masks project through it
   to per-pixel label maps and corners on every real frame (xr-from-3d D, use 1). For DeepFluoro the
   released registrations give the pose; C-ArmLSpine's poses are the project's own registrations,
   whose accuracy is not measured, so its label maps carry a pose-quality flag.
5. Registration-supervised priors: where no pose is stored (FluoroCap panels, a new device's frames
   with a CT), the registration code gives it: a 2D/3D registration of the frame to the verified CT
   (DiffDRR or the contour method of section 1, which is patent-pending and non-commercial, so the
   open DiffDRR route first), and the registered pose renders the label map for that frame. That is
   the supervised pixel-to-pixel 3D-to-2D prior: for each real pixel, which body it lies on, from the
   CT, with no reader drawing on the X-ray. Its check is the reprojection distance on held-out
   landmarks, which the contour paper reports at 0.67 mm with a fiducial; without one, the project's
   own number is to be measured and is expected to be worse.
6. What it feeds: E layer 4's shape head (masks as targets on real frames), C's anchors on real
   frames, and the gold truth column of the Any-View plan, which until now held only lumbar and
   lumbosacral sets; the gold stays lumbar and lumbosacral until a cervical or thoracic pair is held.
7. The annotated X-rays without a CT then take one of two roles per person, chosen by the split and
   never both: the training of an independent pseudolabeller (a teacher that never sees the gold
   sets, whose labels on the unannotated films are checked against the gold), or the test of the
   network itself. Which role each set takes is decided when the gold count is known, since a set
   that tests must stay out of every training.

Before the talk: step 1 can run as soon as the owner gives the word and the number of jobs; steps 2
and 3 are the owner's and Dr Tech's hours, so their count of cases is theirs to set (every case is
not needed: 30 verified cases give a 95 % interval near plus or minus 10 points on a per-body rate
at 90 %, and C-ArmLSpine's 149 are the natural first set). Steps 4 to 6 are engineering after the
talk.

## 6. FluoroSeg and the FluoroSAM weights on the grid

FluoroSeg is 2.65 TB, gated on Hugging Face; the owner accepted the terms, and his token file
~/.hf/token.env is on the grid (2026-10-22). The grid fetch goes through the gated fetch word
(schwingnet-fetch-<id>) once a record names it. Its worth here is bounded: renders
of other people's CTs with TotalSegmentator masks, which the project already makes from its own CTs
(workstream C); the one use is pretraining the encoder on 3 million views with tools, and its licence
is non-commercial like COBRA's, the same lawyer's question. The owner said yes on 2026-10-22, and
its fetch word is hf_fluoroseg (#124), against the volume's 22 TB quota with 7.3 TB used.

The FluoroSAM weights (2.5 GB, Google Drive) are the one download row 7 needs; the container cannot
reach Google Drive, so the thread that holds the grid's Drive route ("Granted datasets onto the grid")
fetches them (fluorosam_model_weights.pth, about 1 GB) to the data root's fluorosam_weights_drive
through SchwingNet #124, as it fetched the Killeen archive.

Which record the grid's Zenodo token serves (grid/README.md and grid/run-platform-fetch.sh, read on
2026-10-23): MAGIC-CT, Zenodo 18389015 (OpenSpineConsortium/spine-datasets#7), whose data-use
application was approved on 2026-10-22; the grid word `fetch zenodo_magic_ct` (#124, pull request
#128) reads ZENODO_TOKEN from ~/.zenodo/token.env at mode 600, checks each of the record's 21 files by
md5 and stops at 50 GB, under CC BY 4.0 on the record and its non-commercial data use agreement. The
Flepp set needs no token: Zenodo 15753063 is open with no login, and it is already on the grid
(section 1). The FluoroSAM weights have their own fetch word, fluorosam_weights_drive
(fluorosam_model_weights.pth, 1,002,351,026 bytes), beside ipcai2025_robotic_xray_drive (the digital
twin's archive, 202410191.zip) and hf_fluoroseg (about 2.65 TB) in grid/run-platform-fetch.sh; each
waits for the owner's word and count.

## 7. Open questions for the owner

- The number of C-ArmLSpine cases he and Dr Tech will correct and verify before the talk: his answer
  of 2026-10-22 23:08 UTC was "maybe none maybe all of them", so the automatic first pass runs on
  every set and the count is set once its masks show how much correction they need.
- FluoroSeg: answered, yes (2026-10-22, the fetch word hf_fluoroseg); its licence question for a
  product stays the lawyer's, as COBRA's.
- Which direction the ablation ladder takes (#131, section 4): the recommendation is the build-up
  before the talk and the leave-one-out after it; both are kept until he says.
- His word and the count for the three fetches that wait (section 6): the digital twin's Drive archive
  (ipcai2025_robotic_xray_drive, OpenSpineConsortium/spine-datasets#170), FluoroSeg (hf_fluoroseg,
  about 2.65 TB) and the FluoroSAM weights (fluorosam_weights_drive).

## 8. VertebralDiffusion (github.com/arcadelab/VertebralDiffusion)

The owner's question of 2026-10-22, "your opinion on using this template for training or whether
something better exists, and how it could fit into my current workflow", answered on #70 (task N,
rare anatomy made in 3D) by the thread "Benchmark and priors issues" on 2026-10-22 23:43 UTC and
carried here as it stands:

- What it is: one commit (773fc5e, 2025-03-20, author Rapuris, message "changes") on the ashleve
  Lightning-Hydra template. The README is the template's, unchanged. There is no LICENSE, no paper, no
  weights, no data and no results. The code is a 3D VQ-GAN taken from TATS and a 3D DDPM taken from
  lucidrains' video-diffusion-pytorch, trained directly on voxels on 128^3 per-vertebra NIfTI crops of
  NMDID CTs, at hard-coded Johns Hopkins paths. The data module splits 20 / 10 / 70 with a shuffle that
  takes no seed of its own, so the split is fixed only when a run goes through one of the experiment
  configs, which set seed 12345 (train.yaml leaves it null). Its requirements file omits torchio,
  nibabel, monai and einops.
- As a training template: no. It is a student's unconditional 3D vertebra generator, not a workflow,
  and with no licence file it may not be copied. SchwingNet's workflow (tools/flow.py with RUN.json
  first and the ledger row last, the catalog versions, the person-keyed splits, beethoven-qa's gate)
  already does what a template would, and the repository's rule is that a new dependency is an issue
  first.
- Where the idea fits: task N (#70). A generator of 3D vertebral shapes is one way to make L6, T13 and
  a sacralised L5 in 3D, instead of editing segmented CTs by hand. If that route is taken, read the
  maintained implementations first: MONAI Generative Models (3D VQ-VAE, latent diffusion and
  ControlNet; Apache-2.0, to confirm) and Khader et al.'s medicaldiffusion (MIT, to confirm), run on
  this repository's own CTs. The generator's output is scored by the same renders and the same held
  real frames as everything else. Nothing is trained before the owner's word and count.

It is not a benchmark: it reports no number, so it has no row in section 2 (Inferred from the
repository as read; nothing Published).

## 9. Read for the revision of 2026-10-23

- arXiv 2412.08020v1 (HTML): Section 4.1 and Table 1 of Appendix A.
- arXiv 2403.08059: v1 for the renderer sentence, v3 for the rendering paragraph and the real-cadaver
  and synthetic-validation numbers; v2's renderer sentence stands on this note's first reading and the
  checkpoint on #130, since arxiv.org rate-limited the re-read on 2026-10-23.
- arXiv 2506.13292v2 (HTML): its structure, Sections 1 to 5 and Appendices A to F, Figure 8 in
  Appendix B, and the abstract's code link; Zenodo 15753063, the record page (files, licence,
  description, DOI line).
- github.com/arcadelab/fluoroseg (README; src/fluoroseg/alb/build_aug.py), github.com/arcadelab/fluorosam
  and github.com/benjamindkilleen/IPCAI-language-digital-twin, cloned on 2026-10-23 and searched for
  noise, scatter and render settings.
- Sekuboyina and others, "Pushing the limits of an FCN and a CRF towards near-ideal vertebrae
  labelling", ISBI 2023 (doi 10.1109/ISBI53787.2023.10230520; arXiv 2108.06554), the abstract; Ahmad,
  Ali and Jung, HSI 2025 (doi 10.1109/HSI66212.2025.11142408), the abstract through Kyungpook National
  University's research portal.
- This repository: docs/research/lumbosacral-to-cervical-extrapolation.md (its table in section 2 and
  the second reading of 8.1), docs/research/ct-priors-for-2d-detection.md section 6,
  docs/research/demo-plan.md, docs/research/evaluation/README.md, tools/evaluate.py, grid/README.md,
  grid/run-platform-fetch.sh, docs/research/data-manifest/MANIFEST.md, and the comments on #70, #130,
  #131 and #135.
