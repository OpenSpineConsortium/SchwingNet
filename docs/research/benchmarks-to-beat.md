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
- Released: the code, the weights (2.5 GB on Google Drive) and FluoroSeg (2.65 TB on Hugging Face,
  gated, CC BY-NC-SA 4.0; the owner accepted its terms on 2026-10-22). The cadaver set is not
  released.

### The language-promptable digital twin (Killeen et al., arXiv 2412.08020, December 2024)

Voice control of a robotic C-arm (Loop-X) through GPT-4o and Whisper, with FluoroSAM's masks from
several views stacked into a sparse 3D "digital twin" of one cadaveric torso (80 images, 46 unique
viewpoints; truth from four stitched navigated CBCTs segmented by TotalSegmentator).

- End-to-end voice success 83.54 % over 158 prompts (visualisation 82.6 %, collimation 60.7 %,
  viewfinding 83.3 %).
- FluoroSAM on this cadaver, text only: vertebrae as one class 0.78 +/- 0.15 Dice; vertebral levels
  0.04 Dice; ribs 0.02 Dice; centroid error 58.87 +/- 50.29 mm over the top 40 prompts.
- The twin localises 35 structures within 51.68 +/- 30.84 mm from random orientations; collimation
  boxes precision 0.26, recall 0.70.
- Nothing released; no baseline compared.

### Multi-view X-ray/CT registration by bone substructure contours (Flepp et al., arXiv 2506.13292)

Two calibrated X-rays of the distal femur, a fiducial with 16 metal beads for the pose, an nnU-Net
that draws three substructure contours (diaphysis, medial and lateral condyle) trained on
patient-specific DRRs, and a contour ICP that matches within a substructure only.

- Real test: 5 cadaveric specimens, ten views each at about 9 degrees apart, Siemens Fluorospot, CT
  at 0.2 mm slices.
- Numbers: mean reprojection distance 0.67 mm (ImFusion, manual four-point start, 5.35 mm; Zhang's
  silhouette ICP 4.03 mm); sub-millimetre in 96.1 % of 30 runs, 92 % of 50 random starts (plus or
  minus 50 mm, plus or minus 180 degrees), 100 % with the restart; contours at 0.59 mm Chamfer.
- Released: the dataset (X-rays, poses, CTs, contour masks of 5 specimens, Zenodo 15753063), the code
  by request under a non-commercial licence; patent pending EP25168706.7. The femur, not the spine.

## 2. What each of them cannot do, which is the opening

| Capability | FluoroSAM / the twin | Contour registration | SchwingNet's claim |
| --- | --- | --- | --- |
| Name the vertebral level on a real fluoroscopic frame | no: 0.04 Dice on levels, the paper's own number | no: it has no levels | yes, the product; measured per level on held-out real frames |
| Work without a CT of the patient | yes for masks, no for the twin's geometry (CBCT truth) | no: needs the preoperative CT and a fiducial | yes, CT-free at the podium |
| Any angle | trained on a hemisphere; tested at plus or minus 30 and 90 on one device | two views 45 degrees apart or more | the per-angle curve on real sweeps (C-ArmLSpine, COBRA) is the test |
| Classify (anomaly, transitional anatomy) | no | no | the screener and the counting prior (xr-from-3d A, F, H) |
| Real fluoroscopy | trained on renders only, tested on one cadaver and one device | trained on renders of the same specimen, tested on the specimen | trained on real films and frames plus renders, tested leave-one-device-out |
| Latency | not reported | nnU-Net at 18 GB GPU, ICP to converge; no number | the 97 ms budget, measured |

So the first-time claims the talk can make, each with its measurement: level naming on real frames
with no CT, at any angle, with latency; and anomaly and transitional-anatomy classification from a
single frame. Segmentation of bone as one class is not a claim to make against FluoroSAM, which does
it well (0.78 to 0.90 with points); the comparison is on levels, where it scores 0.04.

## 3. How FluoroSAM handles the gap between renders and real fluoroscopy

Read from fluoroseg/src/fluoroseg/alb/build_aug.py and the paper. It is intensity-space domain
randomisation and nothing else:

1. Every render is taken through the negative log, inverted, and windowed by a k-means mixture window
   (the window's bounds from the intensity clusters, so the bone band fills the range), as the real
   images are windowed at inference to the 99th percentile.
2. Then, at random, an inversion with probability 0.5, and one of: CLAHE (clip 4 to 6, tiles 8 x 12),
   or two to four of {Gaussian, motion or median blur; sharpen or emboss; contrast scaled by -2 to 2;
   a Gaussian non-uniform contrast (alpha 0.6 to 1.4, sigma 0.1 to 0.5 of the image); fog or
   drizzle; pixel dropout at 5 % or coarse dropout of 8 to 20 holes up to 64 px; channel shuffle}.
3. No noise model beyond DeepDRR's, no scatter model beyond DeepDRR's, no detector or image
   intensifier model, no vendor processing (unsharp masking, edge enhancement, LUTs), no grid lines,
   collimation edges or burnt-in text, no style transfer, and no fine-tuning on real images. The gap
   is never quantified: the synthetic test gives 0.43 text-only Dice, the real cadaver 0.39 on hard
   tissue and 0.26 overall, and the only real device is the Loop-X.

What this means for SchwingNet: the randomisation is the same layer 2 that xr-from-3d's workstream E
names (SyntheX's recipe), so it is table stakes, not a differentiator. The differentiators are layers
1, 3 and 4 there: reading each device's own LUTs from the header, a learned per-device intensity
correction, and shape as a target supervised by projected CT labels; and the measurement they lack,
leave-one-device-out accuracy on real frames across several devices (the record holds C-ArmLSpine,
FluoroCap's panels, DeepFluoro's vendor frames and COBRA's projections, each from different hardware).

## 4. The gradual reverse ablation

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

## 5. The CT-and-X-ray pairs, their segmentations, and the plan

The owner's ask: find out whether the held CT-X-ray sets come with segmentations, plan ITK-SNAP and
AI-assisted segmentation with Dr Tech's verification into the priors work, and use registration code
for supervised pixel-to-pixel 3D-to-2D priors.

| Set | X-rays | CT | Segmentation shipped | What is needed |
| --- | --- | --- | --- | --- |
| C-ArmLSpine (held) | 149 cases, 299 spot frames, 59,609 DICOM frames, 2 sweeps | CBCT per case | level labels on the CBCT, two labellers agreeing on 814 of 910 bodies; no body masks | masks per body: TotalSegmentator, then correction |
| COBRA (held, CC BY-NC) | 692 cases of raw CBCT projections with geometry | planning CT and the reconstruction | none for vertebrae | TotalSegmentator on the planning CT, then correction; the geometry projects them |
| DeepFluoro (held) | 366 H5 frames, 2,659 vendor frames | CT of 6 specimens | pelvis and femur masks, no vertebrae | lumbar bodies to add |
| Ljubljana 2D/3D gold standard (held) | 18 frames of one cadaver, L1 to L5 | CT, with the pose of every frame | the registration's gold standard; no body masks | masks for five bodies, then projection |
| FluoroSAM's cadaver | 464 frames | CBCT | TotalSegmentator | not released |
| Flepp's femur set | 50 X-rays | 5 CTs | contour masks, bone models | not spine; a registration benchmark only |

The plan, as workstream O of the xr-from-3d programme (issue #127 under #56):

1. Automatic first pass: TotalSegmentator (vertebrae and sacrum) on every planning CT and CBCT of
   C-ArmLSpine, COBRA and DeepFluoro, on the grid, as one array job; its masks are the AI assistance.
2. Correction by the owner in ITK-SNAP, case by case, with the level names from the C-ArmLSpine
   labels and the counting prior as the check; each corrected mask is a file under the case with the
   editor's name and the date in its sidecar, never in the mask.
3. Verification by Dr Tech: a second reader marks each case verified or returned, in a review sheet
   the repository tracks (tools/docx_review.py's pattern, or a CSV in the case folder); a body counts
   as gold only when verified. The two-reader agreement is the number reported, as C-ArmLSpine's
   814 of 910 is.
4. Projection: for C-ArmLSpine and COBRA the pose is stored, so the verified masks project through it
   to per-pixel label maps and corners on every real frame (xr-from-3d D, use 1). For DeepFluoro the
   released registrations give the pose.
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
is non-commercial like COBRA's, the same lawyer's question. Not fetched until the owner says so and
the space (2.65 TB against the volume's 22 TB quota, 7.3 TB used) is his call.

The FluoroSAM weights (2.5 GB, Google Drive) are the one download row 7 needs; the container cannot
reach Google Drive, so the thread that holds the grid's Drive route ("Granted datasets onto the grid")
fetches them (fluorosam_model_weights.pth, about 1 GB) to the data root's fluorosam_weights_drive
through SchwingNet #124, as it fetched the Killeen archive.

## 7. Open questions for the owner

- The number of C-ArmLSpine cases he and Dr Tech will correct and verify before the talk.
- Whether FluoroSeg is fetched at all before the licence question is answered.
