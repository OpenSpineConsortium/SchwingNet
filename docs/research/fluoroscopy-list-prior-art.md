# The owner's fluoroscopy list as prior art and baselines

Source: the thread "Dataset census and roadmap", 2026-10-23, on two asks of the owner's that day. At
12:22 UTC the owner uploaded a two-page summary from Google Gemini titled "Fluoroscopic AI Dataset
Author Contacts", with: "im not missing any of these, the last one seems to be exactly what i need
to convert all of my different XRay corpuses into a common preprocessed unified dataset" (the last
one being the NIH and Yale denoising paper). At 12:31 UTC, on the first answer: "can i draw anything
from their methods as prior art or a baseline?". Read from the sources in section 6 on 2026-10-23,
and corrected the same day from an adversarial review (section 7). Confidential with the rest of
this repository: it says where the provisional's claims can and cannot rest, so nothing of it leaves
before the provisional is filed. Grades are those of docs/research/xr-from-3d/README.md section 3:
Measured is this project's own record, Published is shown in the source named, Inferred is reasoned
here and not shown. Nothing here is legal advice; what is cited and what is claimed are counsel's.

## 1. The list, item by item

The records named are those of OpenSpineConsortium/spine-datasets.

| Item | What it is | Its record | As prior art here | As a baseline here |
| --- | --- | --- | --- | --- |
| Veriserum (ETH Zurich, 2025) | about 110,000 dual-plane fluoroscopic frames of knee implant phantoms with registered poses | veriserum: waits on the owner's call on its non-commercial term | no: no spine | no |
| DeepFluoro (Grupp et al., IPCAI 2020) | cadaveric pelvis fluoroscopy registered to CT | deepfluoro: held | for registration, not for levels | no |
| CAMS-Knee (Taylor et al., J Biomech 2017) and Stan (Dreyer et al., J Biomech 2022) | six living subjects with instrumented knee implants, moving-fluoroscope images registered to the implant parts; Stan is a reference subject made from their loads and kinematics, CSV files with no images | cams_knee, added 2026-10-23, behind an institutional agreement for non-commercial use, with one subject's example trial after a registration form under the same terms; Stan has no record, having no images | no: no spine | no |
| CM Spine (Zeng et al., Electronics 2024) | 208 AP lumbar G-arm images taken during surgery, L1 to L5 annotated | cm_spine_drive_file, identified 2026-10-23: the Drive file its authors link is not yet opened, and no licence is stated | yes, the closest on the list (section 3) | yes, at the cost of a training run (section 3) |
| LevelCheck (Johns Hopkins) | intraoperative radiographs registered to the patient's CT | levelcheck_jhu: asked; the PI answered on 2026-10-21 that the data stay at Johns Hopkins | yes; already a comparator row of docs/research/benchmarks-to-beat.md (Lo 2015) | yes, that row |
| CTSpine1K and X23D (Jecklin et al., J Imaging 2022) | 1,005 public spine CTs; X23D renders 17,420 DRRs from 871 of them to rebuild the lumbar shape from a few views, and tests on renders alone | ctspine1k: held; X23D ships no data | X23D for 3D shape from sparse views, not for levels; its code is withheld "due to a pending patent application" | no |
| DeepDRR (Unberath et al., MICCAI 2018), DiffDRR (Gopalakrishnan and Golland, 2022), ProST (Gao et al., MICCAI 2020) | software that renders X-rays from CT: DeepDRR with scatter and quantum noise, the other two differentiable | none: software, not data | yes, for any claim on rendering fluoroscopy from CT with physics noise (workstreams C, M and P) | no: they name no level |
| Real-time video denoising (Sadda and Qarni 2018) | a learned denoiser for angiographic fluoroscopy | none: no data released | narrowly, and a granted patent is closer (section 2) | as an optional arm of an ablation, from the literature (section 2) |

## 2. The denoiser: Sadda and Qarni 2018

Sadda P, Qarni T. "Real-Time Medical Video Denoising with Deep Learning: Application to
Angiography." Int J Appl Inf Syst 2018;12(13):22-28, doi:10.5120/ijais2018451755, PMC5985814 (Yale
School of Medicine; NIH grant T35DK104689).

### What it did (Published)

- Data: 20 coronary angiogram videos from a stock-footage vendor, grayscale, 320 x 240 to 512 x 512,
  labelled clear or noisy by eye; 4 clear videos held out.
- Training: 1,150 random 60 x 60 patches from 190 clear frames, with Gaussian noise of mean 0 and
  sigma 0.05 added, and no other kind of noise.
- Network: a 13-layer convolutional autoencoder in Keras and TensorFlow, three convolution and
  max-pool stages of 70, 60 and 50 filters (3 x 3), a 50-filter convolution, then three upsampling
  stages of 60, 70 and 1 filters, ReLU throughout and a sigmoid output; mean squared error, Adam
  from 1e-4, 1,500 iterations.
- Test: 675 patches from 150 clear frames, with the training's Gaussian noise, and with speckle
  (multiplicative, uniform, variance 1/3) and salt and pepper (pixels recoloured white or black,
  "each with a probability of 0.05"), neither seen in training; compared with BM3D by MSE and SSIM
  on the patches.
- Results (Tables 1 to 3): BM3D's MSE is one to two orders below the network's in all three tests
  (Gaussian 1.4e-4 against 0.014, speckle 9.1e-4 against 0.022, salt and pepper 0.0028 against
  0.19), while the network's SSIM is above BM3D's (0.99, 0.99 and 0.97 against 0.97, 0.88 and 0.64).
  The authors call the Gaussian difference "marginal", and note that BM3D smooths away the smallest
  vessels that the network keeps.
- Speed (Tables 4 and 5): on average 0.44 s on an unnamed CPU against BM3D's 1.81 s, and 0.021 s on
  an unnamed GPU, with BM3D's GPU times estimated from speedups reported elsewhere, not measured.
  The timing ran on 1,000 patches drawn from 100 frames, and "Both the neural network and the BM3D
  algorithms were evaluated on the patches" (Section 3.4), so the paper's "single image" is a patch
  by its own account; the timing patches' size is not stated, and those of training and test are 60
  x 60.
- Its own limits, in its conclusion: generality traded for performance, so that it is "unlikely to
  transfer well" to images "such as x-rays that show bones instead of blood vessels", which are this
  project's images; and video processed "as a bag of unrelated still image video frames". The set is
  also small, and was "subjectively divided" into clear and noisy, which the paper does not count
  among its limits. No code, weights or data are released.

### Why it does not make one dataset of the corpora (Inferred)

- The corpora differ by device and setting: kVp, dose, detector, the vendor's own processing
  (unsharp masking, equalisation, LUTs), collimation and grids, as workstream E lists them
  (docs/research/xr-from-3d/README.md section 3, E). Noise follows from two of those, dose and
  detector, and a network that learned to remove Gaussian noise does not undo a LUT or an unsharp
  mask.
- A learned filter moves edges. The paper's own comparison is about which method keeps the smallest
  structures, and here those structures are the vertebral corners the labels sit on, so any denoiser
  is judged by corner error, not by MSE.
- The unifying step exists: tools/bank.py writes every source into one bank format, and
  tools/ingest.py and tools/catalog.py turn the banks into one versioned catalog
  (docs/research/data-catalog.md); what is left of the device difference is #61's four layers.
- One gap seen while reading (Measured from the code at 7708538): bank.py's DICOM path applies the
  modality LUT, inverts MONOCHROME1 and cuts the 0.5 to 99.5 percentile window to 8 bits, and does
  not read the VOI LUT, which is where #61's layer 1 begins.

### As prior art (Inferred; counsel's to judge)

- It discloses a convolutional autoencoder that denoises fluoroscopic angiogram frames, learned from
  clean frames with synthetic Gaussian noise added, and timed at 0.021 s a patch on a GPU, which it
  calls real time (its bar is read below, under its timing). BM3D (Dabov et al., IEEE Trans Image
  Process 2007) is the classical prior art for denoising as such.
- Closer art for learned denoising of live fluoroscopy is a granted patent: Subtle Medical's US
  11,769,229 B2, "Systems and methods for real-time video denoising" (Gong, Duffy, Datta and Van
  Veen; priority 18 June 2021, granted 26 September 2023). Its claim 1 is a two-stage deep-learning
  framework for a live stream of medical frames, a first network denoising each frame in the spatial
  domain and a second predicting the final frame from several of them, in time and space, with a
  motion map; its claim 8 is claim 1 where the apparatus "is performing fluoroscopic imaging"
  (Published; the claims and dates as Justia prints them, and Google Patents, which lists it as
  active).
- Neither, in what was read (Sadda in full, the patent's claims and abstract), discloses anything of
  the spine, of levels, of a constraint that keeps shape (corners or body masks), of mapping real
  frames toward renders, of device harmonisation, or of naming after denoising.
- That does not leave the shape constraint itself open. TD-GAN (Zhang, Miao, Mansi and Liao, MICCAI
  2018, arXiv 1806.07201, a row of docs/research/lumbosacral-to-cervical-extrapolation.md section 2)
  translates between DRRs of labelled CTs and real X-ray topograms with "an added module leveraging
  the pre-trained DI2I to enforce segmentation consistency", DI2I being a segmenter trained on the
  DRRs, and so parses the real images (Published; the abstract). Segmentation-conditioned
  normalisation, in MRI and OCT, is what workstream E's layer 4 calls "the published version of the
  same idea" (docs/research/xr-from-3d/README.md section 3, E). So the step of #135 that applies
  "the shape-preserving denoiser of workstream E, real to render-like"
  (docs/research/lumbosacral-to-cervical-extrapolation.md, its step 2) rests nothing new on learned
  denoising, nor on a shape constraint from projected CT labels as such. What these do not show, in
  what was read, is narrower: level-specific targets, a soft body mask and corners for each named
  level, held through the correction and used before levels are named on fluoroscopy. Whether that
  is new, and what any claim would say, is counsel's.
- These belong on the list counsel reads before the provisional is filed by 30 October: Sadda, BM3D,
  Subtle's patent, TD-GAN, the closer art of section 3, and the two pending applications the reading
  met, X23D's, for which its code is withheld, and the contour registration's EP25168706.7
  (docs/research/benchmarks-to-beat.md section 1). How each bears on novelty and on freedom to
  operate is counsel's to decide.

### As a baseline (Inferred)

- #135's reverse ablation (the issue's step 5, and step 6 of
  docs/research/lumbosacral-to-cervical-extrapolation.md section 5) removes one ingredient at a
  time, "no denoising" among them. Widening that one removal into four arms on the same held test
  persons is this note's proposal, not #135's design: no denoiser; BM3D; the shape-preserving
  denoiser with its shape loss switched off, trained on the same pairs of real frames and renders;
  and the shape-preserving denoiser itself. The third arm is the control, since it differs from the
  fourth by the constraint alone.
- A rebuild of Sadda and Qarni's network is an optional fifth arm, from the literature, and not a
  control: it learns to remove Gaussian noise from clean patches, while #135's denoiser "is trained
  to take a real frame to its DRR-like image" on paired frames. No document yet says what network
  that denoiser is, and workstream E's four layers hold no denoiser; its nearest relative is layer
  4, shape as a target (docs/research/xr-from-3d/README.md section 3, E).
- Each arm is scored as this repository scores: naming accuracy per level with its Wilson interval,
  leave-one-device-out, the corner error against the projected truth, and the arm's time inside the
  whole frame path's p95 under task #13's rules. Patch MSE and SSIM say nothing about corners.
- Sadda's paper is complete enough to rebuild from (the layers, filters, loss, optimiser and patch
  size above). Every arm is a training run, so none starts before the owner's word and the number
  (docs/project.md); BM3D needs a package the repository does not have (pixi.toml lists none), which
  is an issue first (.claude/rules/writing.md).

### Its timing is not a reference

Its real-time bar is ten times too slow: "the minimum speed of one frame in 0.33 seconds that is
needed to process 30-frame-per-second video in real-time" (Section 3.4), where 30 frames a second is
33 ms a frame. Its 21 ms is on an unnamed GPU and, by its own account, for one patch, not a frame. A
denoiser arm's time is measured here inside the whole frame path, on the deployed file with ONNX
parity, and that path's p95 must stay under 97 ms, one frame interval of C-ArmLSpine's sweeps at
10.3 frames a second (docs/research/latency-and-sweep/README.md).

## 3. Three closer comparators

### CM Spine's own paper (Zeng et al., Electronics 2024)

Zeng Y, Wang K, Dai L, Wang C, Xiong C, Xiao P, Cai B, Zhang Q, Sun Z, Cheng E, Song B
(corresponding). "Exploring Neighbor Spatial Relationships for Enhanced Lumbar Vertebrae Detection
in X-ray Images." Electronics 2024;13(11):2137, published 30 May 2024 (Anhui Medical University; the
Hefei Institutes of Physical Science, Chinese Academy of Sciences; the University of Science and
Technology of China; Hefei University). The page prints nine names, an ellipsis and Song B; Cheng E
is from MDPI's own citation of the paper, and the author contributions give these eleven sets of
initials.

- What it reads at test: one AP lumbar image, with no CT and no prior image. The method is a
  two-stage CenterNet with Hourglass backbones, the first stage's heatmap fed to the second, and two
  added output heads, for the visibility of each vertebra's neighbours above and below and for its
  offsets to them ("the last two branches (blue) are used to predict the visibility and relative
  offsets of neighboring vertebrae", Figure 2). It has no graph network, though the list said it had
  (Published).
- Data: CM Spine, 208 AP lumbar images at 1024 x 1024 from a Geelin500-A mobile dual-mode G-arm,
  "anterior view images during surgical procedures", of patients with lumbar disc herniation or
  compression fractures, 148 to learn and 60 to test, 537 vertebrae annotated L1 to L5; and BUU's
  public 400 AP and 400 lateral films, 300 and 100 per view (Published). The paper gives no patient
  count, does not say that the 148 and 60 are split by patient, never uses the word fluoroscopy, and
  has no ethics or consent statement (Published, by their absence from the text).
- Numbers: COCO AP over IoU 0.5 to 0.95, per level. On CM Spine it is 13.6 points above CenterNet on
  average (L1 +6.0, L2 +7.7, L3 +20.1, L4 +25.1, L5 +9.3); on BUU, +6.5 over CenterNet, +1.9 over
  YOLOv5 and +10.0 over Faster R-CNN on AP films, and +4.8, +0.8 and +12.3 on laterals. The absolute
  values are in its Tables 3 to 5, which are images on the MDPI page and were not read, and no
  inference time is given (Published; the text alone).
- Released: "Our code and data are available at" github.com/zengyuyuyu/Neighbor, a src folder and a
  README, with no licence file and no weights. The README links a Drive file, the one
  spine-datasets' cm_spine_drive_file names; the data platform's download of it came back empty and
  nobody has opened it since, so whether it holds the 208 images is unchecked (that record).

What it means here (Inferred). Level naming on real images with no CT is published twice: Huang 2022
on AP and lateral Long-Film images of cadavers (a row of docs/research/benchmarks-to-beat.md section
2), and Zeng on AP lumbar images of patients taken during surgery with one G-arm. So the talk's
first-time claim (that section) holds only as the whole of it, never as level naming on real frames
alone: what neither shows is a per-level naming rate on real frames at any angle, the per-angle
curve, with its latency measured. Two parts need care. A detector of its own is the reported stack's
and not yet version 1's, which draws over truth boxes from the case's CBCT until a detector stage
exists (that section's version 1 row). And the latency is a first only while Zeng reports none: when
Zeng's code runs here it is timed under task #13's rules, and the latency becomes a comparison.

As a baseline Zeng is the nearest published method, but not rung 0 of the ladder
(docs/research/benchmarks-to-beat.md section 4.2), which stays FluoroSAM's released weights: Zeng
releases no weights, so its code run on the held C-ArmLSpine persons is a training run, which waits
on the owner's word and the number (docs/project.md). Both comparisons, its code on C-ArmLSpine and
SchwingNet on CM Spine's 60 test images, are scored by naming accuracy per level, since its AP mixes
finding a body with naming it. The second can give no person count beside its Wilson interval, since
the paper gives no patient count and no patient split, and for the same reason the paper's own AP
gains may be optimistic. The code is public with no licence, so it is run for the comparison and
never copied into this repository. The data carry no licence and the paper no consent statement:
whether CM Spine may be used here goes to counsel, beside COBRA's CC BY-NC term
(docs/memory/from-3d-to-x-ray.md), and whether the owner's IRB determination covers it is the
owner's to confirm, as HPR 2026-330 did for VinDr-SpineXR
(docs/memory/vindr-is-covered-by-hpr-2026-330.md).

### VDVM (Zhang et al., J X-Ray Sci Technol 2023)

Zhang R, Hu Y, Zhang K, Lan G, Peng L, Zhu Y, Qian W, Yao Y. "VDVM: An automatic vertebrae detection
and vertebral segment matching framework for C-arm X-ray image identification." J X-Ray Sci Technol
2023;31(5):935-949, doi:10.3233/XST-230025.

- What it reads at test: a C-arm image and a DR radiograph of the patient, full-length in training
  ("203 full length X-ray images to train the vertebra detection model") and lumbar in the test set;
  the abstract does not say which DR image each C-arm image is matched to at test. YOLOv3 finds the
  vertebrae on both, Mobile-Unet draws their contours, the tilt is corrected, and a match over
  several vertebrae by visual information fidelity pairs the C-arm's vertebrae with the radiograph's
  segments (Published; the abstract alone).
- Numbers: learned from 382 C-arm and 203 full-length images; vertebra finding mAP 0.87 on 31 C-arm
  and 0.96 on 31 lumbar DR test images; segment matching accuracy 0.733 on 31 C-arm images, which
  the abstract does not define (Published; the abstract alone).

What it means here (Inferred). Like LevelCheck it needs a second image of the patient, a radiograph
rather than a CT, so the distinction a claim draws is no prior image of the patient at all. Its
0.733 sits beside the all-levels row on C-ArmLSpine, which reads no other image at inference, though
until the full text says how it is counted, per image or per vertebra, the two are not one measure.

### Cervical corners on swallow videofluoroscopy (Zhang et al., Med Image Anal 2021)

Zhang Z, Mao S, Coyle J, Sejdic E. "Automatic annotation of cervical vertebrae in videofluoroscopy
images via deep learning." Med Image Anal 2021;74:102218, doi:10.1016/j.media.2021.102218,
PMC8560570 (University of Pittsburgh).

- What it reads at test: one frame of a swallow videofluoroscopy, the patient seated "in the lateral
  plane", with no CT. A two-stage network finds the vertebral region and then fixed named points:
  "the antero-inferior corner of C2, and the anterior-superior and anterior inferior corners of the
  C3 and C4 vertebral bodies"; C3 was labelled "on only first three frames of each subjects", so the
  first stage learned from C2 and C4 alone (Published).
- Data: "1518 swallowing videofluoroscopies from 265 patients" with swallowing difficulty, on a
  Toshiba Ultimax, to learn, and 70 healthy volunteers on a GE Precision 500D to test; "no person in
  the training group is in the validation and test group" (Published).
- Numbers: a mean distance from the annotations of 4.20 +/- 5.54 pixels, against 4.35 +/- 3.12
  between human raters; 93 % of points within five pixels. The abstract says real time, and the
  text, as read, gives no time (Published).
- Its data are the Pittsburgh corpus that spine-datasets' pittsburgh_swallow records, asked for by
  the owner on 2026-10-20 and still waiting; that record's truth line said C2 and C4 only, and is
  corrected from the paper (section 5).

What it means here (Inferred). Named cervical corners on real fluoroscopy with no CT are published,
but for three fixed bodies in a field that holds them, so the network chooses no level by counting.
It narrows no first the talk claims, and it is #135's cervical comparator: the same corners, scored
as corner error with the person count, on its 70 test volunteers once the Pittsburgh request is
granted.

## 4. What the list got wrong

Each item was checked against its source (Published, but for LevelCheck's answer, which is this
project's own record, Measured), so the list itself is never quoted as a source:

- The denoiser is not sub-millisecond: 21 ms a patch on a GPU (Table 5 and Section 3.4). It was not
  learned from three kinds of noise, but from Gaussian noise alone, with speckle and salt and pepper
  as tests.
- The list said CM Spine needs an email to the authors; their repository links a Drive file instead,
  though whether it holds the set is unchecked and no licence is stated, so writing to the
  corresponding author for terms stays an option (spine-datasets cm_spine_drive_file). Its method
  has no graph network.
- CAMS-Knee's images are registered to the implant parts, and the set comes under an institutional
  agreement for non-commercial use, with one subject's example trial after a registration form under
  the same terms; Stan has no images at all.
- X23D has no data of its own: its renders are of CTSpine1K.
- LevelCheck's data are not one data use agreement away: the PI answered on 2026-10-21 that they
  stay at Johns Hopkins and were not shared at publication, and the follow-up to a co-author waits
  (spine-datasets levelcheck_jhu).

## 5. What changed

- OpenSpineConsortium/spine-datasets#217: cm_spine_drive_file identified as CM Spine, and cams_knee
  added.
- OpenSpineConsortium/spine-datasets#218: pittsburgh_swallow's truth line corrected to the corners
  of C2, C3 and C4, C3's on the first three frames of each subject.
- docs/research/benchmarks-to-beat.md: the rows of section 3 (Zeng, VDVM and Zhang 2021), and the
  first-time claim narrowed by Huang 2022 and Zeng.
- Nothing was run, fetched or sent.

## 6. Read

- Sadda and Qarni 2018, PMC5985814, through the session's fetch tool, since the proxy refuses PMC to
  a direct download: Sections 3.1 to 3.4, Tables 1 to 5 and the conclusion; the review re-read it
  through PMC's OAI record, where the article page asked for a captcha.
- Zeng et al. 2024: the MDPI page 2079-9292/13/11/2137, its text, read twice (the tables are images
  there, and the PDF did not read), and MDPI's citation of it; github.com/zengyuyuyu/Neighbor, its
  file list and README.
- Zhang et al. 2023: the abstract, through Stevens Institute of Technology's research portal.
- Zhang, Mao, Coyle and Sejdic 2021: PMC8560570, its abstract and methods.
- Zhang, Miao, Mansi and Liao 2018 (TD-GAN): arXiv 1806.07201v1, the abstract.
- US 11,769,229 B2: its claims, filing date and priority on Justia
  (patents.justia.com/patent/11769229), and its bibliographic page on Google Patents.
- Jecklin et al. 2022: PMC9604813, its data and its code statement.
- CAMS-Knee: movement.ethz.ch/data-repository/cams-knee-project.html; cams-knee.orthoload.com, its
  data request and sample download pages, its moving fluoroscopy and video pages, the sample and
  full dataset descriptions and Stan's (Description_CAMS_Stan_Dataset_v1.0.pdf).
- arXiv 2509.05483v1 (Veriserum): its introduction and references 2 and 18.
- This repository: tools/bank.py at 7708538, pixi.toml, docs/research/xr-from-3d/README.md,
  docs/research/lumbosacral-to-cervical-extrapolation.md, docs/research/benchmarks-to-beat.md,
  docs/research/latency-and-sweep/README.md and issue #135; spine-datasets' records
  cm_spine_drive_file, cams_knee, levelcheck_jhu and pittsburgh_swallow.

## 7. The adversarial review

A second reader, asked to make the note fail, read it against every source above on 2026-10-23. No
number was wrong. What it found, and what was done:

- Three inferences went further than their sources: the shape constraint as the part that may be new
  (TD-GAN and E's layer 4 already show it; narrowed to level-specific targets, novelty left to
  counsel); the first-time claim (Huang 2022 had narrowed it before Zeng, version 1 has no detector
  of its own yet, and the latency is a first only while Zeng reports none); and the four-arm
  ablation (this note's proposal, not #135's, now with a control that differs by the constraint
  alone).
- Two sentences read as legal judgements: that two applications bear on freedom to operate rather
  than on novelty, and what a claim would have to say. Both are now counsel's.
- Overstatements fixed: VDVM's second image, full-length only in training; CM Spine's Drive file,
  unopened; Sadda's timing, per patch by its own account; Zeng's two heads; Sadda's stated limits;
  LevelCheck's answer graded Measured; CAMS-Knee's example trial.
- Caveats added: CM Spine's missing patient count, split, licence and consent statement; the
  training run Zeng's code needs; why Zeng is not rung 0.
- Missing art added, each read before it was counted: Subtle Medical's patent, and Zhang et al.
  2021, whose data are a set the owner has already asked for.
